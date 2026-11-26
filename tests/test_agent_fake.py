import os

import pytest

from fakes import ScriptedClient, oracle_script, response, tool_use
from menu_agent import agent, score


@pytest.mark.parametrize("rid", ["P1", "P2", "P3", "P4"])
def test_oracle_agent_scores_perfectly(rid, tmp_path):
    cs, ref, script = oracle_script(rid)
    client = ScriptedClient(script)
    draft = agent.run_agent(cs, "claude-sonnet-5-5", str(tmp_path / "ledger.json"), client=client)
    assert draft["run"]["stop"] == "finished"
    s = score.score(draft, ref, cs)
    c = s["M1_coverage"]
    assert c["captured"] == len(ref["items"]) and c["invented"] == 0 and c["duplicated"] == 0
    a = s["M2_field_accuracy"]
    for f in ("name", "section", "description", "price", "restaurant_facts"):
        assert a[f]["correct"] == a[f]["compared"], f
    assert a["ingredients"]["f1"] == 1.0
    assert s["M3a_verbatim"]["verbatim"] == s["M3a_verbatim"]["facts"]
    assert s["M4_unknowns"]["fabricated"] == 0 and s["M4_unknowns"]["kept"] == s["M4_unknowns"]["reference_unknowns"]
    assert s["M5_problems"]["flagged"] == s["M5_problems"]["reference_problems"]
    assert not s["M6_statements"]["missed"]
    assert s["M9_dish_type"]["different"] == 0
    # caching: system, tools and the last message carry breakpoints; never more than 4
    sent = client.sent[-1]
    marks = sum(1 for m in sent["messages"] for b in m["content"] if isinstance(b, dict) and "cache_control" in b)
    assert marks == 1 and "cache_control" in sent["system"][0] and "cache_control" in sent["tools"][-1]
    assert draft["run"]["cost"]["usd"] > 0


def test_budget_guard_refuses_to_start(tmp_path):
    import json
    led = tmp_path / "ledger.json"
    led.write_text(json.dumps({"runs": [{"usd": 15.0}], "total_usd": 15.0}))
    cs, _, script = oracle_script("P1")
    with pytest.raises(agent.BudgetError):
        agent.run_agent(cs, "claude-sonnet-5-5", str(led), budget=17.0, run_ceiling=3.0, client=ScriptedClient(script))


def test_run_ceiling_stops_and_ledger_counts(tmp_path):
    import json
    cs, _, _ = oracle_script("P1")
    big = {"input_tokens": 400_000, "output_tokens": 10_000, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    script = [response([tool_use("list_captures", {})], usage=big)] * 3
    draft = agent.run_agent(cs, "claude-sonnet-5-5", str(tmp_path / "l.json"), run_ceiling=0.5,
                            client=ScriptedClient(script))
    assert draft["run"]["stop"] == "run_ceiling"
    assert json.load(open(tmp_path / "l.json"))["total_usd"] == pytest.approx(0.9)


def test_bad_quote_is_refused_and_reported_back(tmp_path):
    cs, _, _ = oracle_script("P1")
    bad = {"capture_id": "P1-C1", "section_path": ["Starters"], "name": "Chowder Cup",
           "description": {"state": "known", "quote": "a creamy clam soup"}, "price": {"state": "not_stated"},
           "ingredients": [], "statements": [], "dish_type": {"id": None, "confidence": "unmapped", "rationale": ""}}
    script = [response([tool_use("read_capture", {"capture_id": "P1-C1"})]),
              response([tool_use("record_items", {"items": [bad]})]),
              response([tool_use("finish", {"sections_seen": [["Starters"]], "dish_lines_seen": 1})])]
    client = ScriptedClient(script)
    draft = agent.run_agent(cs, "claude-sonnet-5-5", str(tmp_path / "l.json"), client=client)
    assert draft["items"] == [] and draft["refusals"] == 1
    last_results = client.sent[-1]["messages"][-1]["content"]
    assert "quote not found" in last_results[0]["content"]


def test_haiku_long_prompt_tier():
    from menu_agent.pricing import request_cost
    short = request_cost("claude-haiku-5-5", {"input_tokens": 50_000, "output_tokens": 0})
    long_ = request_cost("claude-haiku-5-5", {"input_tokens": 150_000, "output_tokens": 0})
    assert short == pytest.approx(0.005) and long_ == pytest.approx(0.075)

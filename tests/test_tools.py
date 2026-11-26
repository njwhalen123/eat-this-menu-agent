import json
import os

from conftest import PRACTICE
from menu_agent import captures
from menu_agent.tools import ToolSession


def session(rid="P1", cap=12):
    return ToolSession(captures.load(os.path.join(PRACTICE, rid)), retrieval_cap=cap)


def item(**kw):
    base = {"capture_id": "P1-C1", "section_path": ["Starters"], "name": "Chowder Cup",
            "description": {"state": "known", "quote": "clams, potato, smoked bacon, cream"},
            "price": {"state": "known", "quote": "9"},
            "ingredients": [{"name": "clams", "quote": "clams, potato"}], "statements": [],
            "dish_type": {"id": None, "confidence": "unmapped", "rationale": ""}}
    base.update(kw)
    return base


def test_must_open_before_recording():
    s = session()
    out = json.loads(s.call("record_items", {"items": [item()]})[0])
    assert out["refused"] == 1 and "read_capture" in out["results"][0]["errors"][0]


def test_good_item_recorded_with_source_text():
    s = session(); s.call("read_capture", {"capture_id": "P1-C1"})
    out = json.loads(s.call("record_items", {"items": [item()]})[0])
    assert out["recorded"] == 1
    assert s.items[0]["description"]["text"] == "clams, potato, smoked bacon, cream"


def test_invented_quote_and_unnamed_ingredient_refused():
    s = session(); s.call("read_capture", {"capture_id": "P1-C1"})
    bad1 = item(description={"state": "known", "quote": "clams, potato, cream and love"})
    bad2 = item(name="Smoked Beet Salad", ingredients=[{"name": "walnuts", "quote": "roasted beets"}],
                description={"state": "not_stated"})
    out = json.loads(s.call("record_items", {"items": [bad1, bad2]})[0])
    assert out["refused"] == 2 and not s.items
    assert "not named in its quote" in " ".join(out["results"][1]["errors"])


def test_dish_type_must_exist_and_duplicates_refused():
    s = session(); s.call("read_capture", {"capture_id": "P1-C1"})
    out = json.loads(s.call("record_items", {"items": [item(dish_type={"id": "DT99", "confidence": "clear", "rationale": ""})]})[0])
    assert out["refused"] == 1
    s.call("record_items", {"items": [item()]})
    out = json.loads(s.call("record_items", {"items": [item()]})[0])
    assert out["refused"] == 1 and "already recorded" in out["results"][0]["errors"][0]


def test_retrieval_cap_and_unopened_pages_reported():
    s = session("P3", cap=2)
    assert not s.call("read_capture", {"capture_id": "P3-C1"})[1]
    assert not s.call("read_capture", {"capture_id": "P3-C2"})[1]
    text, err = s.call("read_capture", {"capture_id": "P3-C3"})
    assert err and "cap" in text
    s.call("finish", {"sections_seen": [], "dish_lines_seen": 0})
    assert any(p["kind"] == "missing_page" and p["capture_id"] == "P3-C3" for p in s.problems)


def test_conflicting_fact_needs_two_values():
    s = session(); s.call("read_capture", {"capture_id": "P1-C1"})
    v = {"capture_id": "P1-C1", "value": "x", "quote": "Hours: Tue–Sun 5 pm – 10 pm"}
    assert s.call("record_restaurant_fact", {"field": "hours", "state": "conflicting", "values": [v]})[1]
    assert not s.call("record_restaurant_fact", {"field": "hours", "state": "known", "values": [v]})[1]

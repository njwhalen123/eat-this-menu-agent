import json
import os

from conftest import PRACTICE
from menu_agent import baseline, captures, score


def test_baseline_is_deterministic_and_quotes_are_from_pages():
    for rid in ("P1", "P2", "P3", "P4"):
        cs = captures.load(os.path.join(PRACTICE, rid))
        a, b = baseline.run(cs), baseline.run(cs)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        ref = json.load(open(os.path.join(PRACTICE, rid, "reference.json")))
        s = score.score(a, ref, cs)
        assert s["M1_coverage"]["invented"] == 0


def test_baseline_rules_examples():
    lab = baseline.classify(["Starters", "Arancini 12", "Burrata", "tomato, basil", "Mains", "Cod", "$27"])
    assert lab == ["heading", "dish", "dish", "other", "heading", "dish", "price"]
    assert baseline._split_name("Pork Gyoza ...... 9") == ("Pork Gyoza", "")
    assert baseline._split_name("Tavern Burger – beef, bun 18") == ("Tavern Burger", "beef, bun")

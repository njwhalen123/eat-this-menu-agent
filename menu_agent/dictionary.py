"""The existing dish-type dictionary and the baseline's keyword lists."""
from __future__ import annotations

import csv
import os
import re

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_PAREN = re.compile(r"\s*\([^)]*\)")

# Variation strings too generic to name a dish on their own (method §9 log,
# 2026-11-25 clarification of rule 9).
VARIATION_STOPLIST = {"classic", "creamy", "cheese", "base components"}


def load_dish_types() -> list[dict]:
    with open(os.path.join(DATA, "dish_types.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["variation_list"] = [v.strip() for v in r["variations"].split(",") if v.strip()]
    return rows


def dish_type_ids() -> set[str]:
    return {r["dish_type_id"] for r in load_dish_types()}


def dictionary_text() -> str:
    """The dictionary as the agent sees it."""
    out = []
    for r in load_dish_types():
        v = f" (variations: {r['variations']})" if r["variations"] else ""
        out.append(f"- {r['dish_type_id']} {r['name']}{v}")
    return "\n".join(out)


def dish_type_keywords() -> list[tuple[str, str]]:
    """(keyword, dish_type_id) pairs for the baseline, longest first."""
    pairs = []
    for r in load_dish_types():
        kws = {_PAREN.sub("", r["name"]).strip()}
        for v in r["variation_list"]:
            v2 = _PAREN.sub("", v).strip()
            if not v2 or v2.lower() in VARIATION_STOPLIST:
                continue
            if " or " in f" {v2.lower()} " or "and/or" in v2.lower():
                continue
            kws.add(v2)
        pairs += [(k, r["dish_type_id"]) for k in kws if k]
    return sorted(pairs, key=lambda p: -len(p[0]))


def ingredient_vocabulary() -> list[str]:
    """Vocabulary terms with parenthetical notes removed, longest first."""
    with open(os.path.join(DATA, "ingredient_vocabulary.txt"), encoding="utf-8") as f:
        terms = {_PAREN.sub("", t).strip() for t in f if t.strip()}
    return sorted({t for t in terms if t}, key=lambda t: (-len(t), t.lower()))

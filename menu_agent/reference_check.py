"""Checks a reference against its saved pages: every name, description, price,
ingredient, statement and restaurant fact must be on a page, and every
ingredient must be named in its dish's description (the practice coding rule)."""
from __future__ import annotations

from .captures import CaptureSet
from .text import named_in


def _found(cs: CaptureSet, text: str) -> bool:
    return any(c.search.find(text) for c in cs.captures.values())


def check(ref: dict, cs: CaptureSet) -> list[str]:
    errs = []
    for r in ref["items"]:
        n = r["name"]
        if not _found(cs, n):
            errs.append(f"{n}: name not on any page")
        for h in r["section"].split(" > "):
            if not _found(cs, h):
                errs.append(f"{n}: heading {h!r} not on any page")
        for fld in ("description", "price"):
            if r[fld] is not None and not _found(cs, r[fld]):
                errs.append(f"{n}: {fld} {r[fld]!r} not on any page")
        for ing in r["ingredients"]:
            if not r["description"] or not named_in(ing, r["description"]) and not any(
                    named_in(w, r["description"]) for w in [ing.split()[-1]]):
                errs.append(f"{n}: ingredient {ing!r} not named in the description")
        for st in r["statements"]:
            if not _found(cs, st["text"]):
                errs.append(f"{n}: statement {st['text']!r} not on any page")
    for t in ref.get("menu_statements", []):
        if not _found(cs, t):
            errs.append(f"menu statement not on any page: {t!r}")
    for fld, v in (ref.get("restaurant_facts") or {}).items():
        if v is not None and not _found(cs, v):
            errs.append(f"restaurant fact {fld} {v!r} not on any page")
    return errs

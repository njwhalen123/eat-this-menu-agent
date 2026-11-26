"""The text-extraction-plus-keyword baseline (method §7), no model.

Rules, numbered as in the method:
 1. Text from the shared extractor (extract.py).
 2. Price: a token like 14, $14 or 14.50 at the end of a line, or alone on the next line.
 3. Section heading: 1–6 words, no price, not ending in a full stop, all upper case or
    title case, followed within 3 lines by a dish line. Consecutive headings nest.
 4. Dish line: a line with a price, or a title-case line of <= 8 words directly followed
    by a line starting in lower case. The name is the text before the price or a separator.
 5. Description: text after the separator on the dish line, then the following lines up
    to the next dish line or heading.
 6. Ingredients: whole-word keyword matches in the description, longest first.
 7. Warnings and labels: a fixed list of patterns, recorded as quoted statements.
 8. Restaurant facts: hours (weekday or "hours" plus a time) and address (number plus
    street suffix) only.
 9. Dish type: whole-word match of the dish name against type names and variations.
10. Everything else unknown; the only problem reported is "no text extracted".
"""
from __future__ import annotations

import re

from .captures import CaptureSet
from .dictionary import dish_type_keywords, ingredient_vocabulary
from .tools import DRAFT_FORMAT

VERSION = "baseline-v0"

PRICE_END = re.compile(r"(?:^|\s)(\$?\d{1,3}(?:\.\d{2})?)\s*$")
PRICE_ALONE = re.compile(r"^\$?\d{1,3}(?:\.\d{2})?$")
SEPARATORS = [" – ", " — ", " - ", " | ", ".."]
SMALL_WORDS = {"a", "an", "and", "or", "of", "the", "with", "on", "in", "to", "for", "&", "de", "la", "al", "di", "e"}
WARN_SUBSTR = ["contains", "allerg", "raw or undercooked", "consuming raw", "gluten-free", "gluten free",
               "vegan", "vegetarian", "nut", "may contain", "cross-contact"]
WARN_TOKENS = [("GF", re.compile(r"(?<![A-Za-z])GF(?![A-Za-z])")), ("(V)", re.compile(r"\(V\)"))]
WEEKDAYS = re.compile(r"\b(mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(day)?s?\b", re.I)
TIME = re.compile(r"\b\d{1,2}(:\d{2})?\s?(am|pm|a\.m\.|p\.m\.)\b|\b\d{1,2}:\d{2}\b", re.I)
ADDRESS = re.compile(r"\b\d{1,5}\s+[A-Za-z0-9 .'-]+\b(St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Way|Pl|Place|"
                     r"Sq|Square|Row|Ln|Lane|Wharf|Ct|Court|Dr|Drive|Pkwy|Parkway|Hwy|Terrace|Ter)\b\.?")


def _price(line: str) -> str | None:
    m = PRICE_END.search(line)
    return m.group(1) if m else None


def _is_title(line: str) -> bool:
    ws = [w for w in re.findall(r"[A-Za-z][A-Za-z'’\-]*", line)]
    if not ws:
        return False
    if line.upper() == line and any(c.isalpha() for c in line):
        return True
    return all(w[0].isupper() or w.lower() in SMALL_WORDS for w in ws)


def _starts_lower(line: str) -> bool:
    m = re.search(r"[A-Za-z]", line)
    return bool(m) and line[m.start()].islower()


def _split_name(line: str) -> tuple[str, str]:
    body = line
    p = _price(line)
    if p:
        body = line[: line.rfind(p)].rstrip()
    for sep in SEPARATORS:
        if sep in body:
            a, b = body.split(sep, 1)
            # a run of separator characters (a dot leader "......") is not a description
            return a.strip(), b.strip().lstrip(".-–—| ").strip()
    return body.strip(), ""


def _word_pattern(term: str) -> re.Pattern:
    # whole words, case-insensitive; a simple plural on the last word is forgiven (§9 log)
    esc = re.escape(term)
    return re.compile(r"(?<![A-Za-z])" + esc + r"(?:e?s)?(?![A-Za-z])", re.I)


_ING = None
_DT = None


def _vocab():
    global _ING, _DT
    if _ING is None:
        _ING = [(t, _word_pattern(t)) for t in ingredient_vocabulary()]
        _DT = [(k, d, _word_pattern(k)) for k, d in dish_type_keywords()]
    return _ING, _DT


def _match_ingredients(text: str) -> list[tuple[str, str]]:
    """(term, matched text) pairs, longest first, without overlaps."""
    ing, _ = _vocab()
    taken: list[tuple[int, int]] = []
    found = []
    for term, pat in ing:
        for m in pat.finditer(text):
            if any(m.start() < b and a < m.end() for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            found.append((m.start(), term, m.group(0)))
    return [(t, g) for _, t, g in sorted(found)]


def _warnings(line: str) -> list[str]:
    low = line.lower()
    hits = [w for w in WARN_SUBSTR if w in low]
    hits += [label for label, p in WARN_TOKENS if p.search(line)]
    return hits


def classify(lines: list[str]) -> list[str]:
    """Label each line: 'dish', 'price', 'heading' or 'other'."""
    n = len(lines)
    lab = ["other"] * n
    for i, ln in enumerate(lines):
        nxt = lines[i + 1] if i + 1 < n else ""
        if PRICE_ALONE.match(ln):
            lab[i] = "price"
        elif _price(ln) and not PRICE_ALONE.match(ln):
            lab[i] = "dish"
        elif PRICE_ALONE.match(nxt):
            lab[i] = "dish"
        elif _is_title(ln) and len(ln.split()) <= 8 and nxt and _starts_lower(nxt):
            lab[i] = "dish"
    for i, ln in enumerate(lines):
        if lab[i] != "other":
            continue
        nw = len(ln.split())
        if 1 <= nw <= 6 and not _price(ln) and not ln.rstrip().endswith(".") and _is_title(ln):
            if any(lab[j] == "dish" for j in range(i + 1, min(n, i + 4))):
                lab[i] = "heading"
    return lab


def run(cs: CaptureSet) -> dict:
    _, dts = _vocab()
    items, menu_statements, facts, problems = [], [], [], []
    seen_fact = set()
    k = 1
    for cid, c in cs.captures.items():
        lines = c.lines
        if not lines:
            problems.append({"kind": "other", "capture_id": cid, "where": c.url, "note": "no text extracted", "by": "baseline"})
            continue
        lab = classify(lines)
        path: list[str] = []
        run_heads: list[str] = []
        current = None
        for i, ln in enumerate(lines):
            if lab[i] == "heading":
                run_heads.append(ln)
                current = None
                continue
            if run_heads:
                if len(run_heads) >= len(path):
                    path = list(run_heads)
                else:
                    path = path[: len(path) - len(run_heads)] + run_heads
                run_heads = []
            if lab[i] == "dish":
                name, rest = _split_name(ln)
                price = _price(ln)
                if not price and i + 1 < len(lines) and lab[i + 1] == "price":
                    price = lines[i + 1]
                current = {
                    "item_key": f"B{k:03d}", "capture_id": cid, "section_path": list(path),
                    "name": {"text": name, "line": i + 1},
                    "description": {"state": "not_stated"} if not rest else {"state": "known", "text": rest, "lines": [i + 1, i + 1]},
                    "price": {"state": "known", "text": price} if price else {"state": "not_stated"},
                    "ingredients": [], "statements": [],
                    "dish_type": {"id": None, "confidence": "unmapped", "rationale": "", "status": "proposed"},
                    "_desc_lines": [(i + 1, rest)] if rest else [],
                }
                k += 1
                items.append(current)
                for kw, dt, pat in dts:
                    if pat.search(name):
                        current["dish_type"] = {"id": dt, "confidence": "likely", "rationale": f"name matches {kw!r}", "status": "proposed"}
                        break
                for w in _warnings(ln):
                    current["statements"].append({"kind": "warning", "text": w, "quote": ln, "lines": [i + 1, i + 1]})
                continue
            if lab[i] == "price":
                continue
            # 'other' line: description continuation, warning, or restaurant fact
            is_fact = False
            if (WEEKDAYS.search(ln) or "hours" in ln.lower()) and TIME.search(ln):
                facts.append({"field": "hours", "state": "known", "values": [{"capture_id": cid, "value": ln, "quote": ln}]})
                is_fact = True
            elif ADDRESS.search(ln) and "address" not in seen_fact:
                seen_fact.add("address")
                facts.append({"field": "address", "state": "known", "values": [{"capture_id": cid, "value": ADDRESS.search(ln).group(0), "quote": ln}]})
                is_fact = True
            if is_fact:
                current = None
                continue
            w = _warnings(ln)
            if current is not None:
                current["_desc_lines"].append((i + 1, ln))
                for x in w:
                    current["statements"].append({"kind": "warning", "text": x, "quote": ln, "lines": [i + 1, i + 1]})
            elif w:
                menu_statements.append({"capture_id": cid, "kind": "warning", "text": ", ".join(w), "quote": ln, "lines": [i + 1, i + 1]})
    for it in items:
        dl = it.pop("_desc_lines")
        if dl:
            it["description"] = {"state": "known", "text": " ".join(t for _, t in dl), "lines": [dl[0][0], dl[-1][0]]}
            for ln_no, t in dl:
                for term, got in _match_ingredients(t):
                    it["ingredients"].append({"name": term, "quote": t, "lines": [ln_no, ln_no]})
    # merge multiple hours lines into one fact (several lines = one schedule)
    hours = [f for f in facts if f["field"] == "hours"]
    if len(hours) > 1:
        facts = [f for f in facts if f["field"] != "hours"] + [{"field": "hours", "state": "known",
                 "values": [v for f in hours for v in f["values"]]}]
    return {
        "format": DRAFT_FORMAT, "restaurant_id": cs.restaurant_id, "system": "baseline", "system_version": VERSION,
        "run": {}, "captures": {cid: {"url": c.url, "sha256": c.sha256, "retrieved_at": c.retrieved_at} for cid, c in cs.captures.items()},
        "captures_read": list(cs.captures), "items": items, "menu_statements": menu_statements,
        "restaurant_facts": facts, "problems": problems, "finished": None, "refusals": 0,
    }

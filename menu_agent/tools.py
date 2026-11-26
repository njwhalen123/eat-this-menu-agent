"""The agent's tools, and the code checks behind them.

Every tool works on one restaurant's saved pages; nothing is fetched live.
A recording tool refuses anything whose quote is not in the page, and an
ingredient that isn't named in its own quote, so a draft can't contain a
claim the source doesn't make (CATALOG-EXPANSION §3.1 (3), §5.3).
"""
from __future__ import annotations

import json
from typing import Any

from .captures import CaptureSet
from .dictionary import dish_type_ids
from .text import key, named_in, normalize

DRAFT_FORMAT = "menu-agent-draft/0"
DEFAULT_RETRIEVAL_CAP = 12  # Nick, 2026-11-25: every linked menu page, up to 12
PAGE_LINES = 400

STATEMENT_KINDS = ["warning", "dietary_label", "option", "qualifier", "other"]
CONFIDENCE = ["clear", "likely", "ambiguous", "untypeable", "unmapped"]
PROBLEM_KINDS = ["did_not_render", "image_only", "cut_off", "orphan_price", "missing_page",
                 "conflict", "unclear_structure", "other"]
FACT_FIELDS = ["hours", "address", "phone", "price_note"]


def _quoted(q: dict) -> dict:
    return {"type": "object", "properties": q, "required": list(q)}


QUOTE = {"type": "string", "description": "Exact text copied from the capture (whitespace may differ)."}

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "list_captures",
        "description": "List this restaurant's saved pages: capture ID, address, kind, title, length, images (not readable) and links between pages.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_capture",
        "description": f"Read a saved page as numbered lines. Opening a page counts toward the retrieval cap. Returns at most {PAGE_LINES} lines per call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "capture_id": {"type": "string"},
                "from_line": {"type": "integer", "minimum": 1},
                "to_line": {"type": "integer", "minimum": 1},
            },
            "required": ["capture_id"],
        },
    },
    {
        "name": "search_capture",
        "description": "Find the lines of a page that contain a phrase (case-insensitive). The page must already be open.",
        "input_schema": {
            "type": "object",
            "properties": {"capture_id": {"type": "string"}, "text": {"type": "string"}},
            "required": ["capture_id", "text"],
        },
    },
    {
        "name": "record_items",
        "description": (
            "Record one or more dishes. Each one is checked separately: a dish whose quotes are not in the page, "
            "or whose ingredient is not named in its own quote, is refused with a reason and nothing about it is "
            "stored. Use state 'not_stated' when the page gives no description or no price."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "capture_id": {"type": "string"},
                            "section_path": {"type": "array", "items": {"type": "string"},
                                             "description": "Headings as written, outermost first."},
                            "name": {"type": "string", "description": "The dish name exactly as written."},
                            "description": {
                                "type": "object",
                                "properties": {"state": {"type": "string", "enum": ["known", "not_stated"]}, "quote": QUOTE},
                                "required": ["state"],
                            },
                            "price": {
                                "type": "object",
                                "properties": {"state": {"type": "string", "enum": ["known", "not_stated"]}, "quote": QUOTE},
                                "required": ["state"],
                            },
                            "ingredients": {
                                "type": "array",
                                "items": _quoted({"name": {"type": "string", "description": "As the page names it."}, "quote": QUOTE}),
                            },
                            "statements": {
                                "type": "array",
                                "description": "What the page itself says about this dish: warnings, dietary labels, options, qualifiers such as 'GF bun available'.",
                                "items": _quoted({"kind": {"type": "string", "enum": STATEMENT_KINDS},
                                                  "text": {"type": "string"}, "quote": QUOTE}),
                            },
                            "dish_type": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": ["string", "null"]},
                                    "confidence": {"type": "string", "enum": CONFIDENCE},
                                    "rationale": {"type": "string"},
                                },
                                "required": ["id", "confidence", "rationale"],
                            },
                        },
                        "required": ["capture_id", "section_path", "name", "description", "price",
                                     "ingredients", "statements", "dish_type"],
                    },
                }
            },
            "required": ["items"],
        },
    },
    {
        "name": "delete_item",
        "description": "Remove a dish you recorded by mistake (for example a duplicate).",
        "input_schema": {"type": "object", "properties": {"item_key": {"type": "string"}}, "required": ["item_key"]},
    },
    {
        "name": "record_menu_statement",
        "description": "Record a statement that applies to the whole menu or a whole section, such as an allergy notice or a raw-food warning.",
        "input_schema": {
            "type": "object",
            "properties": {"capture_id": {"type": "string"}, "kind": {"type": "string", "enum": STATEMENT_KINDS},
                           "text": {"type": "string"}, "quote": QUOTE},
            "required": ["capture_id", "kind", "text", "quote"],
        },
    },
    {
        "name": "record_restaurant_fact",
        "description": "Record hours, address, phone or a price note, only where the page plainly states it. State 'conflicting' needs two or more values, each quoted; never choose between them.",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": FACT_FIELDS},
                "state": {"type": "string", "enum": ["known", "unknown", "conflicting"]},
                "values": {"type": "array", "items": _quoted({"capture_id": {"type": "string"}, "value": {"type": "string"}, "quote": QUOTE})},
            },
            "required": ["field", "state", "values"],
        },
    },
    {
        "name": "record_problem",
        "description": "Record missing information or an extraction problem: a section that didn't render, an image-only menu, a cut-off line, a price with no dish, a linked page that wasn't saved.",
        "input_schema": {
            "type": "object",
            "properties": {"kind": {"type": "string", "enum": PROBLEM_KINDS}, "capture_id": {"type": "string"},
                           "where": {"type": "string"}, "note": {"type": "string"}},
            "required": ["kind", "note"],
        },
    },
    {
        "name": "finish",
        "description": "End the run. List every section heading you saw and how many dish lines you counted, so the code can compare them with what you recorded.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sections_seen": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                "dish_lines_seen": {"type": "integer"},
                "notes": {"type": "string"},
            },
            "required": ["sections_seen", "dish_lines_seen"],
        },
    },
]


class ToolSession:
    def __init__(self, cs: CaptureSet, retrieval_cap: int = DEFAULT_RETRIEVAL_CAP):
        self.cs = cs
        self.cap = retrieval_cap
        self.opened: list[str] = []
        self.items: list[dict] = []
        self.menu_statements: list[dict] = []
        self.facts: list[dict] = []
        self.problems: list[dict] = []
        self.finished: dict | None = None
        self.refusals = 0
        self._next = 1
        self.dt_ids = dish_type_ids()

    # ---------- dispatch ----------
    def call(self, name: str, args: dict) -> tuple[str, bool]:
        """Returns (result text, is_error)."""
        fn = getattr(self, "t_" + name, None)
        if fn is None:
            return f"Unknown tool {name}.", True
        try:
            out = fn(**(args or {}))
        except TypeError as e:
            return f"Bad arguments for {name}: {e}", True
        if isinstance(out, tuple):
            return out
        return out, False

    # ---------- helpers ----------
    def _cap(self, cid: str):
        c = self.cs.captures.get(cid)
        if c is None:
            raise KeyError(cid)
        return c

    def _span(self, cid: str, quote: str | None):
        if not quote or not normalize(quote):
            return None, "empty quote"
        sp = self._cap(cid).search.find(quote)
        if sp is None:
            return None, f"quote not found in {cid}: {quote[:80]!r}"
        return sp, None

    def _require_open(self, cid: str) -> str | None:
        if cid not in self.cs.captures:
            return f"No capture {cid}."
        if cid not in self.opened:
            return f"Open {cid} with read_capture first."
        return None

    # ---------- reading ----------
    def t_list_captures(self):
        by_url = self.cs.by_url()
        out = {"restaurant_id": self.cs.restaurant_id, "menu_scope": self.cs.menu_scope,
               "retrieval_cap": self.cap, "opened": self.opened, "captures": []}
        for cid, c in self.cs.captures.items():
            links = []
            for ln in c.ex.links:
                target = by_url.get(ln["url"].rstrip("/"))
                links.append({"text": ln["text"], "url": ln["url"], "saved_as": target})
            out["captures"].append({
                "capture_id": cid, "url": c.url, "kind": c.kind, "role": c.role, "title": c.ex.title,
                "lines": len(c.lines), "pdf_pages": c.ex.pages if c.kind == "pdf" else None,
                "pdf_pages_without_text": c.ex.pages_without_text or None,
                "images_not_read": [{"file": i["src"].rsplit("/", 1)[-1], "alt": i["alt"]} for i in c.ex.images],
                "links": links,
            })
        return json.dumps(out, indent=1)

    def t_read_capture(self, capture_id: str, from_line: int = 1, to_line: int | None = None):
        if capture_id not in self.cs.captures:
            return f"No capture {capture_id}.", True
        if capture_id not in self.opened:
            if len(self.opened) >= self.cap:
                return f"Retrieval cap reached ({self.cap} pages). Record the rest as a problem.", True
            self.opened.append(capture_id)
        c = self._cap(capture_id)
        n = len(c.lines)
        a = max(1, from_line)
        b = min(n, to_line or (a + PAGE_LINES - 1), a + PAGE_LINES - 1)
        head = f"{capture_id} {c.url} ({c.kind}) lines {a}-{b} of {n}"
        if n == 0:
            head += " — NO TEXT EXTRACTED"
        if c.ex.images:
            head += f"; {len(c.ex.images)} image(s) not read"
        body = "\n".join(f"{c.line_label(i)} | {c.lines[i - 1]}" for i in range(a, b + 1))
        more = f"\n… {n - b} more lines; call again with from_line={b + 1}." if b < n else ""
        return head + "\n" + body + more

    def t_search_capture(self, capture_id: str, text: str):
        err = self._require_open(capture_id)
        if err:
            return err, True
        c = self._cap(capture_id)
        t = normalize(text).lower()
        hits = [f"{c.line_label(i)} | {ln}" for i, ln in enumerate(c.lines, 1) if t in normalize(ln).lower()]
        return "\n".join(hits[:60]) or "No lines match."

    # ---------- recording ----------
    def _check_item(self, it: dict) -> tuple[dict | None, list[str]]:
        errs: list[str] = []
        cid = it.get("capture_id", "")
        e = self._require_open(cid)
        if e:
            return None, [e]
        rec: dict = {"capture_id": cid}
        # section headings must be on the page
        path = [s for s in it.get("section_path", []) if normalize(s)]
        for h in path:
            if self._cap(cid).search.find(h) is None:
                errs.append(f"section heading not found in {cid}: {h!r}")
        rec["section_path"] = [self._cap(cid).search.find(h).text if self._cap(cid).search.find(h) else h for h in path]
        # name
        name = it.get("name", "")
        sp, e = self._span(cid, name)
        if e:
            errs.append("name: " + e)
        else:
            rec["name"] = {"text": sp.text, "line": sp.start_line}
        # description and price
        for fld in ("description", "price"):
            d = it.get(fld) or {}
            st = d.get("state")
            if st == "known":
                sp, e = self._span(cid, d.get("quote"))
                if e:
                    errs.append(f"{fld}: " + e)
                else:
                    rec[fld] = {"state": "known", "text": sp.text, "lines": [sp.start_line, sp.end_line]}
            elif st == "not_stated":
                rec[fld] = {"state": "not_stated"}
            else:
                errs.append(f"{fld}: state must be 'known' or 'not_stated'")
        # ingredients
        rec["ingredients"] = []
        for ing in it.get("ingredients", []):
            sp, e = self._span(cid, ing.get("quote"))
            if e:
                errs.append(f"ingredient {ing.get('name')!r}: " + e)
            elif not named_in(ing.get("name", ""), sp.text):
                errs.append(f"ingredient {ing.get('name')!r} is not named in its quote {sp.text!r}")
            else:
                rec["ingredients"].append({"name": ing["name"], "quote": sp.text, "lines": [sp.start_line, sp.end_line]})
        # statements
        rec["statements"] = []
        for s in it.get("statements", []):
            sp, e = self._span(cid, s.get("quote"))
            if e:
                errs.append(f"statement {s.get('text')!r}: " + e)
            elif s.get("kind") not in STATEMENT_KINDS:
                errs.append(f"statement kind must be one of {STATEMENT_KINDS}")
            else:
                rec["statements"].append({"kind": s["kind"], "text": s.get("text", ""), "quote": sp.text,
                                          "lines": [sp.start_line, sp.end_line]})
        # dish type proposal
        dt = it.get("dish_type") or {}
        dt_id = dt.get("id")
        conf = dt.get("confidence")
        if dt_id is not None and dt_id not in self.dt_ids:
            errs.append(f"dish_type {dt_id!r} is not in the dictionary (use null and 'unmapped')")
        if conf not in CONFIDENCE:
            errs.append(f"dish_type confidence must be one of {CONFIDENCE}")
        if dt_id is None and conf in ("clear", "likely"):
            errs.append("a 'clear' or 'likely' confidence needs a dish type id")
        rec["dish_type"] = {"id": dt_id, "confidence": conf, "rationale": dt.get("rationale", ""), "status": "proposed"}
        # duplicate guard
        if not errs:
            k = (cid, key(" > ".join(rec["section_path"])), key(rec["name"]["text"]))
            for old in self.items:
                if (old["capture_id"], key(" > ".join(old["section_path"])), key(old["name"]["text"])) == k:
                    errs.append(f"already recorded as {old['item_key']} (delete it first to replace it)")
        return (None if errs else rec), errs

    def t_record_items(self, items: list):
        results = []
        for i, it in enumerate(items):
            rec, errs = self._check_item(it if isinstance(it, dict) else {})
            if rec is None:
                self.refusals += 1
                results.append({"index": i, "recorded": False, "errors": errs})
            else:
                rec["item_key"] = f"I{self._next:03d}"
                self._next += 1
                self.items.append(rec)
                results.append({"index": i, "recorded": True, "item_key": rec["item_key"]})
        bad = sum(1 for r in results if not r["recorded"])
        return json.dumps({"recorded": len(results) - bad, "refused": bad, "results": results}), False

    def t_delete_item(self, item_key: str):
        before = len(self.items)
        self.items = [x for x in self.items if x["item_key"] != item_key]
        return ("Deleted." if len(self.items) < before else f"No item {item_key}."), len(self.items) == before

    def t_record_menu_statement(self, capture_id: str, kind: str, text: str, quote: str):
        e = self._require_open(capture_id)
        if e:
            return e, True
        sp, e = self._span(capture_id, quote)
        if e:
            self.refusals += 1
            return e, True
        if kind not in STATEMENT_KINDS:
            return f"kind must be one of {STATEMENT_KINDS}", True
        self.menu_statements.append({"capture_id": capture_id, "kind": kind, "text": text, "quote": sp.text,
                                     "lines": [sp.start_line, sp.end_line]})
        return "Recorded."

    def t_record_restaurant_fact(self, field: str, state: str, values: list):
        if field not in FACT_FIELDS:
            return f"field must be one of {FACT_FIELDS}", True
        if state == "conflicting" and len(values) < 2:
            return "'conflicting' needs at least two quoted values.", True
        if state == "unknown" and values:
            return "'unknown' takes no values.", True
        if state == "known" and len(values) != 1:
            return "'known' takes exactly one value; use 'conflicting' for more.", True
        out = []
        for v in values:
            e = self._require_open(v.get("capture_id", ""))
            if e:
                return e, True
            sp, e = self._span(v["capture_id"], v.get("quote"))
            if e:
                self.refusals += 1
                return e, True
            out.append({"capture_id": v["capture_id"], "value": v.get("value", ""), "quote": sp.text})
        self.facts = [f for f in self.facts if f["field"] != field]
        self.facts.append({"field": field, "state": state, "values": out})
        return "Recorded."

    def t_record_problem(self, kind: str, note: str, capture_id: str = "", where: str = ""):
        if kind not in PROBLEM_KINDS:
            return f"kind must be one of {PROBLEM_KINDS}", True
        self.problems.append({"kind": kind, "capture_id": capture_id, "where": where, "note": note, "by": "agent"})
        return "Recorded."

    def t_finish(self, sections_seen: list, dish_lines_seen: int, notes: str = ""):
        used = {key(" > ".join(x["section_path"])) for x in self.items}
        used_heads = {key(h) for x in self.items for h in x["section_path"]}
        for s in sections_seen:
            path = s if isinstance(s, list) else [s]
            if key(" > ".join(path)) not in used and not (path and key(path[-1]) in used_heads):
                self.problems.append({"kind": "other", "capture_id": "", "where": " > ".join(path),
                                      "note": "section seen but no dish recorded under it", "by": "code"})
        if dish_lines_seen != len(self.items):
            self.problems.append({"kind": "other", "capture_id": "", "where": "",
                                  "note": f"agent counted {dish_lines_seen} dish lines but recorded {len(self.items)}",
                                  "by": "code"})
        for cid, c in self.cs.captures.items():
            if cid not in self.opened and "out of scope" not in c.role:
                self.problems.append({"kind": "missing_page", "capture_id": cid, "where": c.url,
                                      "note": "saved page never opened", "by": "code"})
        self.finished = {"sections_seen": sections_seen, "dish_lines_seen": dish_lines_seen, "notes": notes}
        return f"Finished: {len(self.items)} dishes, {len(self.problems)} problems."

    # ---------- output ----------
    def draft(self, system: str, system_version: str, run: dict) -> dict:
        return {
            "format": DRAFT_FORMAT,
            "restaurant_id": self.cs.restaurant_id,
            "system": system,
            "system_version": system_version,
            "run": run,
            "captures": {cid: {"url": c.url, "sha256": c.sha256, "retrieved_at": c.retrieved_at}
                         for cid, c in self.cs.captures.items()},
            "captures_read": list(self.opened),
            "items": self.items,
            "menu_statements": self.menu_statements,
            "restaurant_facts": self.facts,
            "problems": self.problems,
            "finished": self.finished,
            "refusals": self.refusals,
        }

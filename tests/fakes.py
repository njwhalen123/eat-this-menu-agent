"""A scripted stand-in for the Claude API, so the loop runs with no key and no cost."""
import itertools
import json
import os

from conftest import PRACTICE

_ids = itertools.count(1)


def tool_use(name, inp):
    return {"type": "tool_use", "id": f"toolu_{next(_ids)}", "name": name, "input": inp}


def response(blocks, stop="tool_use", usage=None):
    return {"id": f"msg_{next(_ids)}", "content": blocks, "stop_reason": stop,
            "usage": usage or {"input_tokens": 1000, "output_tokens": 500,
                               "cache_creation_input_tokens": 0, "cache_read_input_tokens": 4000}}


class ScriptedClient:
    """Returns the scripted responses in order; records what it was sent."""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []
        self.messages = self

    def create(self, **kw):
        self.sent.append(json.loads(json.dumps(kw)))
        return self.script.pop(0) if self.script else response([{"type": "text", "text": "done"}], stop="end_turn")


def oracle_script(rid):
    """The tool calls a perfect agent would make, built from the practice answer key."""
    import menu_agent.captures as captures
    root = os.path.join(PRACTICE, rid)
    cs = captures.load(root)
    ref = json.load(open(os.path.join(root, "reference.json")))
    in_scope = [cid for cid, c in cs.captures.items() if "out of scope" not in c.role]
    script = [response([tool_use("list_captures", {})])]
    script.append(response([tool_use("read_capture", {"capture_id": cid}) for cid in in_scope]))

    def where(text):
        return next(cid for cid in in_scope if cs.captures[cid].search.find(text))

    items = []
    for r in ref["items"]:
        cid = where(r["name"])
        items.append({
            "capture_id": cid, "section_path": r["section"].split(" > "), "name": r["name"],
            "description": {"state": "known", "quote": r["description"]} if r["description"] else {"state": "not_stated"},
            "price": {"state": "known", "quote": r["price"]} if r["price"] else {"state": "not_stated"},
            "ingredients": [{"name": i, "quote": r["description"]} for i in r["ingredients"]],
            "statements": [{"kind": s["kind"], "text": s["text"], "quote": s["text"]} for s in r["statements"]],
            "dish_type": {"id": r["dish_type"], "confidence": "clear" if r["dish_type"] else "unmapped", "rationale": "x"},
        })
    script.append(response([tool_use("record_items", {"items": items})]))
    blocks = [tool_use("record_menu_statement", {"capture_id": where(t), "kind": "warning", "text": t, "quote": t})
              for t in ref["menu_statements"]]
    for fld, v in ref["restaurant_facts"].items():
        if v:
            blocks.append(tool_use("record_restaurant_fact", {"field": fld, "state": "known",
                                                              "values": [{"capture_id": where(v), "value": v, "quote": v}]}))
    for p in ref["problems"]:
        blocks.append(tool_use("record_problem", {"kind": p["kind"], "where": p["where"], "note": "practice"}))
    script.append(response(blocks))
    sections = sorted({tuple(r["section"].split(" > ")) for r in ref["items"]})
    script.append(response([tool_use("finish", {"sections_seen": [list(s) for s in sections],
                                                "dish_lines_seen": len(ref["items"])})]))
    return cs, ref, script

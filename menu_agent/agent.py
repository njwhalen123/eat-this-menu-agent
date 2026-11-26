"""The agent loop: one restaurant, one model, tools over saved pages only.

Spending is guarded twice:
  - before a run starts, the shared ledger's total plus this run's ceiling must
    stay under the budget (default $17, under the ~$19.77 prepaid credit);
  - during a run, it stops when the run's own cost passes its ceiling.
The ledger is updated after every API call, so an interrupted run still counts.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import time

from .captures import CaptureSet
from .dictionary import dictionary_text
from .pricing import CONFIRMED_ON, PRICES, request_cost
from .tools import TOOL_SPECS, ToolSession

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_VERSION = "agent_v0"
MAX_TOKENS = 16000
READ_TOOLS = {"list_captures", "read_capture", "search_capture"}


class BudgetError(Exception):
    pass


def system_prompt(version: str = PROMPT_VERSION) -> str:
    with open(os.path.join(ROOT, "prompts", f"{version}.md"), encoding="utf-8") as f:
        return f.read().replace("{dictionary}", dictionary_text())


def code_commit() -> str:
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ---------------- ledger ----------------

def _load_ledger(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"runs": [], "total_usd": 0.0}


def _save_ledger(path: str, led: dict) -> None:
    led["total_usd"] = round(sum(r["usd"] for r in led["runs"]), 6)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(led, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


# ---------------- message helpers ----------------

def _block_dict(b) -> dict:
    if isinstance(b, dict):
        return b
    if hasattr(b, "model_dump"):
        return b.model_dump(mode="json", exclude_none=True)
    return dict(vars(b))


def _get(o, name, default=None):
    return o.get(name, default) if isinstance(o, dict) else getattr(o, name, default)


def _usage_dict(u) -> dict:
    keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    return {k: int(_get(u, k, 0) or 0) for k in keys}


def _mark_cache(messages: list) -> None:
    """Cache breakpoint on the last block of the last message only."""
    for m in messages:
        if isinstance(m["content"], list):
            for b in m["content"]:
                b.pop("cache_control", None)
    last = messages[-1]["content"]
    if isinstance(last, list) and last:
        last[-1]["cache_control"] = {"type": "ephemeral"}


def _tools_payload() -> list:
    tools = json.loads(json.dumps(TOOL_SPECS))
    tools[-1]["cache_control"] = {"type": "ephemeral"}
    return tools


# ---------------- the run ----------------

def run_agent(cs: CaptureSet, model: str, ledger_path: str, budget: float = 17.0, run_ceiling: float = 3.0,
              max_turns: int = 60, retrieval_cap: int = 12, client=None, prompt_version: str = PROMPT_VERSION) -> dict:
    if model not in PRICES:
        raise ValueError(f"no confirmed price for {model}; add it to pricing.py first")
    led = _load_ledger(ledger_path)
    if led["total_usd"] + run_ceiling > budget:
        raise BudgetError(f"spent ${led['total_usd']:.2f}; another run (ceiling ${run_ceiling:.2f}) "
                          f"could pass the ${budget:.2f} budget")
    if client is None:
        import anthropic  # imported here so tests and the baseline need no key
        client = anthropic.Anthropic(max_retries=4)

    sysp = system_prompt(prompt_version)
    run_id = f"{cs.restaurant_id}-{model}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    entry = {"run_id": run_id, "restaurant_id": cs.restaurant_id, "model": model, "usd": 0.0,
             "started": _now(), "ended": None}
    led["runs"].append(entry)
    _save_ledger(ledger_path, led)

    tools = ToolSession(cs, retrieval_cap=retrieval_cap)
    messages = [{"role": "user", "content": [{"type": "text", "text": (
        f"Restaurant {cs.restaurant_id}. Menu scope: {cs.menu_scope or 'the whole menu'}. "
        "Build the draft record from its saved pages, then call finish.")}]}]
    calls, tool_log = [], []
    usd = 0.0
    model_s = read_s = 0.0
    nudges = 0
    stop = "max_turns"
    for turn in range(max_turns):
        _mark_cache(messages)
        t0 = time.monotonic()
        resp = client.messages.create(model=model, max_tokens=MAX_TOKENS,
                                      system=[{"type": "text", "text": sysp, "cache_control": {"type": "ephemeral"}}],
                                      tools=_tools_payload(), messages=messages)
        secs = time.monotonic() - t0
        model_s += secs
        usage = _usage_dict(_get(resp, "usage", {}))
        cost = request_cost(model, usage)
        usd += cost
        calls.append({"turn": turn, "request_id": _get(resp, "_request_id") or _get(resp, "id"),
                      "stop_reason": _get(resp, "stop_reason"), "usage": usage, "usd": round(cost, 6),
                      "seconds": round(secs, 2)})
        entry["usd"] = round(usd, 6)
        _save_ledger(ledger_path, led)

        content = [_block_dict(b) for b in (_get(resp, "content") or [])]
        messages.append({"role": "assistant", "content": content})
        uses = [b for b in content if b.get("type") == "tool_use"]
        reason = _get(resp, "stop_reason")
        if uses:
            results = []
            for u in uses:
                t1 = time.monotonic()
                text, is_err = tools.call(u["name"], u.get("input") or {})
                if u["name"] in READ_TOOLS:
                    read_s += time.monotonic() - t1
                tool_log.append({"turn": turn, "tool": u["name"], "error": is_err,
                                 "capture_id": (u.get("input") or {}).get("capture_id")})
                results.append({"type": "tool_result", "tool_use_id": u["id"], "content": text, "is_error": is_err})
            messages.append({"role": "user", "content": results})
            if tools.finished is not None:
                stop = "finished"
                break
        elif reason == "refusal":
            stop = "refusal"
            tools.problems.append({"kind": "other", "capture_id": "", "where": "", "note": "the model declined", "by": "code"})
            break
        else:
            if nudges >= 2:
                stop = "no_finish"
                break
            nudges += 1
            note = ("Your reply was cut off. Record fewer dishes per call." if reason == "max_tokens"
                    else "Continue with the tools. When every in-scope dish is recorded, call finish.")
            messages.append({"role": "user", "content": [{"type": "text", "text": note}]})
        if usd > run_ceiling:
            stop = "run_ceiling"
            tools.problems.append({"kind": "other", "capture_id": "", "where": "",
                                   "note": f"stopped at the run ceiling (${run_ceiling:.2f}); draft is incomplete", "by": "code"})
            break

    entry["ended"] = _now()
    _save_ledger(ledger_path, led)
    totals = {k: sum(c["usage"][k] for c in calls) for k in calls[0]["usage"]} if calls else {}
    run = {
        "run_id": run_id, "model": model, "prompt_version": prompt_version,
        "prompt_sha256": hashlib.sha256(sysp.encode()).hexdigest(), "code_commit": code_commit(),
        "retrieval_cap": retrieval_cap, "started": entry["started"], "ended": entry["ended"], "stop": stop,
        "turns": len(calls), "calls": calls, "tool_log": tool_log,
        "seconds": {"model": round(model_s, 2), "reading_pages": round(read_s, 3)},
        "cost": {"usd": round(usd, 6), "tokens": totals, "prices": PRICES[model], "prices_confirmed_on": CONFIRMED_ON},
        "tool_errors": sum(1 for t in tool_log if t["error"]),
    }
    return tools.draft("agent", f"{prompt_version}+{model}", run)

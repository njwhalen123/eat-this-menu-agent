from __future__ import annotations

import argparse
import json
import os
import sys

from . import baseline, captures, score


def _write(obj, path):
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.write("\n")
    else:
        json.dump(obj, sys.stdout, indent=2, ensure_ascii=False)
        print()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="run.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baseline", help="run the keyword baseline on one restaurant folder")
    b.add_argument("restaurant"); b.add_argument("-o", "--out")
    s = sub.add_parser("score", help="score a draft against a reference")
    s.add_argument("draft"); s.add_argument("restaurant")
    s.add_argument("--reference", help="default: <restaurant>/reference.json")
    s.add_argument("--adjudication"); s.add_argument("-o", "--out")
    c = sub.add_parser("check-reference", help="check that every reference fact is on its page")
    c.add_argument("restaurant"); c.add_argument("--reference")
    a = sub.add_parser("agent", help="run the agent (paid API calls)")
    a.add_argument("restaurant"); a.add_argument("-o", "--out", required=True)
    a.add_argument("--model", default="claude-sonnet-5-5")
    a.add_argument("--ledger", required=True, help="spend ledger JSON shared by all runs")
    a.add_argument("--budget", type=float, default=17.0, help="refuse to start past this total spend (USD)")
    a.add_argument("--run-ceiling", type=float, default=3.0, help="stop a run past this cost (USD)")
    a.add_argument("--max-turns", type=int, default=60)
    a.add_argument("--retrieval-cap", type=int, default=12)
    args = ap.parse_args(argv)

    if args.cmd == "baseline":
        cs = captures.load(args.restaurant)
        _write(baseline.run(cs), args.out)
    elif args.cmd == "score":
        cs = captures.load(args.restaurant)
        with open(args.draft, encoding="utf-8") as f:
            draft = json.load(f)
        with open(args.reference or os.path.join(args.restaurant, "reference.json"), encoding="utf-8") as f:
            ref = json.load(f)
        adj = None
        if args.adjudication:
            with open(args.adjudication, encoding="utf-8") as f:
                adj = json.load(f)
        res = score.score(draft, ref, cs, adj)
        print(score.summary_md(res), file=sys.stderr)
        _write(res, args.out)
    elif args.cmd == "check-reference":
        from .reference_check import check
        cs = captures.load(args.restaurant)
        with open(args.reference or os.path.join(args.restaurant, "reference.json"), encoding="utf-8") as f:
            ref = json.load(f)
        errs = check(ref, cs)
        for e in errs:
            print(e)
        print(f"{len(errs)} problem(s)", file=sys.stderr)
        return 1 if errs else 0
    elif args.cmd == "agent":
        from .agent import run_agent
        cs = captures.load(args.restaurant)
        draft = run_agent(cs, model=args.model, ledger_path=args.ledger, budget=args.budget,
                          run_ceiling=args.run_ceiling, max_turns=args.max_turns, retrieval_cap=args.retrieval_cap)
        _write(draft, args.out)
        print(json.dumps(draft["run"]["cost"]), file=sys.stderr)
    return 0

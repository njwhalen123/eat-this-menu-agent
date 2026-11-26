"""Scores a draft against a reference (method §2–§3).

Automatic parts: matching, M1, M2, M3(a), M4, M5, M6, M7, M9.
Human parts are written to a review sheet and read back when filled in:
  - near matches (same dish / split / merged / different),
  - M3(b), whether each sampled quote supports its claim,
  - the adjudication of disagreements (system error / reference error / source ambiguous).
Until the sheet is filled in, near matches count as provisional matches and
the summary says so.
"""
from __future__ import annotations

import difflib
import json
import random
import re

from .captures import CaptureSet
from .text import key, normalize, words

SAMPLE_SEED = 2026
SAMPLE_OTHER = 30


def _path(p) -> str:
    return key(" > ".join(p) if isinstance(p, list) else (p or ""))


def _price(p: str | None) -> str:
    if p is None:
        return ""
    p = normalize(p).lower().replace("$", "").strip()
    return re.sub(r"\.00$", "", p)


def ing_match(a: str, b: str) -> bool:
    """Ingredients match when one name's words appear contiguously in the other's
    ('roasted beets' ~ 'beets'), after lower-casing and simple singular forms."""
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return False
    short, long_ = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    return any(long_[i:i + len(short)] == short for i in range(len(long_) - len(short) + 1))


def _similar(a: str, b: str) -> bool:
    ka, kb = key(a), key(b)
    if not ka or not kb:
        return False
    if ka in kb or kb in ka:
        return True
    return difflib.SequenceMatcher(None, ka, kb).ratio() >= 0.85


def _stmt_found(ref_text: str, sys_stmts: list[dict]) -> bool:
    r = normalize(ref_text).lower().rstrip(".")
    for s in sys_stmts:
        hay = normalize((s.get("quote") or "") + " " + (s.get("text") or "")).lower()
        if r and r in hay:
            return True
    return False


def match(draft: dict, ref: dict, adjudication: dict | None = None):
    adj = (adjudication or {}).get("near_matches", {})
    sys_items = draft["items"]
    used: set[int] = set()
    pairs: dict[int, tuple[int, str]] = {}  # ref index -> (sys index, how)
    # pass 1: exact name + section; pass 2: exact name, other section
    for exact_section in (True, False):
        for ri, r in enumerate(ref["items"]):
            if ri in pairs:
                continue
            for si, s in enumerate(sys_items):
                if si in used or key(s["name"]["text"]) != key(r["name"]):
                    continue
                if exact_section and _path(s["section_path"]) != _path(r["section"]):
                    continue
                pairs[ri] = (si, "exact" if exact_section else "section_differs")
                used.add(si)
                break
    # pass 3: near matches, same section preferred
    near = []
    for ri, r in enumerate(ref["items"]):
        if ri in pairs:
            continue
        cands = [si for si, s in enumerate(sys_items) if si not in used and _similar(s["name"]["text"], r["name"])]
        cands.sort(key=lambda si: (_path(sys_items[si]["section_path"]) != _path(r["section"]),
                                   -difflib.SequenceMatcher(None, key(sys_items[si]["name"]["text"]), key(r["name"])).ratio()))
        if cands:
            si = cands[0]
            nid = f"{ri}:{si}"
            label = adj.get(nid, "provisional")
            near.append({"id": nid, "reference": r["name"], "system": sys_items[si]["name"]["text"], "label": label})
            if label in ("provisional", "same dish"):
                pairs[ri] = (si, "near_" + label.replace(" ", "_"))
                used.add(si)
    return pairs, used, near


def score(draft: dict, ref: dict, cs: CaptureSet, adjudication: dict | None = None) -> dict:
    pairs, used, near = match(draft, ref, adjudication)
    sys_items = draft["items"]
    out: dict = {"restaurant_id": ref["restaurant_id"], "system": draft["system"],
                 "system_version": draft.get("system_version"), "reference_dishes": len(ref["items"])}

    # ---- M1 coverage
    matched_names = {key(ref["items"][ri]["name"]) for ri in pairs}
    dup = invented = out_scope = extra = 0
    unmatched = []
    for si, s in enumerate(sys_items):
        if si in used:
            continue
        cap = cs.captures.get(s["capture_id"])
        role = cap.role if cap else ""
        found = any(c.search.find(s["name"]["text"]) for c in cs.captures.values())
        if not found:
            invented += 1; kind = "invented"
        elif "out of scope" in role:
            out_scope += 1; kind = "out of scope"
        elif key(s["name"]["text"]) in matched_names:
            dup += 1; kind = "duplicate"
        else:
            extra += 1; kind = "in source, not in reference"
        unmatched.append({"system": s["name"]["text"], "section": " > ".join(s["section_path"]), "label": kind})
    split = sum(1 for n in near if n["label"] == "split")
    merged = sum(1 for n in near if n["label"] == "merged")
    out["M1_coverage"] = {"captured": len(pairs), "missed": len(ref["items"]) - len(pairs),
                          "duplicated": dup, "split": split, "merged": merged, "invented": invented,
                          "out_of_scope_excluded": out_scope, "in_source_not_in_reference": extra,
                          "provisional_near_matches": sum(1 for n in near if n["label"] == "provisional"),
                          "rate": round(len(pairs) / max(1, len(ref["items"])), 3)}

    # ---- M2 field accuracy, M4 unknowns, M6 statements, M9 mapping
    f = {k: [0, 0] for k in ("name", "section", "description", "price")}
    qualifier_lost = 0
    tp = fp = fn = 0
    unknown_kept = unknown_total = fabricated = 0
    m6 = {"warnings_and_labels": [0, 0], "other_statements": [0, 0], "missed": []}
    m9 = {"agree": 0, "different": 0, "missed_mapping": 0, "over_mapped": 0, "unmapped_kept_unmapped": 0}
    for ri, r in enumerate(ref["items"]):
        s = sys_items[pairs[ri][0]] if ri in pairs else None
        # statements count whether or not the dish was captured
        for st in r["statements"]:
            bucket = "warnings_and_labels" if st["kind"] in ("warning", "dietary_label") else "other_statements"
            m6[bucket][1] += 1
            if s is not None and _stmt_found(st["text"], s["statements"]):
                m6[bucket][0] += 1
            elif bucket == "warnings_and_labels":
                m6["missed"].append(f"{r['name']}: {st['text']}")
        if s is None:
            continue
        f["name"][1] += 1; f["name"][0] += key(s["name"]["text"]) == key(r["name"])
        f["section"][1] += 1; f["section"][0] += _path(s["section_path"]) == _path(r["section"])
        if r["description"] is None:
            unknown_total += 1
            if s["description"]["state"] == "known":
                fabricated += 1
            else:
                unknown_kept += 1
        else:
            f["description"][1] += 1
            got = s["description"].get("text", "") if s["description"]["state"] == "known" else ""
            ok = normalize(got) == normalize(r["description"])
            f["description"][0] += ok
            if not ok:
                for st in r["statements"]:
                    t = normalize(st["text"]).lower()
                    if t in normalize(r["description"]).lower() and t not in normalize(got).lower():
                        qualifier_lost += 1
        if r["price"] is None:
            unknown_total += 1
            if s["price"]["state"] == "known":
                fabricated += 1
            else:
                unknown_kept += 1
        else:
            f["price"][1] += 1
            got = s["price"].get("text") if s["price"]["state"] == "known" else None
            f["price"][0] += _price(got) == _price(r["price"]) and got is not None
        sys_ings = [i["name"] for i in s["ingredients"]]
        matched_sys = set()
        for ring in r["ingredients"]:
            hit = next((k for k, si in enumerate(sys_ings) if k not in matched_sys and ing_match(ring, si)), None)
            if hit is None:
                fn += 1
            else:
                tp += 1; matched_sys.add(hit)
        fp += len(sys_ings) - len(matched_sys)
        rd, sd = r.get("dish_type"), s["dish_type"].get("id")
        if rd and sd == rd: m9["agree"] += 1
        elif rd and sd: m9["different"] += 1
        elif rd and not sd: m9["missed_mapping"] += 1
        elif not rd and sd: m9["over_mapped"] += 1
        else: m9["unmapped_kept_unmapped"] += 1
    # restaurant facts
    facts = {x["field"]: x for x in draft.get("restaurant_facts", [])}
    f["restaurant_facts"] = [0, 0]
    for fld, val in (ref.get("restaurant_facts") or {}).items():
        sysf = facts.get(fld)
        if val is None:
            unknown_total += 1
            if sysf and sysf["state"] == "known":
                fabricated += 1
            else:
                unknown_kept += 1
            continue
        f["restaurant_facts"][1] += 1
        if sysf and sysf["state"] in ("known", "conflicting"):
            hay = " ".join(normalize(v.get("quote", "") + " " + v.get("value", "")) for v in sysf["values"]).lower()
            f["restaurant_facts"][0] += normalize(val).lower() in hay
    # menu-level statements
    all_sys_stmts = list(draft.get("menu_statements", [])) + [st for it in sys_items for st in it["statements"]]
    m6["menu_statements"] = [sum(_stmt_found(t, all_sys_stmts) for t in ref.get("menu_statements", [])),
                             len(ref.get("menu_statements", []))]
    for t in ref.get("menu_statements", []):
        if not _stmt_found(t, all_sys_stmts):
            m6["missed"].append(f"(menu) {t}")
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    out["M2_field_accuracy"] = {k: {"correct": v[0], "compared": v[1]} for k, v in f.items()}
    out["M2_field_accuracy"]["qualifier_lost"] = qualifier_lost
    out["M2_field_accuracy"]["ingredients"] = {"tp": tp, "fp": fp, "fn": fn, "precision": round(prec, 3),
                                                "recall": round(rec, 3),
                                                "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0}
    out["M4_unknowns"] = {"kept": unknown_kept, "reference_unknowns": unknown_total, "fabricated": fabricated}
    out["M6_statements"] = m6
    out["M9_dish_type"] = m9

    # ---- M3(a) every quote verbatim in its capture
    facts_list = _facts(draft)
    ok = 0
    for fa in facts_list:
        cap = cs.captures.get(fa["capture_id"])
        fa["verbatim"] = bool(cap and fa["quote"] and cap.search.find(fa["quote"]))
        ok += fa["verbatim"]
    out["M3a_verbatim"] = {"verbatim": ok, "facts": len(facts_list)}

    # ---- M5 problems
    sys_probs = " || ".join(key(p.get("where", "") + " " + p.get("note", "") + " " + p.get("kind", ""))
                            for p in draft.get("problems", []))
    ref_probs = ref.get("problems", [])
    flagged = [p for p in ref_probs if key(p["where"]) and key(p["where"]) in sys_probs]
    out["M5_problems"] = {"flagged": len(flagged), "reference_problems": len(ref_probs),
                          "system_problems": len(draft.get("problems", []))}

    # ---- M7 cost
    out["M7_cost"] = draft.get("run", {}).get("cost", {"usd": 0.0})

    # ---- review sheet
    out["review_sheet"] = {"near_matches": near, "unmatched_system_items": unmatched,
                           "m3b_sample": _sample(facts_list)}
    return out


def _facts(draft: dict) -> list[dict]:
    facts = []
    for it in draft["items"]:
        cid = it["capture_id"]
        base = f"{it['item_key']} {it['name']['text']}"
        facts.append({"id": f"{it['item_key']}.name", "kind": "name", "claim": it["name"]["text"],
                      "quote": it["name"]["text"], "capture_id": cid})
        for fld in ("description", "price"):
            if it[fld]["state"] == "known":
                facts.append({"id": f"{it['item_key']}.{fld}", "kind": fld, "claim": f"{base}: {fld}",
                              "quote": it[fld]["text"], "capture_id": cid})
        for k, ing in enumerate(it["ingredients"]):
            facts.append({"id": f"{it['item_key']}.ing{k}", "kind": "ingredient",
                          "claim": f"{base} names {ing['name']}", "quote": ing["quote"], "capture_id": cid})
        for k, st in enumerate(it["statements"]):
            facts.append({"id": f"{it['item_key']}.st{k}", "kind": "statement",
                          "claim": f"{base}: {st['kind']} {st['text']}", "quote": st["quote"], "capture_id": cid})
    for k, st in enumerate(draft.get("menu_statements", [])):
        facts.append({"id": f"menu.st{k}", "kind": "statement", "claim": f"menu: {st['kind']} {st['text']}",
                      "quote": st["quote"], "capture_id": st["capture_id"]})
    for fa in draft.get("restaurant_facts", []):
        for k, v in enumerate(fa["values"]):
            facts.append({"id": f"fact.{fa['field']}{k}", "kind": "restaurant_fact",
                          "claim": f"{fa['field']} = {v['value']}", "quote": v["quote"], "capture_id": v["capture_id"]})
    return facts


def _sample(facts: list[dict]) -> list[dict]:
    always = [f for f in facts if f["kind"] in ("ingredient", "statement", "restaurant_fact")]
    rest = [f for f in facts if f["kind"] not in ("ingredient", "statement", "restaurant_fact")]
    rng = random.Random(SAMPLE_SEED)
    pick = rng.sample(rest, min(SAMPLE_OTHER, len(rest)))
    return [{"id": f["id"], "claim": f["claim"], "quote": f["quote"], "verdict": ""} for f in always + pick]


def summary_md(s: dict) -> str:
    c = s["M1_coverage"]; a = s["M2_field_accuracy"]; u = s["M4_unknowns"]; m6 = s["M6_statements"]
    def fr(x): return f"{x['correct']}/{x['compared']}"
    lines = [
        f"### {s['restaurant_id']} · {s['system']} ({s.get('system_version')})",
        f"- **M1 coverage:** {c['captured']}/{s['reference_dishes']} captured; missed {c['missed']}, duplicated {c['duplicated']}, "
        f"invented {c['invented']}, in source but not in reference {c['in_source_not_in_reference']}, "
        f"out of scope {c['out_of_scope_excluded']}" + (f"; **{c['provisional_near_matches']} provisional near matches**" if c['provisional_near_matches'] else ""),
        f"- **M2 fields:** name {fr(a['name'])}, section {fr(a['section'])}, description {fr(a['description'])} "
        f"(qualifiers lost {a['qualifier_lost']}), price {fr(a['price'])}, restaurant facts {fr(a['restaurant_facts'])}; "
        f"ingredients P {a['ingredients']['precision']} R {a['ingredients']['recall']} F1 {a['ingredients']['f1']} "
        f"(tp {a['ingredients']['tp']}, fp {a['ingredients']['fp']}, fn {a['ingredients']['fn']})",
        f"- **M3a verbatim quotes:** {s['M3a_verbatim']['verbatim']}/{s['M3a_verbatim']['facts']}",
        f"- **M4 unknowns kept:** {u['kept']}/{u['reference_unknowns']}; fabricated {u['fabricated']}",
        f"- **M5 problems flagged:** {s['M5_problems']['flagged']}/{s['M5_problems']['reference_problems']}",
        f"- **M6 warnings and labels:** {m6['warnings_and_labels'][0]}/{m6['warnings_and_labels'][1]}; other statements "
        f"{m6['other_statements'][0]}/{m6['other_statements'][1]}; menu-level {m6['menu_statements'][0]}/{m6['menu_statements'][1]}"
        + (f"; missed: {'; '.join(m6['missed'])}" if m6['missed'] else ""),
        f"- **M7 cost:** ${s['M7_cost'].get('usd', 0):.4f}",
        f"- **M9 dish types:** {json.dumps(s['M9_dish_type'])}",
    ]
    return "\n".join(lines)

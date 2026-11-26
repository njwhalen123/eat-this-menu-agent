# Eat THIS! menu agent (15.071 Project 2)

*Working README, 2026-11-25, written by the AG chat (Claude, Opus 5.5) for Nick Whalen. The one-page project README replaces it before submission on Tue Dec 8.*

**The question:** can an agent help Eat THIS! add restaurant information with less human effort, while keeping its sources and its uncertainty?

**What this repository holds:**
- the agent and a keyword baseline
- the scorer
- a runnable example on four **fictional** practice restaurants

Real restaurants' pages, answer keys and per-restaurant results are kept private.

## What it does

The agent reads one restaurant's **saved** menu pages (it never browses live) and drafts a record: dishes, sections, descriptions, prices, the ingredients the page names, and the page's own warnings and labels. Every fact carries the exact text it came from.

**Code, not the model, enforces the rules:**
- A fact is refused unless its quote is on the page.
- An ingredient is refused unless its own quote names it.
- A missing description or price is recorded as *not stated*.
- Dish types are only *proposed*, from a fixed dictionary, and a person confirms each one.

A person then reviews the draft against the saved page.

**The baseline** is plain text extraction plus keyword rules, with no model. It runs on exactly the same text, so the comparison measures the extraction, not how each one read the page.

## Run the example

```
pip install -r requirements.txt
python3 -m pytest -q                                   # 26 tests, no API key needed
python3 -I run.py check-reference examples/practice/P1 # the answer key is on its page
python3 -I run.py baseline examples/practice/P1 -o runs/P1-baseline.json
python3 -I run.py score runs/P1-baseline.json examples/practice/P1
```

**The agent makes paid API calls.** It reads `ANTHROPIC_API_KEY` from the environment. Never put the key in a file or a chat.

```
python3 -I run.py agent examples/practice/P1 -o runs/P1-agent.json --ledger runs/spend.ledger.json
```

**Spending guards:**
- `--ledger` is a spend record shared by every run. The run refuses to start when the ledger's total plus `--run-ceiling` (default $3) would pass `--budget` (default $17).
- A run stops when its own cost passes its ceiling.
- Prices come from `menu_agent/pricing.py`, confirmed on the official pricing page on 2026-11-25.

## The practice restaurants

All four are invented, with `.example` web addresses. Each one tests a page format:

| ID | Format | What it tests |
|---|---|---|
| P1 | One HTML page | Qualifiers ("GF bun available", "no croutons"), an option, a "contains" warning, a market price, sides with names and prices only |
| P2 | Tabbed HTML, with every panel in the page | Prices on their own line, the same dish on lunch and dinner, an image-only Specials panel |
| P3 | An index page linking to separate menu pages | One linked page wasn't saved; a drinks page is out of scope; small plates have names and prices only |
| P4 | A two-page PDF | A description that runs across the page break, a raw-food notice |

The answer keys (`reference.json`) were written by the same author as the menus. They test the pipeline, not anyone's accuracy. `examples/practice/build_practice.py` rebuilds everything.

## Measures

The measures were written down before any testing. They're scored per restaurant and overall:
- **Menu coverage:** captured, missed, duplicated, invented
- **Field accuracy:** name, section, description, price; ingredient precision and recall
- **Supporting-passage correctness:** machine-checked, plus a person's sample
- **Unknowns kept as unknown:** fabrications counted separately
- **Extraction problems flagged**
- **Warnings the page states that were missed**
- **Cost per restaurant**
- **Human review minutes**

## Layout

`menu_agent/` holds:

| File | What it does |
|---|---|
| `extract.py` | Turns HTML and PDF pages into numbered lines |
| `captures.py` | A restaurant's saved pages, checked by hash |
| `text.py` | Normalization and the verbatim-quote check |
| `tools.py` | The agent's tools and the code checks |
| `agent.py` | The loop, caching and spending guards |
| `baseline.py` | The keyword rules |
| `score.py` | The measures and the review sheet |
| `pricing.py` | Token prices |

The rest of the repository:
- `prompts/agent_v0.md`: the agent's instructions
- `data/`: the dish-type dictionary and ingredient keywords (see `data/SOURCES.md`)
- `examples/practice/`: the four fictional restaurants

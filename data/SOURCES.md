# Data files and where they come from

Both files were exported from the private Eat THIS! repository at commit `d1d0848` (2026-11-25). They contain generic ingredient and dish names only: no restaurant names, menus or recipe text.

| File | Exported from | Used by |
|---|---|---|
| `ingredient_vocabulary.txt` | The union of `ingredient` in `scripts/allergy-checks.csv`, `kind` in `scripts/kinds.csv` and `normalized_ingredient` in `docs/research/dish-library-sample/observations.csv` (278 terms) | The baseline's ingredient keywords (method §7 rule 6) |
| `dish_types.csv` | Each `## DTnn` heading and its "Variations researched" line in `docs/research/dish-library-sample/dish_types.md` (30 types) | The agent's dish-type proposals and the baseline's dish-type keywords (rule 9) |

The dictionary is the existing one (D-071, Project 2 record): the agent may propose a type, the reviewer confirms, and an unmapped dish stays unmapped. Neither file changes before the freeze except through a logged change.

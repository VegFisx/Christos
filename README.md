# Christos (炼膏师)

**CHemistry ReactIng SysTem for OrganicS** — a reaction-prediction engine for
organic chemistry built on a reusable, provenance-tracked template library.

Christos takes a set of chemical inputs, resolves them against curated
herbal / natural-product / formula tables, and enumerates the reactions those
inputs can undergo under a stated condition class.  Every predicted entry
carries the template that produced it, the literature or dataset record the
template was mined from, and the condition evidence behind the match.  Nothing
is scored and nothing is ranked: the output is a ledger you audit, not a
leaderboard you trust.

The name is a back-formation of *CHemistry ReactIng SysTem for OrganicS*.  In
Chinese the program is called 炼膏师, after the alchemist who tends the furnace.

---

## Status

`v0.9.0-beta` — research prototype, not a validated production tool.  See
[`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) before using any output in a
publication or a regulatory context.

The public build deliberately disables target-agnostic retrosynthesis, free-form
reagent specification, and purchasable-building-block lookup.  Those paths are
available only when the engine is started with `CHRISTOS_RESEARCH_MODE=1` on a
machine that holds the full internal dataset.

---

## What is in this repository

| Path | Contents |
|---|---|
| `chemreact.py` | Command-line entry point: `predict`, `routes`, `info` |
| `ui.py`, `ui_page.html` | Local web UI (binds to `127.0.0.1`) |
| `desktop.py` | Thin native-window wrapper around the local UI |
| `core/` | Reaction engine: cascade, template matching, direction, scoring internals, optional xTB thermodynamic layer |
| `conditions/` | Condition-class model and reagent activation rules |
| `rules/` | Template library (`rules.json`), schema, stereochemistry checks, sanity checks |
| `sources/` | Read-only accessors for the herb, formula, natural-product and alias tables |
| `api/` | Programmatic prediction interface |
| `tools/` | Read-only database helper, mapped-atom safety audit, regression runner |
| `data/demo/` | Small de-identified demo catalogue (100 herbs, 50 formulas) |

---

## Requirements

* Python 3.12
* RDKit, RDChiral, NumPy, joblib
* `pywebview` only if you want the native window (`desktop.py`)

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
```

---

## Quick start

```bash
python chemreact.py info
python chemreact.py predict --herb 甘草 --limit 12 --rounds 1
python chemreact.py routes --target "CC(=O)Oc1ccccc1C(=O)O" --depth 2
python ui.py --no-browser      # then open http://127.0.0.1:8765/
```

The engine locates itself in this order:

1. `CHEMCREACT_STAGE` environment variable, if set;
2. this repository's own directory (the normal case after `git clone`);
3. a fixed development path (author's machine only).

---

## Data

The full databases (**≈63 MB herbal SQLite, ≈296 MB natural-product SQLite**,
plus derived formula and alias tables) are **not** part of this repository.
They are assembled from third-party sources with their own licences and cannot
be redistributed here.  `data/demo/` holds a small catalogue that is enough to
exercise the UI and read the output format.

`data/README.md` describes the expected schema and how the tables are built.
Every database access in this codebase goes through a read-only URI
(`file:...?mode=ro`), so pointing Christos at a database never modifies it.

---

## Environment variables

| Variable | Purpose |
|---|---|
| `CHEMCREACT_STAGE` | Directory holding `core/`, `rules/`, `sources/` |
| `CHRISTOS_TCMAI_SRC` | Directory holding `thermo_xtb.py` (optional) |
| `CHRISTOS_XTB` | Path to the `xtb` executable (optional) |
| `CHRISTOS_RESEARCH_MODE` | `1` enables target-agnostic route search and free reagents |
| `CHRISTOS_DB_DIR` | Directory containing `tcm.db` and `coconut.db` |

If the xTB executable is absent the thermodynamic layer reports itself
unavailable and the rest of the pipeline continues without ΔG estimates.

---

## Scope and safety

Christos is a research instrument for enumerating plausible transformations.
It is **not** a synthesis planner, and it makes no claim that a listed
transformation is practical, safe, legal or economical.  Reaction conditions
are reported as evidence classes, not as validated protocols.

The public build omits:

* retrosynthesis towards arbitrary user-supplied targets;
* free-form reagent and solvent specification;
* purchasable-building-block lookup and supplier links.

This is a deliberate boundary.  Please do not work around it in derivative
deployments.

---

## Citation

If you use Christos in academic work, please cite the system paper.  A
`CITATION.cff` is provided; fill in the DOI once the preprint is public.

---

## Licence

MIT.  See [`LICENSE`](LICENSE).

---

## 中文简介

Christos（炼膏师）是一个面向有机化学的反应预测引擎。它把输入的药材、天然产物或方剂
解析到化合物层面，再按给定条件类别枚举可能发生的反应。每条预测都附带产生它的模板、
模板的文献/数据集出处，以及条件依据。系统**不打分、不排序**，输出的是可供人工审计的
台账，而不是排行榜。

完整数据库（约 63 MB 中药库、约 296 MB 天然产物库，以及派生的方剂表与别名表）不随
仓库分发，原因见 `data/README.md`。`data/demo/` 内有一个小规模目录，足以体验界面与
输出格式。

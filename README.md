# Christos

A local, auditable reaction-prediction system for Chinese medicine component
clarification: resolve herb/formula names to compound seeds, enumerate products
with reaction templates, and keep the source record, template and condition
evidence attached to every candidate.

This repository contains the engine, the rule library, the benchmark data and
the scripts needed to reproduce the published numbers. **The manuscript and its
figures are not included.**

## Reproduce the experiments

Two documents answer this:

- **`PUBLIC_REPRO.md`** — one page: what is reproducible, what is not, and why.
- **`REPRODUCE.md`** — full commands, runtimes, expected outputs and caveats.
- **`TEST_EXAMPLES.md`** — copy-paste smoke tests and holdout cases, with expected outputs.

### Quick start

Run from the repository root on Windows with Python 3.12:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`rdchiral` and SmartReact are vendored under `libs/`; no extra install is needed.

### Headline checks

| Experiment | Command | Expected |
|---|---|---|
| Forward, USPTO-50k 50,016 | `$env:CHEMCREACT_BENCH_OUT='out'; python -I tools\paper_bench_50k_forward.py 100000 4` | 92.01% (stereo off 82.77%, baseline 55.53%) |
| Official test split | `$env:CHEMCREACT_BENCH_OUT='out'; python -I tools\paper_bench_official_test.py 2` | 91.71% any-position; top-1 43.28% is diagnostic only |
| Reverse coverage, 5,002 | `$env:CHEMCREACT_BENCH_OUT='out'; python -I tools\paper_bench_50k_coverage.py 4 data/benchmark/lib_uspto50k_excl_v2.jsonl 10` | 94.74% |
| Reverse coverage, 50,016 | `$env:CHEMCREACT_BENCH_OUT='out'; python -I tools\paper_bench_50k_coverage.py 4 data/benchmark/lib_uspto50k_excl.jsonl 1` | 79.81% |
| Paozhi holdout, 31 cases | `$env:CHEMCREACT_TCM_DB='data\tcm_holdout.db'; python -I tools\run_holdout_paozhi.py --mode evidence --rounds 1` | 20/21 skeleton-level with the reference supplement |
| Rule/mapping safety | `python -I tools\audit_mapped_safety.py` | ERROR 0 |

The holdout needs the shipped reference-structure supplement:

```powershell
python -I tools\score_holdout_presence.py reports\holdout_paozhi_20261127.json `
  reports\holdout_paozhi_20261127_structure_supplement_20261127.json
# 20/21 skeleton-level hits, 1 positive miss, 10 negative controls
```

The 3-round development configuration reaches 21/21 positives but also raises
product formation in the negative controls from 5/10 to 9/10. That trade-off is
documented in `PUBLIC_REPRO.md` and the paper; selectivity is not an acceptance
criterion at this stage.

### What is not reproducible from this repository alone

- **Multi-step planning** (47.67%/72.33%): needs ORD-derived purchasable-block
  indices and a COCONUT index that are not shipped because of size.
- **Formula coverage** (85.64%/44.29%): needs `formula_db.json`, not shipped.
- **Full TCM database** (31,646 compounds): only a 17-herb demo subset and a
  56-compound holdout subset are shipped.
- **The manuscript and figures**.

See `PUBLIC_REPRO.md` for the complete list.

## Repository layout

| Path | Contents |
|---|---|
| `core/`, `rules/`, `conditions/`, `sources/` | Engine, 117-rule library, condition layer, input resolution |
| `tools/` | Benchmark, audit and reproduction scripts |
| `data/benchmark/` | USPTO-50k targets, official test split, reverse template libraries |
| `data/tcm_subset.db` | 17-herb demo subset (2,899 compounds) |
| `data/tcm_holdout.db` | 56-compound holdout-only subset (31 cases) |
| `reports/` | Derived artifacts, template pools, benchmark results, data card |
| `integration/` | Command-line and desktop bridges |

## Data and license

Provenance, upstream licenses and known limitations are in `DATA_CARD.md`.
Code is MIT (see `LICENSE`); upstream data carry their own licenses. Citation
metadata is in `CITATION.cff` (version 1.1.0; DOI `10.5281/zenodo.24564325`).

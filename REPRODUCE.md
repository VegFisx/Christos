# Reproducing the numbers

Everything below was run from a **fresh clone** of this repository on
Windows 11 with CPython 3.12.10 and the pinned versions in `requirements.txt`.
The clone was 101.8 MB (including the shipped derived artifacts).

Each command prints a summary and writes a JSON next to it. Small samples are
for a quick smoke test; the full-size commands follow.

## Smoke tests (minutes)

```powershell
# 1. forward, official 5,001-reaction test split, first 150 rows
$env:CHEMCREACT_BENCH_LIMIT='150'; $env:CHEMCREACT_BENCH_OUT='_out'
python -I tools/paper_bench_official_test.py 1
# measured: recall 88.67%, top-1 48.67%, mean 21.9 candidates, 0 errors, 16 s

# 2. reverse coverage, every 500th target (101 targets)
python -I tools/paper_bench_50k_coverage.py 1 reports/paper/data/lib_uspto50k_excl_v2.jsonl 500
# measured: any-hit 95/101 = 94.06%, 152 s

# 3. multi-step, 20 targets, depth 2, beam 4
$env:CHEMCREACT_MS_TPL='reports/paper/data/lib_uspto50k_excl_v2_freq10.jsonl'
$env:CHEMCREACT_MS_TAG='repro_d2'
python -I tools/bench_multistep.py 20 2 4 --use-lib
# measured: 10/20 = 50.0% (paper: 47.67% on 300 targets), 45 s
```

Small samples deviate from the paper values by a few points, which is expected:
the official split smoke test uses 3% of the rows and the multi-step test uses
7% of the targets.

## Full runs (hours)

| Command | Paper value | Wall clock on this machine |
|---|---|---|
| `python -I tools/paper_bench_50k_forward.py 100000 2` | 92.01% (current default) | ~1,800 s |
| `python -I tools/paper_bench_official_test.py 2` | 91.71% / top-1 43.28% | 354 s |
| `python -I tools/paper_bench_50k_coverage.py 4 reports/paper/data/lib_uspto50k_excl_v2.jsonl 10` | 94.74% | 2,428 s |
| `python -I tools/paper_bench_50k_coverage.py 4 reports/paper/data/lib_uspto50k_excl.jsonl 1` | 79.81% | 2,311 s |
| `CHEMCREACT_MS_TPL=reports/paper/data/lib_uspto50k_excl_v2_freq10.jsonl python -I tools/bench_multistep.py 300 2 4 --use-lib` | 47.67% | 906 s |
| same with `300 3 4` | 72.33% | 1,446 s |

The multi-step benchmark **requires** `--use-lib` and the `_freq10` library
(16,891 compiled templates). Without them it falls back to the 3,025-template
clustered library and reports roughly 21 points lower.

## What still needs data that is not in this repository

| Input | Needed for | Where to get it |
|---|---|---|
| `tcm.db` (63 MB, SQLite) | the **full** herbal database; a 1.96 MB subset of the rows the paper touches ships in `data/tcm_subset.db` | not redistributable as a whole |
| `ord-data/` (1.2 GB parquet) | only for **re-mining** templates; the mined library itself ships here | Open Reaction Database, `ord-data` release |
| `reports/paper/data/uspto_mit/USPTO_MIT.csv` (53.8 MB) | the 480K split experiment | `python tools/fetch_data.py mit` |

So: **all four forward/reverse/multi-step benchmark families reproduce from a
clean clone**, and the TCM-side validations re-run against the bundled subset:

```powershell
python -I tools/validate_tcm_on_subset.py
# literature 5/5 consistent, paozhi 3 consistent + 3 formula-only, formula 4/4
```

See `data/TCM-SUBSET.md` for what the subset contains and what it leaves out.
The recorded outputs of the same runs are in `reports/validation/`, so every
claim can also be read without running anything.

The recorded outputs of those TCM-side validations are shipped in
`reports/validation/` so the claims can be read without the database:

| File | What it records |
|---|---|
| `literature_paths_20261104.json` | five literature cases: substrate, target, matched rule, chain |
| `paozhi_paths_20261104.json` | six processed-herb cases with per-target status |
| `formula_decoction_20261104.json` | Sini decoction: 4/4 targets with rules |
| `formula_followups_20261104.json` | two-round glycyrrhizin, single vs combined decoction, Huangqin decoction |
| `whole_herb_20261106.json`, `whole_herb_top12_marker_20261106.json`, `whole_herb_20261106_top20prec.json` | whole-herb runs in three sampling modes |
| `citation_check.json`, `quote_check.json`, `literature_audit.json` | machine audit of all 25 DOIs and 25 quotes |
| `kinetics_calibration_20261106.json` | fitted rate constants, Q10 and Arrhenius Ea |
| `template_leakage_20261104.json`, `template_similarity_20261105.json` | leakage and nearest-neighbour checks |

Each file names its substrates by `ingredient_id` and its rules by rule id, so
the entries can be checked against the database if you have it.

## Environment notes

- Always run with `python -I`. A workspace-wide `PYTHONPATH` can shadow `libs/`.
- `libs/smartreact` is vendored and added to `sys.path` by the entry points.
- On Windows, console code pages break the `✓`/Chinese output of some audit
  scripts; each script reconfigures its own stdout, so this only matters if you
  redirect output to a file with a legacy code page.

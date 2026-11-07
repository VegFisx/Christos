# Christos

A local reaction-prediction system for forward enumeration, retrosynthesis, and
result-level provenance, with a traditional-Chinese-medicine (TCM) input layer.

Every candidate keeps the record it came from: template id, source compound,
reaction round, condition marker, and the flags that say which evidence is
missing. The system answers "by these rules, A can become B" — it does not
predict yields, selectivity, or whether a reaction is practical.

## What is in this repository

| Path | Content |
|---|---|
| `core/` | Reaction engine, template application, retrosynthesis search, scoring, thermodynamics |
| `conditions/` | Condition templates, activation scoring, reaction-extent annotation |
| `rules/` | Curated rules (70+), evidence files, direction table |
| `sources/` | Input resolution: herb names, species, formulas |
| `integration/tcmai_bridge/` | CLI (`chemreact.py`) and local web UI (`ui.py` + `ui_page.html`) |
| `tools/` | Benchmark, audit, validation and figure scripts |
| `libs/smartreact/` | Vendored base-template enumerator (not on PyPI) |
| `reports/` | Round-by-round reports, and the manuscript under `reports/paper/` |

## Quick start

```powershell
python -m pip install -r requirements.txt

# forward prediction from a SMILES, decoction conditions, one round
python integration/tcmai_bridge/chemreact.py predict --smiles "CCO" --cond 煎煮 --rounds 1 --limit 5

# the local web UI
python integration/tcmai_bridge/ui.py
```

The produced directory contains a CSV ledger (one row per reaction step), a TSV
index, a `meta.json`, and a one-page HTML report where each product can be
traced back through the steps that produced it.

## Benchmarks (frozen settings)

| Task | Result |
|---|---|
| Forward, USPTO-50k, 50,016 reactions | 91.69% candidate-set recall (45,862 hits; Wilson 95% CI 91.45–91.93) |
| Forward, official 5,001-reaction test split | 91.71% recall, top-1 43.28%, MRR 0.5496 |
| Forward, USPTO-MIT deterministic sample (39,176) | 71.18% recall, top-1 32.81%, MRR 0.4187 |
| Reverse, 5,002 targets / 79,184 templates | 94.74% any-hit |
| Reverse, 50,016 targets / 3,065 leak-controlled templates | 79.81% any-hit |
| Multi-step route found, depth ≤2 / ≤3, 300 targets | 47.67% / 72.33% |

Strict same-reaction overlap between our template examples and either test set is
zero (0/50,016 and 0/479,035). The transformer baselines that report 90–93% are
top-1 on USPTO-MIT's 40,000-reaction split; those numbers are not directly
comparable with candidate-set recall here.

## Data

The raw data is **not** included. It is large and separately licensed:

- ORD reaction records (`ord-data/`) — needed only to re-mine templates; the
  mined library ships here
- USPTO-MIT — download with `python tools/fetch_data.py mit`
- `tcm.db` — the full herbal compound database, read-only, not distributed here.
  A 1.96 MB subset of the rows the paper touches ships in
  `data/tcm_subset.db`, and `python tools/validate_tcm_on_subset.py` re-runs the
  TCM-side validations against it.

The derived artifacts a reviewer needs to re-run the benchmarks **are** in this
repository: `reports/mined_forward_templates_full_s5.jsonl` (9.4 MB),
`reports/paper/data/lib_uspto50k_excl*.jsonl` (retrosynthesis template
libraries), `reports/paper/data/uspto50k_canon.jsonl` and the official
5,001-reaction test split.

## Reproducing the numbers

See [REPRODUCE.md](REPRODUCE.md) for the commands and the values measured from a
fresh clone, including which parts still need `tcm.db`.

```powershell
python -I tools/paper_bench_50k_forward.py 100000 2      # forward, full set
python -I tools/paper_bench_official_test.py 2           # official 5,001 split
python -I tools/paper_bench_50k_coverage.py 4 reports/paper/data/lib_uspto50k_excl_v2.jsonl 10
python -I tools/bench_multistep.py 300 2 4 --use-lib
python -I tools/audit_mapped_safety.py                   # atom-mapping safety gate
```

Every report in `reports/` states the exact command it used.

## Known limits

- The system does not rank well: top-1 is 43%, so it is a candidate generator.
- It cannot tell whether a pair of molecules reacts at all (decoy control shows
  ~0.2% specificity). This is a documented design limit, not a bug.
- Condition parameters annotate; they never filter products. Temperature and
  time extrapolation were tested with leave-one-out and are reported as
  unreliable, so they stay as annotations.
- No wet-lab validation.

## Licence

MIT — see [LICENSE](LICENSE). Third-party components keep their own terms
(`libs/smartreact/` is vendored; RDKit, NumPy, pandas, SciPy, scikit-learn and
matplotlib are BSD-family). `data/tcm_subset.db` is distributed only so that the
paper's cases can be re-run; see `data/TCM-SUBSET.md`.

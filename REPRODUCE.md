# Reproducing the numbers

Everything below was run from a **fresh clone** of this repository on
Windows 11 with CPython 3.12.10 and the pinned versions in `requirements.txt`.

For a one-page answer to "what can an expert actually run from this repository?",
see `PUBLIC_REPRO.md`.

The forward, official-split, and reverse-coverage runs use only files shipped
in the repository. The multi-step benchmark additionally needs the full
`tcm.db` and the ORD-derived purchasable-block indices
(`reports/purchasable_blocks_*.jsonl` and `reports/coconut_inchikey_index.jsonl`).
Those are not shipped because of size, so its commands cannot be reconstructed
from the repository alone; the numbers are reported for completeness.

Each command prints a summary and writes a JSON next to it. Small samples are
for a quick smoke test; the full-size commands follow.

## Smoke tests (minutes)

```powershell
# 1. forward, official 5,001-reaction test split, first 150 rows (bench default, no coverage)
$env:CHEMCREACT_BENCH_LIMIT='150'; $env:CHEMCREACT_BENCH_OUT='_out'
python -I tools/paper_bench_official_test.py 1
# measured: recall 88.67%, top-1 48.67%, mean 21.9 candidates, 0 errors, 16 s

# 2. reverse coverage, every 500th target (101 targets)
python -I tools/paper_bench_50k_coverage.py 1 data/benchmark/lib_uspto50k_excl_v2.jsonl 500
# measured: any-hit 95/101 = 94.06%, 152 s

# 3. multi-step, 20 targets, depth 2, beam 4
$env:CHEMCREACT_MS_TPL='data/benchmark/lib_uspto50k_excl_v2_freq10.jsonl'
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
| `python -I tools/paper_bench_50k_forward.py 100000 4` | 92.01% (current default; 2026-11-27 rerun) | 1,973 s |
| `CHEMCREACT_STEREO_CANON=0 python -I tools/paper_bench_50k_forward.py 100000 4` | 82.77% (stereo off) | 1,956 s |
| `CHEMCREACT_BENCH_LEGACY=1 CHEMCREACT_BENCH_NO_EXTRA=1 python -I tools/paper_bench_50k_forward.py 100000 4` | 55.53% (legacy baseline) | 853 s |
| `python -I tools/paper_bench_official_test.py 2` | 91.71% (any-position recall) | 216 s |
| `python -I tools/paper_bench_50k_coverage.py 4 data/benchmark/lib_uspto50k_excl_v2.jsonl 10` | 94.74% (2026-11-27 rerun) | 2,696 s |
| `python -I tools/paper_bench_50k_coverage.py 4 data/benchmark/lib_uspto50k_excl.jsonl 1` | 79.81% (2026-11-27 rerun) | 2,413 s |
| `CHEMCREACT_MS_TPL=data/benchmark/lib_uspto50k_excl_v2_freq10.jsonl python -I tools/bench_multistep.py 300 2 4 --use-lib` | 47.67% (2026-11-27 rerun) | 928 s |
| same with `300 3 4` | 72.33% (2026-11-27 rerun) | 1,460 s |

The multi-step benchmark **requires** `--use-lib`, the `_freq10` library
(16,891 compiled templates), and the non-shipped files listed at the top.
Without `--use-lib` it falls back to the 3,025-template clustered library and
reports roughly 21 points lower.

The multi-step values are route-recovery rates: a target counts as recovered if
at least one route is found, whether or not every step passes `step_usability`.
Counting only targets with at least one fully usable route gives 47.33% at
depth ≤2 (142/300) and 69.00% at depth ≤3 (207/300).

The official-split row is the bench default and does not include the production coverage tier.
See "Production coverage tier" below for the 96.70% configuration.

Except for the optional re-ranker section, every score in this file is **any-position
recall**: the recorded product (forward) or the recorded precursor set (reverse) must
appear somewhere in the candidate list. The official-split script also prints top-1;
that is a ranking diagnostic, not the acceptance criterion, and the paper does not
use it for any headline number.

## Re-ranking: models, candidate table, and the overlap caveat

The re-ranker only reorders the candidate list; recall never changes.

```powershell
# Candidate-level table (257,444 candidates / 11,996 reactions / 47 columns).
# 40 s to build; the parquet is not shipped, rebuild it instead.
python -I tools/build_candidate_table.py
python -I tools/test_candidate_table.py          # 0 failures expected

# Pack v2 + the template hit-rate post-process into an optional model file.
python -I tools/build_blend_model.py --lambda 0.25
python -I tools/test_rerank_v4.py                # 0 failures expected
```

| Model (`CHEMCREACT_RERANK_MODEL`) | Official 4,993 top-1 | top-5 | Notes |
|---|---|---|---|
| none (emission order) | 43.28% | 67.77% | baseline |
| `reports/rank_model_v2.pkl` (optional) | 72.62% | 89.06% | previous default |
| `reports/rank_model_v4.pkl` (default) | 73.72% | 90.31% | v2 + hit-rate blend, McNemar p = 0.0002 |

These rows use the pre-coverage candidate set (33.5 candidates). The production default now adds
a coverage tier and bounded stereo enumeration; its pool has 44.3 candidates, recall 96.70%
(2026-11-27 rerun; 96.25% in the 2026-11-21 run), and v4 top-1 73.30%. See
"Production coverage tier" below.

Reproduce either row:

```powershell
$env:CHEMCREACT_BENCH_CLI_CONFIG='1'; $env:CHEMCREACT_BENCH_RERANK='1'
$env:CHEMCREACT_RERANK_MODEL='reports/rank_model_v4.pkl'
$env:CHEMCREACT_BENCH_TAG='rerank_v4_official'
python -I tools/paper_bench_official_test.py 6      # ~95 s
```

Worker count matters for wall clock. On a 16 GB machine the full 4,993-row
split takes 587 s with 2 workers (about 1.6 GB), 93 s with 6 (6.8 GB), and
86 s with 8 (8.1 GB); 6 is the knee.

Two caveats belong with these numbers. First, 584 of the 4,993 official test
reactions (11.7%) also appear in the re-ranker's training half; on the remaining
4,409 rows, v2 scores 72.19% and v4 73.24%. Second, the training dataset must be
built with the production engine settings (`--curated --strict-redox
--mined-top-conditions`); a default-config dataset has 21.5 candidates per
reaction against the official split's 33.5, and models trained on it transfer
poorly.

### Production coverage tier (default on)

Since 2026-11-21 the command-line default adds candidates in two layers. The first is a template
tier mined from the 44,932 training reactions of the official split. The second is bounded stereo
enumeration for coverage products whose template contains no stereochemistry. Both layers only add
candidates; they never remove or reorder existing ones. Multi-compound batches with more than two
distinct substrates skip both layers, so herbal runs keep their previous candidate set.

Measured on the full official split (4,993 evaluable reactions, v4 re-ranker):

| Configuration | Recall | top-1 | top-5 | Candidates/reaction |
|---|---|---|---|---|
| no coverage (`--no-rescue --no-stereo-enum`) | 92.19% | **73.72%** | 90.31% | 33.48 |
| coverage, no stereo | 94.99% | 73.70% | 91.51% | 35.07 |
| production default (coverage + stereo), 2026-11-21 | 96.25% | 73.18% | 90.83% | 44.25 |
| production default, 2026-11-27 rerun | **96.70%** | **73.30%** | **91.39%** | **44.3** |

The stereo layer removes stereochemistry from a coverage product, enumerates at most eight
stereoisomers for products with at most four stereocentres, and also adds the flat structure.
Every variant is labelled "stereochemistry unspecified, enumerated variant". A hit therefore
means that the literature product is among the enumerated candidates, not that the system
selected its configuration.

`tools/paper_bench_official_test.py` builds `SmartReactEngine` directly and does not inherit the
CLI default. To reproduce the production row, set the coverage variables explicitly:

```powershell
$env:CHEMCREACT_BENCH_CLI_CONFIG='1'; $env:CHEMCREACT_BENCH_RERANK='1'
$env:CHEMCREACT_BENCH_RESCUE='1'
$env:CHEMCREACT_BENCH_RESCUE_PATH='reports/mined_forward_templates_uspto_train.jsonl'
$env:CHEMCREACT_BENCH_RESCUE_MIN='100000'
$env:CHEMCREACT_BENCH_RESCUE_MIN_SUPPORT='1'
$env:CHEMCREACT_BENCH_RESCUE_MAX_SUPPORT='1000000000'
$env:CHEMCREACT_BENCH_STEREO_ENUM='8'
$env:CHEMCREACT_BENCH_STEREO_MAX_CENTERS='4'
$env:CHEMCREACT_BENCH_TAG='production_default'
python -I tools/paper_bench_official_test.py 2      # 4,993 rows, 1,031 s (2026-11-27)
```

The no-coverage row is the bench default and needs none of these variables. On the command line,
`--no-rescue` and `--no-stereo-enum` restore the 92.19% candidate set.

Leakage. All 5,001 official test reactions were removed from the template source at the reaction
level (5,068 mapped rows, duplicates included). For the 140 baseline misses recovered by the
coverage tier, the source shares no main product, reactant set, or flat constitution (0/140 for
each check). A separate library mined from 9,534 mapped USPTO-MIT reactions outside the 50k corpus
reaches 94.21% with 63.06 candidates on the same split; its first-shard audit found no shared main
product or reactant set among 947 recovered reactions. That external library is not part of the
default.

The earlier ORD low-support pool is superseded. Its full official-split result was 94.45% at
71.36 candidates (`reports/第一百六十一轮-全量95%覆盖评测-20261120.md`).

## Paozhi holdout modes

The processing holdout has three explicit configurations. The default is the evidence
configuration: only the 18 cited processing rules, with the extra, mono, base, coverage, and
stereo layers off. The production configuration adds the train coverage tier and stereo
enumeration. The multi-round file keeps the same cases but runs three rounds; its expectations
were pre-registered separately.

```powershell
# the full tcm.db is not distributed; this subset contains all 56 holdout ids
$env:CHEMCREACT_TCM_DB='data\tcm_holdout.db'
python -I tools\run_holdout_paozhi.py --mode evidence --rounds 1
python -I tools\run_holdout_paozhi.py --mode production --rounds 1
python -I tools\run_holdout_paozhi.py --holdout data\holdout_paozhi_multiround.json --mode evidence --rounds 3
```

Measured on the 31-case combined holdout after the five derived rules and the oleuropein control.
The 2026-11-27 run from `data/tcm_holdout.db` gives the same 23 consistent / 6 miss / 2 formula-only
as the full `tcm.db` run; the subset contains all 56 seed/target ids.
The 12-case strong validation core (before the gap probes) gives 9 consistent and 3 misses at r1.
Multi-round runs use `max_pairs=128` (single-round keeps 1); with that budget the core reaches
11 consistent and 1 miss, with tianma and acetylastragaloside I closing through the benzylic
oxidation rule plus glycoside hydrolysis. The six gap probes give 4/6 at r1 (saikosaponin,
palmatine, 5-HMF, and evodiamine); at r3 all six close, including the two Kansui probes through the
ester rule. The added oleuropein control is consistent in both configurations at r1 and r3. The
original ligustroside case remains a miss and is retained as a seed-target mismatch: its side chain
is tyrosol (C8H10O2), while the recorded target is hydroxytyrosol (C8H10O3). Overall, evidence r1
gives 23 consistent, 6 miss, 2 formula-only; production r1 gives the same. The script's
`prediction_hit` field is a status match, not a product-presence count. On the 21 cases where the
literature reports a product, the original r1 run gives 18 structural hits plus 2 formula-only
cases, with the 10 negative controls excluded from the denominator. The 2 formula-only cases were
re-checked with reference structures derived from tcm.db (dipotassium atractyloside neutralised;
THSG glycoside hydrolysed), pre-registered in
`data/holdout_paozhi_structure_supplement_20261127.json`. The THSG aglycone matches the full
InChIKey; atractyloside matches the 14-character skeleton only (its full key differs in
stereochemistry). At the holdout's skeleton-level matching, this gives 20/21 (95.2%). Evidence r3
gives 28 consistent, 1 miss, 2 formula-only; production r3 gives the same. The remaining r3 miss is
ligustroside.

Recompute the presence score from a saved holdout JSON (does not rerun the engine):

```powershell
python -I tools\score_holdout_presence.py reports\holdout_paozhi_20261126.json
# 18/21 structure hits, 2 formula-only, 1 positive miss, 10 negative controls

python -I tools\score_holdout_presence.py reports\holdout_paozhi_20261126.json `
  reports\holdout_paozhi_20261127_structure_supplement_20261127.json
# 20/21 skeleton-level hits (95.2%), 1 positive miss, 10 negative controls

python -I tools\run_holdout_paozhi.py --mode evidence --rounds 3
python -I tools\score_holdout_presence.py reports\holdout_paozhi_20261127_evidence_r3.json `
  reports\holdout_paozhi_20261127_structure_supplement_20261127.json
# 21/21 positive hits, but 9/10 negative controls also produce a product
```

The 3-round run is a development configuration, not the default. It closes the
last positive case (tianma) but also increases product formation in the negative
controls from 5/10 to 9/10. The residual problem is selectivity, not missing rule
families. The weak set is 12 cases: 9 consistent, 1 miss, 2 formula-only
at r1; 10 consistent, 0 miss, 2 formula-only at r3. The multi-round protocol is developmental, not
an independent holdout, and it is not a production default.

### Independent validation set (pre- and post-patch)

`data/holdout_paozhi_independent_20261122.json` is separate from the 31-case development panel.
It contains three pre-registered cases for the next general-rule patch: benzyl alcohol to
benzaldehyde, glucose to 5-HMF in Polygonatum, and berberine to berberrubine in Coptis. They are
not in the 31-case panel, not in the evidence-rule sources, and not the literature cases used to
design the candidate rules. The berberrubine target comes from PubChem CID 72704.

```powershell
python -I tools\run_holdout_paozhi.py --holdout data\holdout_paozhi_independent_20261122.json --mode evidence --rounds 1
python -I tools\run_holdout_paozhi.py --holdout data\holdout_paozhi_independent_20261122.json --mode production --rounds 1
```

Pre-patch baseline: evidence r1/r3 give 0 consistent and 3 misses; production r1/r3 give
0 consistent, 2 product-only (benzyl alcohol, berberine) and 1 miss (glucose to 5-HMF).
Post-patch result: all four configurations give 3 consistent and 0 misses; the 5-HMF case closes
with the glucose dehydration/cyclization template. `tools/validate_new_rules.py` passes the two
written rules on positive and negative panels, `tools/validate_derived_rules.py` passes the five
derived rules (14/14), and `tools/test_reaction_cases.py` passes 121/121 with 111/111 active-rule
coverage.

Release gate quick after the five derived rules changes only the honey-fried smoke count. Against
the 48 baseline, the first run fails only on `C_miyan_adj` 48 to 49; the other seven smoke counts,
forward 0.8659, official 0.91 / top1 0.4167, rerank 0.92 / top1 0.75 / top5 0.91, and multistep
0.56 are unchanged. With 49 accepted as the new baseline, the second run passes
(`reports/benchmarks/release-d6c0f03-20261122-1809.json`). The committed state was then rerun on a
clean tree at `f9cdefd` (`dirty=0`); it also passes
(`reports/benchmarks/release-f9cdefd-20261122-1844.json`). After the 31-case control, a clean-tree
run at `ce547f6` (`dirty=0`) passes with holdout 23/31 and the same other metrics
(`reports/benchmarks/release-ce547f6-20261122-2245.json`). After the provenance gate, a clean-tree
run at `306e620` (`dirty=0`) passes with the same holdout, smoke, forward, official, rerank, and
multistep figures (`reports/benchmarks/release-306e620-20261122-2342.json`). After the general
organic probe, a clean-tree run at `033540d` (`dirty=0`) passes with the same figures
(`reports/benchmarks/release-033540d-20261123-0755.json`). After the Boc azole rule, a clean-tree
run at `5ed25d1` (`dirty=0`) also passes with the same figures
(`reports/benchmarks/release-5ed25d1-20261123-1450.json`). After the sulfonamide N-acylation
rule, a clean-tree run at `a196294` (`dirty=0`) passes with the same figures
(`reports/benchmarks/release-a196294-20261123-1506.json`). After the Knorr pyrazole rule, a
clean-tree run at `5f64fa3` (`dirty=0`) passes with the same figures
(`reports/benchmarks/release-5f64fa3-20261123-1521.json`). After the sulfur-ylide epoxide rule
and curated triple support, a clean-tree run at `2139f39` (`dirty=0`) passes with the same
figures; `reports/benchmarks/release-2139f39-20261123-1544.json` is the final gate identity.
The +1 comes from the HMF template acting on honey sugars in the adjuvant scenario; the
no-adjuvant honey scenario and the decoction guard stay at 45 and 824. Round 205 adds a
clean-tree run at `1ac1815` (`dirty=0`) with the same seven metrics:
`reports/benchmarks/release-1ac1815-20261124-1042.json`. The automatic baseline comparison
was skipped because the passed baseline path had a duplicated directory; a direct comparison
with `release-eb3232c-20261124-1011.json` is identical. Forward took 393 s instead of 205 s
because the two new exploratory rules add pool enumeration; recall stayed 0.8659.
Round 206 adds three more class-4 rules and a clean-tree gate at `e2d6347` (`dirty=0`)
with the same seven metrics (`reports/benchmarks/release-e2d6347-20261124-1121.json`);
the baseline comparison is against `release-1ac1815-20261124-1042.json`. Round 207
adds the intramolecular pair mode and a clean-tree gate at `701f5fe` (`dirty=0`) with
the same seven metrics (`reports/benchmarks/release-701f5fe-20261124-1156.json`);
forward took 405 s, and smoke remained 824. Round 208 adds the blind holdout,
formula coverage, candidate-burden report and intra cache; its clean-tree gate at
`ca7eaec` (`dirty=0`) also passes with the same seven metrics
(`reports/benchmarks/release-ca7eaec-20261124-1236.json`), forward 437 s. Round 209
adds blind2 and the template-limit experiment; its clean-tree gate at `26bd22d`
(`dirty=0`) passes with the same metrics
(`reports/benchmarks/release-26bd22d-20261124-1312.json`), forward 434 s.
Round 210 adds the dev-driven rules and blind3; its clean-tree gate at `bade26e`
(`dirty=0`) passes with the same metrics
(`reports/benchmarks/release-bade26e-20261124-1339.json`), forward 230 s.
Round 211 adds C–C/C–N coupling rules; its clean-tree gate at `5bf3691`
(`dirty=0`) passes with the same metrics
(`reports/benchmarks/release-5bf3691-20261124-1526.json`), forward 225 s;
official_rerank top1 moved 0.7567 to 0.7500, within its 0.05 threshold.
Round 212 adds subclass analysis and three narrow rules; after reverting an
experimental reverse-pool fallback that had moved smoke guard 824 to 862, its
clean-tree gate at `9dded5f` (`dirty=0`) passes with the same metrics
(`reports/benchmarks/release-9dded5f-20261124-1821.json`), smoke 824.
Round 213 adds the multi-example alcohol chlorination family; after gating its
thionyl chloride pool to alcohol solvents (it had briefly moved smoke 824 to
856), its clean-tree gate at `9377444` (`dirty=0`) passes with the same metrics
(`reports/benchmarks/release-9377444-20261124-1923.json`), smoke 824. After
the benzyl N-alkylation family, the clean-tree gate at `26d2e7a` (`dirty=0`) also
passes with the same metrics
(`reports/benchmarks/release-26d2e7a-20261124-1954.json`).

### Rule provenance gate

`rules/rules.json` marks every rule with `provenance`. It contains 115 rules: 38 `cited`
(18 in the processing evidence set plus twenty general rules) and 77 `unvalidated`; 6 are disabled.
After excluding the six `paozhi_only` rules from general file-level loading, the engine/RunSpec
default load contains 32 validated rules. With `allow_unvalidated=False` (the engine default),
it skips the 71 active unvalidated rules and records both the loaded and skipped counts in
`curated_note`. `allow_unvalidated=True` restores the exploratory set (103 rules). The CLI's
general/煎煮 path is explicitly exploratory: making it strict would cut the decoction guard from
824 to 538 products, which the release gate rejected as a regression. `--strict-provenance`
makes the general path strict; `--allow-unvalidated` forces exploration. The paozhi
evidence/production path stays strict (18 cited/secondary rules), so its holdout and smoke
scenes are unchanged. Explicit `curated_rule_ids` is treated as a caller opt-in and counted
separately, so single-rule tests and the evidence table keep working.

```powershell
python integration\tcmai_bridge\chemreact.py predict --smiles ... --strict-provenance
python integration\tcmai_bridge\chemreact.py predict --smiles ... --allow-unvalidated
```

`tools/test_provenance_gate.py` passes 8/8: default 17 loaded, exploratory 70, explicit
unvalidated rule 1, evidence table 18, and RunSpec propagation (1 product by default versus
6 in exploratory mode on benzyl alcohol). `paper_bench_official_test.py` explicitly opts in
when reproducing the historical CLI-config benchmark, so published numbers keep their original
rule set.

### General organic coverage probe (TCM-external)

`data/holdout_general_organic_20261123.json` pre-registers 30 reactions sampled from the
USPTO-50k official test split, stratified three per reaction class with seed `20261123`.
The run uses curated rules only, with extra/mono/base/coverage/stereo layers and condition
gating off:

```powershell
python -I tools\run_general_holdout.py
```

Strict curated rules (32 validated) recover **1/30** skeleton hits (1 exact). Exploratory
curated rules (70 active) recover **10/30** skeleton hits (9 exact), with median product
counts of 1 versus 12. The added hits come from seven unvalidated rules: intermolecular
amidation, aminolysis of esters, amide hydrolysis, primary-alcohol oxidation, sulfide
oxidation, ketone reduction, and amide-to-nitrile elimination. This is a recall-only
out-of-domain probe, not the 95% TCM literature metric; it supports keeping general/煎煮
exploratory rather than strict. A post-hoc full-engine run on the same 30 cases (curated all +
extra + mono + base, no rescue/stereo) recovers **30/30** skeleton and 29/30 exact hits. This is a
template-library coverage diagnostic, not an independent generalization claim: classes 1/3/4/10
are covered by base/mined templates, so the remaining gap is in the curated rulebook rather than
the full engine. The audit found **0/30** exact and **0/30** same-substrate overlaps between the
30 cases and the 9,770 base-template example reactions. The mined layer is entirely from
`ord_shards_full`; the templates that hit have support ≥11, median 322, with no support ≤10
templates. ORD exact reaction overlap cannot be checked because the mined file stores no per-
reaction source, so the support distribution is the available proxy. Chinese-source bibliographic
candidates for the seven hit rules are listed in
`reports/第一百八十二轮-七条通用规则中文文献溯源-20261123.md`; they are candidate evidence only,
and `rules.json` has not been changed. The product-leakage caveat is closed by a rerun with
`mined_forward_templates_full_lf.jsonl`, which removes ORD reactions whose products hit the
USPTO-50k evaluation set: the 30-case pilot remains **30/30** (29 exact), and the 295-case
expansion reaches **295/295** (100%; 285 exact). Sources are base 67, mined_lf 200, curated 32;
there are no remaining misses.

The expanded pre-registered sample contains 295 cases (30 per class except 25 in class 10;
29/30 overlap with the 30-case pilot). Strict recovers **46/295** (15.6%; Wilson 11.9–20.2;
45 exact), exploratory **136/295** (46.1%; Wilson 40.5–51.8; 128 exact). Class 2 reaches
19/30 and class 4 reaches 11/30 (10 exact); class 3 reaches 5/30 in both; class 1 reaches
1/30. This is a precision expansion, not a new independent set; the hit-rule list grows to
37 rules. The 2026-11-23 diacylhydrazine-to-1,3,4-oxadiazole and 2-alkynylaniline-to-indole
rules are outside the 30-case pilot and each contribute one class-4 hit in the 295 expansion.
Round 205 adds Conrad–Limpach (alpha-aryl) and indazole; round 206 adds Fischer aza-indole,
Larock indole, and Hantzsch thiazole; round 207 adds the same-molecule macro-lactam rule and
engine support. All six templates are marked `unvalidated`, so they count only in the
exploratory configuration.
A curated two-substrate rule can opt into a reverse-order fallback with
`bidirectional: true`; it is tried only when the forward order gives no products.
The morpholine double-alkylation rule uses that flag, and its validation covers
amine-first, ether-first, the external case, and two negatives.

### Intramolecular pair mode (round 207)

Rules marked `intramolecular: true` may carry two reactant templates that are
matched inside one molecule. The engine (`core/smartreact_engine.py::_apply_intra_pair`)
cuts one interior single bond on the shortest path between the two matches, runs
the pair reaction on the two fragments, rejoins the cut bond, and then passes the
result through the normal atom-balance guard. `intra_min_path` (default 8) keeps
the mode away from short-chain lactams. `cyclization_macro_lactam_001` is the
first rule using it: carboxylic acid + terminal ammonium -> macro-lactam + H2O + H+.
The mode is exploratory (`unvalidated`) and is also wired into the simple
`core/engine.py::apply_rule` path for single-rule probes.


### Blind holdout (round 208)

The 295-case set is no longer a clean selection-level holdout: rounds 205–207
used its misses to choose which gaps to work on. A separate 300-case blind set
was sampled from the MIT USPTO file, excluding every exact 295 reactant/product
match, and frozen before evaluation:

`data/holdout_general_organic_blind_20261124.json`
(SHA-256 `46942D0BA2A107020265B56A08A2A6793B59293304E9DA38A03E6BB38F603DC5`).

Results:

| configuration | blind1 (MIT) | 295 (historical) |
|---|---:|---:|
| strict skeleton | **1/300 (0.3%)** | 46/295 (15.6%) |
| exploratory skeleton | **36/300 (12.0%)** | 136/295 (46.1%) |
| full_lf skeleton | **204/300 (68.0%)** | 295/295 (100%) |
| full_lf exact | **202/300** | 285/295 |

A second frozen blind2 from USPTO-50k (SHA-256
`1D8FFF45492605B70AD770D7C357B96A5EAA6B5B113A9C9600C61D31405C4569`) gives
strict 2/300, exploratory 57/300, and full_lf 290/300. The large blind1 vs
blind2 gap shows that source distribution, not a single “blind” number, is the
right unit of reporting. Expanding full_lf templates from 20k to 100k moved
blind1 only from 204 to 205, so template count is not the bottleneck. A third
blind3 from MIT (SHA-256 `D420C132CCA3830444D248C13283A8C56F1213879CB39C6C63C1D208E9183BB5`)
gives strict 2/300, exploratory 21/300, and full_lf 203/300. The four
dev-driven general rules added in round 210 left dev full_lf at 195/300 and
blind3 at 203/300; they are standard-example-validated but did not move these
sets. A mapped dev-miss classification (105 misses, RXNMapper 105/105) gives
C–N formed 34, C–C formed 29, C–O formed 14, C–Cl 9; the next batch should
target generic C–N coupling on protected substrates and C–C coupling, not more
deprotection rules. Three standard-example coupling rules (Suzuki,
Sonogashira, N-arylation) left dev full_lf at 195/300 and gave blind4
full_lf 205/300 with **0 curated hits**; the simple named-reaction templates
are narrower than the mapped element classes. A deeper subclass pass gives
N-alkylation 13, C–C/alkyl–alkyl 12, C–Cl 9, C–C/aryl–alkyl 7,
C–O/ester 7, C–N/aryl amine 7, C–N/amide 6. Three subclass rules
(N-alkylation, O-acylation, alcohol chlorination) also left dev at 195/300;
single-example templates are too narrow, so the next step is multi-example
family templates. A chlorination family from ethanol/benzyl alcohol/cyclohexanol
moved dev full_lf 195 -> 197/300 (curated 4 -> 6); a benzyl/heteroaryl-methyl
N-alkylation family moved it to **198/300** (curated 7). Blind4 hash:
`7682341787D01D6498E185B914A899A2C5EC85FBD76D73892CAD8A8182BC313B`.
A frozen blind5 (SHA-256
`92083DFC5AAC782EFDEBFBA806F748346C16063CD6822CF2DF54EBF51FE16683`) gives
strict 3/300, exploratory 39/300, full_lf 212/300. The family rules contribute
5 curated hits on blind5 (N-benzyl 1, Suzuki 3, Sonogashira 1); the alcohol
chlorination family contributes 0 there, so its dev gain does not generalise yet.
Details:
`reports/第两百零八轮-blind留出集与方剂库-20261124.md`,
`reports/第两百零九轮-第二张blind与模板上限-20261124.md`,
`reports/第两百一十轮-dev缺口与四条通用规则-20261124.md`,
`reports/第两百一十一轮-CN-CC偶联与blind4-20261124.md` and
`reports/dev_reaction_classes_20261124.md`.

### Formula library coverage (round 208)

The user's formula library is now readable. `tools/audit_formula_db_coverage.py`
reads `formula_db.csv` and `tcm.db` in read-only mode:

- 12,075 formula rows; 12,070 parse to at least one ingredient;
- 119,067 ingredient mentions; 95,950 resolve to `tcm.db` herbs (81.6%);
- 4,321/12,070 formulas (35.8%) resolve every ingredient.

The unresolved tail is dominated by synonyms/processing names, excipients, and
parenthetical annotation fragments; this is an herb-resolution lower bound, not
a chemistry validation. Machine-readable rows:
`reports/formula_db_coverage_20261124.json`.

The current recommended coverage uses the sourced synonym table and leaves
ambiguous aliases unresolved:

```powershell
python -I tools\audit_formula_db_coverage3.py --no-alias-map
```

- 117,585 ingredient mentions; 85.64% resolve to `tcm.db` herbs;
- 44.29% of formulas resolve every ingredient;
- 2,541 mentions are ambiguous and are not counted.
Output: `reports/formula_db_coverage3_sourced_20261124.json`.

### TCM decoction example (current default)

```powershell
python -I integration\tcmai_bridge\chemreact.py predict --herb 甘草 --limit 12 --rounds 1 --cond 煎煮 --out runs\gc12
```

Current result: 2,176 candidate products and 2,176 provenance paths. Structural
field completeness is 100% for all nine field groups; the condition rationale
splits into 41.5% ORD condition windows, 30.8% temperature-policy notes, and
27.8% "no ORD condition data, admitted". The old 573-path / 1.2% figure came
from the 2026-10 build and is not reproducible with the current default.

### Candidate burden (round 208)

`tools/report_candidate_burden.py` reports candidate counts, not precision.
On 295 exploratory: mean 14.64, median 14, P90 25, 105/295 cases above 16
candidates. On blind exploratory: mean 14.77, median 14, P90 25, 111/300 above
16. The engine still has no calibrated false-positive/feasibility model.

### Unvalidated rule backlog

`reports/evidence_backlog_20261124.md` and
`reports/rules_unvalidated_backlog_20261124.md` list the active `unvalidated`
rules by category (32 after the ORD-evidence promotion; 41 rules with ORD
execution evidence are `secondary`). They remain exploratory; promotion
requires independent literature or reaction data, not a number on 295.

### Drug input source (ChEMBL)

A read-only ChEMBL snapshot ships under `data/drugs/`:
`chembl_37_drugs.jsonl` contains **3,311** approved small molecules
(`max_phase=4`, `molecule_type=Small molecule`) with ChEMBL IDs, preferred
names, synonyms, formulas, InChIKeys, salts, and withdrawal flags. The source
is the ChEMBL REST API (release `ChEMBL_37`, 2026-05-01), licensed CC BY-SA 3.0
(the ChEMBL homepage statement checked on 2026-11-23);
see `data/drugs/README.md` and `chembl_37_meta.json`. No SMILES were hand-written.

```powershell
# Rebuild the snapshot (network required), then verify it offline.
python -I -X utf8 tools\fetch_chembl_drugs.py
python -I -X utf8 tools\test_drug_source.py      # 0 failures expected

# Enumerate reactions for a drug or a list of drugs.
python integration\tcmai_bridge\chemreact.py predict --drug ASPIRIN --cond 煎煮
python integration\tcmai_bridge\chemreact.py predict --drug-file drugs.txt --cond 煎煮
```

The test parses all 3,311 structures with RDKit (0 failures), matches every
molecular formula (0 mismatches), and matches all InChIKey skeletons. Five
records (0.15%) differ from ChEMBL's full InChIKey in the stereo layer (the
SMILES does not encode that layer); this is reported, not edited. Name lookup
prefers the parent over salts and surfaces candidate counts; use a ChEMBL ID
when a specific salt is intended. The adapter adds an input source only:
`rules.json` and the rule set are unchanged by the drug adapter (the current file has 97 rules;
the oxadiazole, morpholine, indole, Grignard, hydrogenolysis, HCl, quaternization, pyridine-hydrogenation, reductive-amination, Boc-amine, ethynylation, and Barbier patches are separate). Multi-drug input is mixture
enumeration, not a dose/combination model, and outputs are not medical advice.

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

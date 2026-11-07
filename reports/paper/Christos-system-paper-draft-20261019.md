# Christos: a provenance-aware, read-only reaction prediction system for natural-product and traditional Chinese medicine research

**Article type:** Software/Research Article (final type to be selected in the PeerJ submission system)  
**Authors:** [to be completed]  
**Affiliations:** [to be completed]  
**Corresponding author:** [to be completed]

---

## Abstract

**Motivation.** Computational reaction prediction is increasingly used to explore natural products and traditional Chinese medicine (TCM), but existing workflows often separate prediction from provenance, make it difficult to determine why a candidate was generated, and provide no clear boundary between exploratory output and laboratory advice. This is particularly problematic for TCM research, where herb names, plant species, processed medicinal forms, formula versions, and source tiers can refer to different chemical starting points.

**Results.** We present Christos, a local-first reaction prediction system that combines read-only access to heterogeneous chemical data, template-based forward enumeration and retrosynthesis, condition evidence, provenance annotation, and a reproducible reporting interface. Christos resolves inputs at the level of herb, Latin species, COCONUT species, formula, or user-supplied molecules; it does not silently merge same-named formula versions and never writes to the underlying databases. The system exposes both a command-line interface and a local browser interface, with CSV/TSV ledgers and a self-contained HTML report for every run.

On a leak-controlled USPTO-50k benchmark, the selected forward configuration reaches 82.32% single-step recall on 50,016 reactions (41,173 hits; Wilson 95% CI 81.98–82.65%), compared with 55.43% for the baseline configuration. The reverse-direction template search reaches 94.74% any-hit coverage on 5,002 targets, and the multi-step planner reaches 47.67% success at depth ≤ 2 and 72.33% at depth ≤ 3 on 300 targets. In the TCM data layer, the system indexes 31,646 herb compounds, 269,105 COCONUT compounds, 12,071 formula records, and 1,526 pharmacopoeia formula entries. All 3,228 production templates in the provenance chain map back to ORD reaction identifiers. A 500-template condition audit found at least one product match for 493 templates and at least one measured condition class for 491 templates.

**Availability.** Christos is implemented in Python 3.12 with RDKit, rdchiral, SmartReact, DuckDB, and SQLite. The public distribution is deliberately split into a read-only research application and a precomputed demonstration package; arbitrary-target retrosynthesis and free-form reagent input are disabled in the public demo. The code, data cards, protocol, and reference verification snapshots are prepared for release with the manuscript.

**Keywords:** reaction prediction; retrosynthesis; natural products; traditional Chinese medicine; provenance; reproducibility; reaction templates

---

## Introduction

Template-based reaction prediction has become a practical route to exploring chemical transformations when experimental or quantum-chemical data are unavailable. RDKit provides a widely used cheminformatics toolkit (RDKit, 2024), RDChiral extracts and applies reaction templates while preserving stereochemistry (Coley et al., 2019), and systems such as AiZynthFinder and Retro* combine template libraries with search and ranking (Genheden et al., 2020; Chen et al., 2020). Benchmark resources such as USPTO-50k (Schneider et al., 2016) and PaRoutes (Genheden & Bjerrum, 2022) make it possible to compare methods, while the Open Reaction Database (ORD) provides reaction records with experimental context (Kearnes et al., 2021).

These tools are usually evaluated as prediction engines. A complementary engineering question is whether a prediction system can preserve the *history* of a result: which input record was used, which template fired, which source database supplied the compound, which conditions were observed, and whether the result is a measured precedent, a rule-based extension, or an untested hypothesis. This distinction matters when the same software is used across molecular chemistry, natural-product chemistry, and TCM research.

TCM introduces specific data-resolution problems. A Chinese herb name may correspond to a pharmacopoeia entry, a processed medicinal form, a regional alias, or a plant species. A formula may have multiple historical versions with different compositions, and a formula name must not be treated as a synonym for one fixed ingredient list. A compound may come from a herb-specific database or from a species-level natural-product collection such as COCONUT (Sorokina et al., 2021). Treating these identifiers as interchangeable can produce a chemically precise-looking output from an ambiguous input.

Christos was designed around four requirements that follow from these problems:

1. **Resolve inputs explicitly.** Herb names, processed forms, Latin species, COCONUT species, formulas, and user-supplied molecules are separate resolution paths. The system reports which path was used and which records were skipped.
2. **Keep data read-only.** The underlying SQLite databases and formula files are opened through read-only connections. A run may write reports and ledgers, but it must not alter the source data.
3. **Attach provenance to every candidate.** Every product path records the source compound, reaction template, rule name, condition evidence, round, and any uncertainty marker. The system marks candidates rather than silently deleting them.
4. **Make the public boundary explicit.** The public demonstration layer is intentionally narrower than the research engine: arbitrary-target retrosynthesis and free-form reagent input are disabled, and the demo is distributed without a database.

The present paper describes the system, its data model, its reaction and condition layers, and its evaluation. It is not a claim of clinical efficacy, a synthesis protocol, or a replacement for laboratory validation. The results are reported as software and benchmark evidence, with the limitations of template prediction and TCM source data made explicit.

## Materials and Methods

### System overview

Christos is organized as a set of composable layers rather than a single monolithic model:

| Layer | Function | Main implementation |
|---|---|---|
| Input resolution | Chinese herb, Latin species, COCONUT species, formula, or SMILES | `sources/herb.py`, `sources/coconut.py`, `sources/formula.py` |
| Reaction enumeration | Forward template application and cascade expansion | `core/smartreact_engine.py`, SmartReact |
| Retrosynthesis | Template inversion and bounded route search | `tools/retro_search.py` |
| Condition layer | Reaction-class profiles and per-template condition windows | `conditions/`, `data/mined_top_template_conditions*.json` |
| Provenance and reporting | Ledger, index, HTML report, source tags | `core/query_base.py`, `tools/make_report.py` |
| Interfaces | CLI and local browser UI | `integration/tcmai_bridge/` |

The implementation separates the chemical engine from the source-data adapters. This allows the same reaction engine to be used with herb records, species records, or a user-provided molecule set, while keeping the identity of the input source visible in the output.

### Data sources and read-only policy

The current local deployment uses the following resources:

| Resource | Role | Scale | Handling |
|---|---|---:|---|
| Herb database (`tcm.db`) | Herb names, compounds, aliases, evidence | 31,646 compounds | read-only SQLite |
| COCONUT snapshot | Species-level natural products | 269,105 valid molecules | read-only SQLite |
| Formula records | Multi-herb prescriptions and versions | 12,071 records | read-only JSON |
| Pharmacopoeia overlay | 2025 formula entries and source URLs | 1,526 entries | internal overlay, not redistributed |
| USPTO-50k | Leak-controlled benchmark | 50,016 reactions | public benchmark |
| ORD-derived templates | Reaction template source and provenance | 3,228 production templates | derived data, attributed |

The public build does not redistribute upstream raw databases. ORD-derived templates are treated as CC BY-SA 4.0, USPTO-50k is CC0 (figshare 5104873), the COCONUT curated dataset is CC0 with MIT infrastructure code, and the SmartReact template package is Apache-2.0. The local herb and formula resources remain subject to the owner's authorization and are not included in the public demonstration archive.

All SQLite connections use `mode=ro`; when a WAL-backed database cannot be opened read-only because of a missing shared-memory file, the adapter falls back to `immutable=1`, which reads a snapshot without creating or modifying sidecar files. This policy was introduced after observing that a conventional read-write `sqlite3.connect()` can create `-wal` and `-shm` files even when the caller only intends to read.

The public demo contains a small, fixed excerpt rather than the databases. It includes 100 common herbs, one selected Latin species per herb, 50 formulas, and 150 precomputed examples. The formulas are limited to 4–6 ingredients and are filtered for safety before packaging; the demo does not expose arbitrary SMILES or routes.

### Input resolution

An input is resolved in the following order:

1. exact herb or processed-herb name in the herb database;
2. a recognised alias, with the resolved canonical name reported;
3. a species name from the COCONUT species dictionary;
4. an exact formula name, with all versions retained;
5. user-supplied SMILES, when the research interface permits it.

The resolver returns both the selected records and unresolved tokens. For formulas, the system keeps the version list and selects a documented source tier by default; it does not combine same-named versions into a synthetic formula. This choice is deliberate: merging versions would create compositions that do not correspond to any historical or pharmacopoeial record.

### Forward reaction enumeration

The forward engine applies a library of reaction templates to a substrate set. Templates are grouped by reaction name and filtered by reactant category. A run can be bounded by the number of compounds per herb, the number of reaction rounds, the maximum number of substrate pairs, and a per-pair candidate cap.

The current selected configuration uses a support-filtered template pool, a per-pair cap of 32, and a substrate-compatibility prefilter. The cap matters: a very small cap can hide a correct candidate even when the template is present. For this reason the system records the pair coverage and truncation state in the run metadata rather than treating a capped result as a complete enumeration.

### Retrosynthesis

The retrosynthesis module inverts forward templates and applies them recursively to a target molecule. The search returns disconnections, precursor sets, and route-level annotations. Precursors are checked against the available termination set and are annotated as available or unavailable. The system does not infer that an unavailable precursor is impossible; it records the absence of an availability match.

The public build blocks arbitrary-target retrosynthesis by default. The research CLI requires an explicit research-mode environment flag. This is a product boundary, not a claim that the underlying search is harmless in every context.

### Condition evidence

Condition evidence is represented at two levels:

- reaction-class profiles for named reactions, with solvent, pH, temperature, catalyst, and atmosphere windows;
- per-template windows mined from ORD records, where a template is matched to a reaction record before its conditions are collected.

For the per-template layer, a top-N set of templates is evaluated against an evenly spaced ORD sample. A record contributes a condition only when the template generates a product that matches the recorded product. In the current 500-template audit, 493 templates had at least one product match and 491 had at least one condition category. The resulting windows are annotations: they do not simulate kinetics, yield, or selectivity.

### Provenance and reporting

Every candidate path in a ledger contains the product structure, source compound, source herb or species, reaction rule, round, condition activation marker, direction marker, and evidence string. The report generator converts the ledger into a single-file HTML page with the same information and optional structure drawings.

The system deliberately avoids silent scoring. A direction flag or condition marker is shown as an annotation; it does not remove the candidate from the ledger. The phrase “no evidence” is used for a candidate without a matching condition record, not as a claim that the reaction cannot occur.

### Evaluation design

The evaluation has three parts.

**Forward prediction.** The engine is run for one round on the reactants of USPTO-50k records. A hit means the recorded product appears anywhere in the candidate set; no ranking is used. We report both the baseline configuration and the selected production configuration, and use the leak-controlled library for the headline number.

**Retrosynthesis coverage.** A target is a hit if at least one disconnection produces a precursor set equal to the recorded reactant set after atom-map removal. Coverage is reported for the leak-controlled library. Multi-step success is measured on 300 targets with a bounded beam search.

**TCM resolution and provenance.** We exercise herb, species, formula, and SMILES inputs through the same interface and record the resolved source, version, unresolved tokens, and output links. The demo examples are generated from the same engine but are packaged as fixed precomputed samples so that no database is redistributed.

## Results

### Implemented data scale

The current local deployment covers:

- 31,646 herb compounds;
- 269,105 COCONUT compounds;
- 12,071 formula records;
- 1,526 pharmacopoeia formula entries;
- 3,228 production templates with ORD reaction identifiers;
- 100 herbs and 50 formulas in the public demonstration catalog.

These numbers describe the implemented data layer, not a claim of complete chemical coverage. A missing compound or formula means that the current source did not contain it, not that it does not exist.

### Forward prediction

On the leak-controlled USPTO-50k benchmark, the baseline configuration reaches 55.43% single-step recall. The selected configuration, which uses a larger support-filtered candidate pool, a per-pair cap of 32, and compatibility prefiltering, reaches **82.32%** (41,173/50,016) with a Wilson 95% confidence interval of **81.98–82.65%**.

The improvement should be read as a system-configuration result, not as evidence that the template library is universally correct. Candidate truncation, template support, and template quality all contribute. The run metadata records these settings so that the result can be reproduced and compared.

### Retrosynthesis and multi-step planning

The leak-controlled reverse search reaches **94.74%** any-hit coverage on 5,002 targets. With a beam width of four and the selected template library, end-to-end success is **47.67%** at depth ≤ 2 (143/300) and **72.33%** at depth ≤ 3 (217/300) on a fixed 300-target set. Of those 300 targets, 207 have at least one route marked usable under the system’s heuristic criterion.

The system reports the route-level source of each precursor and the availability status. It does not convert a “usable” annotation into an instruction to perform a synthesis.

### Condition and provenance coverage

Every one of the 3,228 production templates is linked to ORD reaction identifiers, and the reaction-level back-reference covers 9,177/9,177 records in the current provenance table. The 500-template condition audit produced 493 templates with at least one matching product and 491 with at least one condition category. The audit is available as a data product and does not change the default runtime library by itself.

### TCM case study

The system can resolve a herb by Chinese name, a species by Latin binomial, a formula by name and version, or a set of user SMILES. For a Glycyrrhiza example, running the current engine over 12 constituents produces a ledger with 552 candidate products and 552 provenance paths; the record includes the source compound, reaction rule, round, and condition evidence for each path. The example is an illustration of the reporting model, not a pharmacological conclusion.

Formula resolution retains all same-named versions and reports the selected source tier and unresolved tokens. In a run with multiple formula versions, the output includes the selected version and the alternatives rather than collapsing them into one composition.

### Public demonstration and safety boundary

The public demo contains 100 common herbs with one Latin species each, 50 formulas, and 150 precomputed entries. Its page has no arbitrary SMILES field, no route search, no free-form reagent input, and no purchasable-block or vendor link. The application is read-only with respect to the source database and writes only its own report and runtime directories.

This boundary is important for a system that can enumerate reaction products. The research interface remains available for controlled experiments, but the public interface deliberately presents a narrower capability set.

## Discussion

Christos is intended to make reaction prediction inspectable rather than to hide uncertainty behind a single score. Three design choices follow from that aim.

First, input resolution is explicit. In TCM data, a herb name, a processed form, a Latin binomial, and a formula version are not interchangeable identifiers. The system records the resolution path and the unresolved tokens, allowing a user to see whether a result was derived from the intended source.

Second, provenance is attached to each candidate. A template identifier, a reaction record reference, a source compound, and a condition marker make it possible to audit a result after the run. This is more useful than a bare ranked list when the underlying data are heterogeneous.

Third, the public interface is narrower than the research engine. A system that can search arbitrary targets or expose purchasable building blocks carries a different risk profile from a system that displays a fixed demonstration catalog. Christos therefore treats public availability as a product decision with explicit feature gates.

The benchmark results show that the selected configuration is materially stronger than the baseline on the frozen USPTO-50k protocol. They do not establish chemical practicality, biological activity, or clinical utility. The template engine remains dependent on the template library and on the input data; the condition layer annotates evidence and does not simulate reaction outcomes.

## Limitations

1. **Template dependence.** The forward and reverse results are bounded by the template library and by candidate truncation. A missing template can hide a correct path.
2. **No laboratory validation in this study.** Condition profiles are based on reaction records and literature; they are not a substitute for experimental validation.
3. **TCM source heterogeneity.** Herb names, processed forms, species assignments, formula versions, and source tiers can be ambiguous. The system reports unresolved tokens rather than forcing a match.
4. **Condition evidence is incomplete.** Many templates have no usable condition record. A missing condition marker means “not found in the current condition data”, not “impossible”.
5. **No universal safety guarantee.** The public build blocks high-risk interfaces, but no software filter replaces legal review, institutional controls, or responsible use.
6. **Data and licence boundaries.** Some local resources are owner-maintained and are not redistributed. The public demo uses only a small, sanitized excerpt.

## Conclusions

Christos provides a provenance-aware, read-only workflow for reaction prediction in natural-product and TCM research. It couples explicit input resolution, template-based enumeration and retrosynthesis, condition evidence, and auditable reports. On a leak-controlled USPTO-50k benchmark, the selected configuration reaches 82.32% single-step recall; reverse search reaches 94.74% coverage on 5,002 targets; and multi-step planning reaches 47.67% and 72.33% at depth ≤ 2 and ≤ 3, respectively. The system’s main contribution is not a new opaque predictor, but an inspectable pipeline in which the source, rule, condition, and uncertainty of each candidate remain visible.

## Data and code availability

The repository contains the protocol, result tables, figure sources, and runnable scripts. Upstream raw data are not redistributed. The public demonstration package is a fixed, precomputed sample; it does not contain the production databases. A repository URL and archival DOI will be inserted before submission.

## Funding

[To be completed.]

## Competing interests

The authors declare no competing interests. [To be confirmed.]

## Author contributions

[To be completed using the CRediT taxonomy.]

## Acknowledgements

[To be completed.]

## References

Journal and conference citations were checked on 2026-10-19: DOI records were resolved through Crossref, and the PMLR conference entry was checked against the official PMLR page. Software references are official project URLs. The Crossref API snapshots are stored in `reports/paper/reference_verification_20261019/`.

1. Chen, B., Li, C., Dai, H., & Song, L. (2020). Retro*: Learning retrosynthetic planning with neural guided A* search. *Proceedings of the 37th International Conference on Machine Learning*, PMLR 119, 1608–1616. https://proceedings.mlr.press/v119/chen20c.html

2. Coley, C. W., Green, W. H., & Jensen, K. F. (2019). RDChiral: An RDKit wrapper for handling stereochemistry in retrosynthetic template extraction and application. *Journal of Chemical Information and Modeling*, 59(6), 2529–2537. https://doi.org/10.1021/acs.jcim.9b00286

3. Genheden, S., & Bjerrum, E. J. (2022). PaRoutes: Towards a framework for benchmarking retrosynthesis route predictions. *Digital Discovery*, 1(4), 527–539. https://doi.org/10.1039/D2DD00015F

4. Genheden, S., Thakkar, A., Chadimová, V., Reymond, J.-L., Engkvist, O., & Bjerrum, E. J. (2020). AiZynthFinder: A fast, robust and flexible open-source software for retrosynthetic planning. *Journal of Cheminformatics*, 12, 70. https://doi.org/10.1186/s13321-020-00472-1

5. Kearnes, S. M., Maser, M. R., Wleklinski, M., Kast, A., Doyle, A. G., Dreher, S. D., Hawkins, J. M., Jensen, K. F., & Coley, C. W. (2021). The Open Reaction Database. *Journal of the American Chemical Society*, 143(45), 18820–18826. https://doi.org/10.1021/jacs.1c09820

6. Maziarz, K., Tripp, A., Liu, G., Stanley, M., Xie, S., Gaiński, P., Seidl, P., & Segler, M. (2025). Re-evaluating retrosynthesis algorithms with Syntheseus. *Faraday Discussions*, 256, 568–586. https://doi.org/10.1039/D4FD00093E

7. RDKit: Open-source cheminformatics. (2024). https://www.rdkit.org

8. Schneider, N., Stiefl, N., & Landrum, G. A. (2016). What’s What: The (nearly) definitive guide to reaction role assignment. *Journal of Chemical Information and Modeling*, 56(12), 2336–2346. https://doi.org/10.1021/acs.jcim.6b00564

9. Sorokina, M., Merseburger, P., Rajan, K., Yirik, M. A., & Steinbeck, C. (2021). COCONUT online: Collection of Open Natural Products database. *Journal of Cheminformatics*, 13, 2. https://doi.org/10.1186/s13321-020-00478-9

10. Torren-Peraire, P., Hassen, A. K., Genheden, S., Verhoeven, J., Clevert, D.-A., Preuss, M., & Tetko, I. V. (2024). Models Matter: The impact of single-step retrosynthesis on synthesis planning. *Digital Discovery*, 3(3), 558–572. https://doi.org/10.1039/D3DD00252G

11. MolecularAI. SmartReact (version 2.0.1) [Computer software]. https://github.com/MolecularAI/smartreact

---

## Figure plan

Generated English figures are available in `figures-system-20261020/en/`;
the corresponding Chinese set is in `figures-system-20261020/zh/`.
See `figures-system-20261020/README.md` for captions and source notes.

The final PeerJ submission should include:

1. A system architecture diagram showing the input resolver, source adapters, reaction engine, condition layer, and report layer.
2. A data-resolution diagram showing herb, species, formula, and SMILES paths.
3. A forward-enumeration example with the complete provenance fields.
4. A reverse-search example showing a route and availability markers.
5. A benchmark figure for forward/retrospective results; the existing `reports/paper/figures-v2/` figures can be reused only after their labels and captions are aligned with this system paper.

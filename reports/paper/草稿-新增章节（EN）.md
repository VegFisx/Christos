# 论文新增章节草稿（EN，可直接入稿打磨）

## Methods 3.x — Pharmacopoeia-anchored, provenance-first ordering

To make the ranking basis of input compounds externally verifiable, we built a predicate
chain from the *Chinese Pharmacopoeia (2025 edition)*. Each monograph's **Assay**
(含量测定) and **Identification** (鉴别) sections were extracted, curated (OCR-shape repair,
section-label rejection, multi-component "total content" sentence reconstruction), and then
linked to our compound database; every row carries the official entry URL. The chain covers
**386/491 (78.6%)** of the pharmacopoeia entries in our scope with **3,277 linked rows
(58.0%)**; a 400-row blind re-check against source text gives **93.5% supported**
(**98.7%** after excluding 5.3% known extraction artifacts; an independent re-check with a
stricter windowed matcher agreed on all 400 rows, zero disagreements). Ordering is **tiered**:
Tier-0 (Assay, quantitative limits) precedes Tier-1 (Identification), and within a tier,
**the official limit value** defines the order — no model score is involved. The behaviour is
gated behind a switch that is **off by default**, so all headline results elsewhere in this
paper are produced without it. The chain is updateable: re-running three scripts against a
new structured pharmacopoeia release regenerates the tables; a source-watcher reports upstream
changes.

## Results/Application — Case study on Glycyrrhiza (甘草)

Running the production configuration on 12 constituents of Glycyrrhiza with the ordering
switch enabled, the ledger contains **552 distinct candidate products (552 provenance paths)**;
the two compounds that the 2025 Pharmacopoeia quantifies for this herb —
**glycyrrhizic acid (≥2.0%)** and **liquiritin (≥0.50%)** — head the candidate list, each
carrying its limit and source entry. A second demonstration with a "total content" herb,
Andrographis (穿心莲), shows the curation layer recovering a four-component total sentence
("andrographolide, neoandrographolide, 14-deoxyandrographolide, dehydroandrographolide") into
linkable components. These cases illustrate the design stance of the system: generate
comprehensively, mark honestly (direction, condition evidence, provenance), never delete or
silently rank, and expose every ordering basis to the user. The same chain also serves a
single-herb-a-day usage pattern: after each batch the system writes a one-page HTML report
and a run ledger entry, so results remain auditable without expert supervision.

## Limitations (honest)

1. **No human blind evaluation.** We could not obtain independent expert annotators; we
   substitute objective proxy criteria plus a curated gold check (93.5%/98.7% supported on
   400 rows) and report this limitation explicitly.
2. **Heuristic usability.** Route-usability verdicts rely on residue/enlargement/inert/absurd
   heuristics with bounded MCS matching; timeouts persist (documented), which may make
   borderline verdicts machine-dependent.
3. **ORD-internal evaluation.** Templates are mined from, and evaluated on, community-standard
   ORD/USPTO-derived data; we controlled evaluation leakage (75,718 leaked rows removed;
   leak-free numbers reported) but external cross-database evaluation remains future work;
   an automated-retrosynthesis baseline comparison is pending.
4. **Pharmacopoeia chain is a downstream layer, not an oracle.** It depends on a third-party
   structured version of the standard; 21% of in-scope entries are not yet linked
   (mineral/aggregate/tail categories), and total-content sentences required bespoke
   reconstruction.
5. **Conditions are marked, not simulated.** Temperature/solvent/reagent windows are annotated
   with evidence strength; we do not claim kinetic, yield, or selectivity prediction.
6. **Scope discipline.** The system is a general reaction engine; herb-specific scenarios
   (e.g., decoction chemistry) are intentionally excluded from this version.

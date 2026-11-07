# arXiv submission metadata (fill before upload)

## Title

Christos: a provenance-aware, read-only reaction prediction system for natural-product and traditional Chinese medicine research

## Authors

[Author 1 — to be completed]  
[Author 2 — to be completed, if applicable]

## Affiliations

[Affiliation 1 — to be completed]  
[Affiliation 2 — to be completed, if applicable]

## Corresponding author

[Name and email — to be completed]

## Abstract

Computational reaction prediction is increasingly used to explore natural products and traditional Chinese medicine (TCM), but existing workflows often separate prediction from provenance, make it difficult to determine why a candidate was generated, and provide no clear boundary between exploratory output and laboratory advice. We present Christos, a local-first reaction prediction system that combines read-only access to heterogeneous chemical data, template-based forward enumeration and retrosynthesis, condition evidence, provenance annotation, and a reproducible reporting interface. Christos resolves inputs at the level of herb, Latin species, COCONUT species, formula, or user-supplied molecules; it does not silently merge same-named formula versions and never writes to the underlying databases. On a leak-controlled USPTO-50k benchmark, the selected forward configuration reaches 91.69% single-step recall on 50,016 reactions (45,862 hits; Wilson 95% CI 91.45–91.93%), compared with 58.73% for the baseline configuration. The reverse-direction template search reaches 94.74% any-hit coverage on 5,002 targets, and the multi-step planner reaches 47.67% success at depth <= 2 and 72.33% at depth <= 3 on 300 targets. In the TCM data layer, the system indexes 31,646 herb compounds, 269,105 COCONUT compounds, 12,071 formula records, and 1,526 pharmacopoeia formula entries. All 3,228 production templates in the provenance chain map back to ORD reaction identifiers. A 500-template condition audit found at least one product match for 493 templates and at least one measured condition class for 491 templates. The system is implemented with RDKit, rdchiral, SmartReact, DuckDB and SQLite; the public build deliberately disables arbitrary-target retrosynthesis and free-form reagent input.

## Comments

[To be completed: page count, figure count, software URL, and optional journal-preprint note.]

## Category suggestions

- Primary candidate: `q-bio.QM` (Quantitative Methods)
- Cross-list candidate: `cs.LG` or `cs.SE` (choose only if the final scope fits)

Confirm category availability and any endorsement requirement in the arXiv account.

## License

[Choose the arXiv license after reading the current options. Do not assume a license on the author's behalf.]

## Data/code availability

- Repository URL: [to be inserted]
- Archived DOI: [to be inserted]
- Public demo: a fixed precomputed package; production databases are not redistributed.

## Submission checklist

- [ ] Replace every author/affiliation/email placeholder in `manuscript.md`.
- [ ] Replace funding, competing-interest, contribution and acknowledgement placeholders.
- [ ] Insert the public repository URL and archival DOI.
- [ ] Confirm the final title and abstract in arXiv metadata.
- [ ] Confirm category and endorsement.
- [ ] Choose the arXiv license.
- [ ] Recompile `manuscript.pdf` from the final Markdown.
- [ ] Verify all five figures are present and captions match the final text.
- [x] Verify 20 DOI references (Crossref/PubMed metadata), one PMID-only article, and the PMLR/software/data-source URLs (2026-10-30).


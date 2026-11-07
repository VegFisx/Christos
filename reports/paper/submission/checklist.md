# PeerJ submission checklist

Generated 2026-10-19 from `paper-draft-en-20261019.md`. Package contents: `manuscript-v3.docx`, `manuscript-v3.pdf` (older `manuscript.docx` is locked by Word), `figures/` (7 PNG at 300 dpi + 7 vector PDF), `figure_legends.md`, `cover_letter.md`.

## 1. Blanks only you can fill

| Field | Where | Status |
|---|---|---|
| Author names, order, ORCID | manuscript title page; submission system | ⬜ |
| Affiliations and corresponding-author email | title page | ⬜ |
| Funding statement (or "no funding") | `## Funding` | ⬜ |
| Competing interests (confirm "none") | `## Competing interests` | ⬜ |
| CRediT author contributions | `## Author contributions` | ⬜ |
| Acknowledgements | `## Acknowledgements` | ⬜ |
| Ethics statement | not applicable (no human/animal subjects) — confirm | ⬜ |

## 2. Current manuscript facts (measured)

| Item | Value |
|---|---|
| Main text (Introduction → Conclusions) | 3,625 words |
| Total up to References | 3,966 words |
| Abstract | 297 words (PeerJ limit 300 for Research Articles — within limit) |
| Figures | 7 |
| Tables | 6 |
| References | 10, all with DOI verified via Crossref/PMLR on 2026-10-19 |
| Pages (PDF) | see `manuscript-v3.pdf` |

## 3. PeerJ-specific requirements

- [x] **Abstract ≤ 300 words** — trimmed to 297 (verified).
- [ ] Figures uploaded as separate files (PNG/PDF supplied), not embedded only in the Word file.
- [ ] Figure legends included with the figure files or at the end of the manuscript.
- [ ] References in PeerJ (author–date) style — already formatted; check journal punctuation at proof stage.
- [ ] Data availability statement — present; add repository DOI/URL once the release package is public.
- [ ] Trial/registration: not applicable.
- [ ] Suggested reviewers (optional; 3–5 names, no recent co-authors).

## 4. Scientific gaps that reviewers may press

1. **No expert blind annotation.** The annotation kit (200 cuts, single-file HTML) exists but was never run. Either run it before submission or state it as a limitation (currently stated).
2. **No learned-retrosynthesis baseline.** The paper positions itself as evaluation/quality work, not SOTA; the cover letter says so explicitly. Consider adding one sentence in Discussion to pre-empt the objection.
3. **ORD-internal evaluation.** Cross-database evaluation is future work; already declared.
4. **The truncation mechanism is inferred, not instrumented.** Stated as inference in Results; a reviewer may ask for a per-pair rank histogram. If you want, we can produce it from existing artefacts.

## 5. Version alignment before submission

- Manuscript reports the frozen v1.0.0 result set; the public code is v0.9.0-beta.
- Either bump the public version to match, or keep the "Supplementary note: version alignment" paragraph (currently included).
- Do not mix v1.0.0 numbers with v0.9.0-beta screenshots in the same submission.

## 6. Files

| File | Purpose |
|---|---|
| `manuscript.docx` / `.pdf` | main manuscript (PDF for review) |
| `figures/fig1_concentration.png` | Figure 1 |
| `figures/fig2_blacklist.png` | Figure 2 |
| `figures/fig3_coverage_topk.png` | Figure 3 |
| `figures/fig4_composition.png` | Figure 4 |
| `figures/fig5_timeout.png` | Figure 5 |
| `figures/fig6_forward_class.png` | Figure 6 |
| `figures/fig7_truncation_multistep.png` | Figure 7 |
| `figure_legends.md` | captions |
| `cover_letter.md` | cover letter draft |

# Reference verification snapshots

The eight DOI-bearing references in `Christos-system-paper-draft-20261019.md` were resolved via the Crossref API on 2026-10-19:

- 10.1021/acs.jcim.6b00564
- 10.1021/acs.jcim.9b00286
- 10.1021/jacs.1c09820
- 10.1039/D2DD00015F
- 10.1039/D3DD00252G
- 10.1039/D4FD00093E
- 10.1186/s13321-020-00472-1
- 10.1186/s13321-020-00478-9

All eight returned HTTP 200 and matching title/year/journal metadata. The raw Crossref JSON responses are stored in this directory.

The two non-DOI official references are:

- Chen et al. 2020, PMLR 119: https://proceedings.mlr.press/v119/chen20c.html
- RDKit and SmartReact: official project URLs listed in the manuscript.

The public GitHub/PMLR pages may be slow or rate-limited from this machine; they were not used to replace Crossref metadata for the DOI-bearing papers.

# Reference verification · 2026-10-29

This directory records the external-source checks used to complete the data
card and the current English/Chinese manuscripts. The network request metadata
and SHA-256 hashes are in `download_manifest.json`.

Verified DOI records:

- `10.1038/s41589-022-01131-2` — TDC, *Nature Chemical Biology* 18(10):1033–1036.
- `10.1093/nar/gkag1041` — CTD update 2027, published online 2026-10-23.
- `10.1021/acs.chemrestox.0c00264` — Tox21 10K compound library, 34(2):189–216.
- `10.1021/acs.chemrestox.6b00135` — ToxCast chemical landscape, 29(8):1225–1251.
- `10.1016/j.medj.2025.100642` — OnSIDES, *Med* 6(7):100642.

Non-DOI sources:

- TDC ADMET Group: <https://tdcommons.ai/benchmark/admet_group/overview/>
- US EPA Tox21 program page:
  <https://www.epa.gov/chemical-research/toxicology-testing-21st-century-tox21>
- OnSIDES v3.1.1 release:
  <https://github.com/tatonetti-lab/onsides/releases/tag/v3.1.1>
- Chinese Pharmacopoeia 2025 structured source:
  <https://github.com/cliviali/Independent-KBs>, commit
  `63cfd6a678b63232bbd49b501546dd450a29a1a2`.

Important provenance limits:

- The local ADMET cache does not store a TDC release tag. Its fields identify
  the TDC ADMET Group, but the exact extraction snapshot is unknown.
- The local cache also does not store a separate Tox21/ToxCast release tag.
- The `Independent-KBs` repository declares no repository-level license.
  Its contents therefore remain internal-only until the maintainer provides
  explicit redistribution terms.

All fetched pages, API responses, and their hashes are retained here for
auditability. Upstream raw datasets and papers are not redistributed.

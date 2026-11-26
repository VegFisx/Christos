# Formula library coverage (2026-11-24)

Read-only audit: `tools/audit_formula_db_coverage.py`

| item | value |
|---|---:|
| formula rows | 12,075 |
| rows parsing to >=1 ingredient | 12,070 |
| ingredient mentions | 119,067 |
| mentions resolved to tcm.db herbs | 95,950 (81.6%) |
| formulas with every ingredient resolved | 4,321 / 12,070 (35.8%) |
| formulas with zero ingredients resolved | 479 |

The unresolved tail is dominated by synonyms/processing names (`生地`, `黄耆`,
`麦门冬`, `制何首乌`, `桂心`), excipients (`硬脂酸镁`, `糊精`), and parenthetical
annotation fragments. This is an **herb-name resolution lower bound**, not a
chemistry or efficacy validation.

Full rows: `reports/formula_db_coverage_20261124.json`.

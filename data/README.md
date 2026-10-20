# Data layout

Christos reads its chemical tables from two SQLite databases plus a handful of
derived JSON/CSV files.  **None of them ship with this repository.**

## Why the full tables are not here

The herbal database is assembled from several third-party pharmacopoeia and
natural-product compilations, each with its own redistribution terms.  The
natural-product database is a local mirror of COCONUT.  Republishing a merged
copy would mean republishing other people's curated data under a licence we do
not hold.  Building the tables from the upstream sources is the supported path.

The demo catalogue in `demo/` was reduced to 100 herbs and 50 formulas and
carries no per-compound provenance that would identify the upstream releases.

## Expected directory

```
<data dir>/
├── tcm.db                  # herbal compounds, herbs, formulas
├── coconut.db              # natural-product structures
├── formula_db.json         # formula records
└── herb_aliases_map.json   # reviewed alias -> canonical name table
```

Point the engine at it with:

```
set CHRISTOS_DB_DIR=D:\path\to\your\data
```

## Read-only guarantee

Every connection in this codebase opens the database through a read-only URI:

```python
sqlite3.connect("file:/path/to/tcm.db?mode=ro", uri=True)
```

`tools/tcm_ro.py` is the single wrapper for that.  If you add code that touches
the databases, use it instead of calling `sqlite3.connect` directly.  A
read-only connection cannot create `-wal` or `-shm` sidecar files, which is what
keeps a live crawler or another writer safe.

## Demo catalogue

| File | Contents |
|---|---|
| `demo/demo_catalog.json` | 100 herbs, 50 formulas, display metadata |
| `demo/demo_predictions.json` | Pre-computed entries so the UI can be explored offline |

The demo files are illustrative only.  They are not a benchmark set and must
not be used to compute accuracy figures.

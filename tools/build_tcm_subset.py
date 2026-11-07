"""Build a small, redistributable subset of ``tcm.db``.

The subset keeps only the rows a reviewer needs to re-run the TCM-side
validations: the herbs used in the paper, their compound links, and the
compounds themselves (plus any compound referenced by a recorded result).

What is deliberately **not** copied:

* ``crawl_progress`` / ``ingredient_progress`` — internal crawl bookkeeping,
  not part of any scientific claim.
* any herb or compound row outside the validation set.

Source database is opened read-only (``mode=ro``); nothing is written back.

Usage::

    python -I tools/build_tcm_subset.py --out data/tcm_subset.db
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
SRC_DB = "D:/TCMAI/tcm.db"

# Herbs used by the recorded validations (literature, processed-herb, formulas,
# whole-herb). Names are the ones the scripts pass to ``compounds_of_herb``.
HERBS = [
    # formulas and whole-herb runs
    "甘草", "人参", "附子", "干姜", "黄芩", "白芍", "大枣",
    "桂枝", "生姜", "麻黄", "苦杏仁", "柴胡", "半夏",
    # processed-herb cases
    "槟榔", "苍耳子", "狼毒", "何首乌",
]

# Seeds are addressed by ingredient id in the recorded cases; keep them even
# when the herb they belong to carries the compound under a different name.
SEED_IDS = [
    "HBIN027729",   # ginsenoside Rb1
    "HBIN016699",   # arecoline
    "HBIN019719",   # CATR
    "HBIN031562",   # JNB
    "HBIN014582",   # aconitine
    "HBIN003908",   # THSG
    "HBIN003457",   # Rg3 (bridge)
    "HBIN027756",   # Rg5
    "HBIN027782",   # Rk1
    "HBIN028561",   # guvacoline
]

# Documented targets that are products rather than components of the herbs
# above; without them a recorded case can be read but not re-run.
EXTRA_TARGETS = [
    "Guvacoline", "Benzoylaconine", "Benzoylmesaconine", "Benzoylhypaconine",
    "Aconine", "Glycyrrhetinic acid", "Prunasin", "Benzaldehyde",
    "Cinnamic acid", "Liquiritigenin", "Paeoniflorigenone",
    "Saikogenin d", "Saikogenin f", "Baicalein", "Wogonin", "Quercetin",
    "Isoliquiritigenin", "Formononetin",
]

# Tables worth copying; the crawl-progress tables are excluded on purpose.
TABLES = ["herbs", "compounds", "herb_compound"]


def ro_connect(path: str = SRC_DB) -> sqlite3.Connection:
    uri = "file:%s?mode=ro" % path
    try:
        con = sqlite3.connect(uri, uri=True)
        con.execute("SELECT 1")
        return con
    except sqlite3.OperationalError:
        return sqlite3.connect("file:%s?immutable=1" % path, uri=True)


def ddl(con: sqlite3.Connection, table: str) -> str:
    row = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not row or not row[0]:
        raise SystemExit("源库没有表 %s" % table)
    return row[0]


def referenced_ids(dirs) -> set:
    """Compound ids referenced by recorded validation output.

    Scans result JSONs so that targets which are not a component of any kept
    herb (e.g. a paozhi product) still resolve in the subset.
    """
    ids = set()
    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.json")):
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                continue
            for tok in text.replace('"', " ").replace(",", " ").split():
                if tok.startswith("HBIN") and len(tok) == 11:
                    ids.add(tok)
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(STAGE / "data" / "tcm_subset.db"))
    ap.add_argument("--src", default=SRC_DB)
    ap.add_argument("--refs", nargs="*", default=[str(STAGE / "reports")])
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    src = ro_connect(args.src)
    cur = src.cursor()

    herb_ids = []
    for name in HERBS:
        rows = cur.execute("SELECT herb_id FROM herbs WHERE name_cn = ?", (name,)).fetchall()
        if not rows:
            print("   [warn] 库里没有药材 %s，跳过" % name)
        herb_ids.extend(r[0] for r in rows)
    herb_ids = sorted(set(herb_ids))

    ph = ",".join("?" * len(herb_ids))
    links = cur.execute(
        "SELECT herb_id, ingredient_id, match_level, match_source FROM herb_compound "
        "WHERE herb_id IN (%s)" % ph, herb_ids
    ).fetchall()
    comp_ids = sorted({r[1] for r in links} | referenced_ids(args.refs) | set(SEED_IDS))
    for name in EXTRA_TARGETS:
        row = cur.execute(
            "SELECT ingredient_id FROM compounds WHERE lower(name_en) = lower(?)", (name,)
        ).fetchone()
        if row:
            comp_ids.append(row[0])
        else:
            print("   [warn] 库里没有目标化合物 %s，跳过" % name)
    comp_ids = sorted(set(comp_ids))
    phc = ",".join("?" * len(comp_ids))

    dst = sqlite3.connect(str(out))
    for t in TABLES:
        dst.execute(ddl(src, t))

    herb_cols = [r[1] for r in cur.execute("PRAGMA table_info(herbs)")]
    comp_cols = [r[1] for r in cur.execute("PRAGMA table_info(compounds)")]
    dst.executemany(
        "INSERT INTO herbs (%s) VALUES (%s)" % (",".join(herb_cols), ",".join("?" * len(herb_cols))),
        cur.execute("SELECT %s FROM herbs WHERE herb_id IN (%s)"
                    % (",".join(herb_cols), ph), herb_ids).fetchall(),
    )
    dst.executemany(
        "INSERT INTO compounds (%s) VALUES (%s)" % (",".join(comp_cols), ",".join("?" * len(comp_cols))),
        cur.execute("SELECT %s FROM compounds WHERE ingredient_id IN (%s)"
                    % (",".join(comp_cols), phc), comp_ids).fetchall(),
    )
    dst.executemany(
        "INSERT INTO herb_compound (herb_id, ingredient_id, match_level, match_source) "
        "VALUES (?,?,?,?)", links,
    )
    dst.commit()

    n_herbs = dst.execute("SELECT COUNT(*) FROM herbs").fetchone()[0]
    n_comps = dst.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    n_links = dst.execute("SELECT COUNT(*) FROM herb_compound").fetchone()[0]
    dst.execute("VACUUM")
    dst.close()
    src.close()

    mb = out.stat().st_size / 1024 / 1024
    print("写出 %s" % out)
    print("  herbs         %d" % n_herbs)
    print("  compounds     %d" % n_comps)
    print("  herb_compound %d" % n_links)
    print("  大小 %.2f MB" % mb)
    print("  未复制：crawl_progress / ingredient_progress（内部爬取记录），"
          "以及验证集以外的药材与成分")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

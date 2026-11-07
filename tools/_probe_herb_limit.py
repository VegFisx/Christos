# -*- coding: utf-8 -*-
r"""一次性探针：查「每味取 N 个成分」背后到底取谁、截掉谁（只读 tcm.db）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tcm_ro import open_db          # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VALID = ("c.smiles IS NOT NULL AND c.smiles != '' AND LENGTH(c.smiles) > 3 "
         "AND c.smiles NOT IN ('Not','not','None','none','N/A','NA','nan','NaN')")
ORDER = "CASE hc.match_level WHEN 'marker' THEN 0 ELSE 1 END, c.mol_weight DESC"


def probe(herb: str) -> None:
    with open_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT herb_id, name_cn FROM herbs WHERE name_cn = ?", (herb,))
        ids = [r[0] for r in cur.fetchall()]
        print("=" * 88)
        print("药材 %s：herb_id=%s" % (herb, ids))
        if not ids:
            return
        ph = ",".join("?" * len(ids))
        n_all = cur.execute("SELECT COUNT(*) FROM herb_compound hc WHERE hc.herb_id IN (%s)"
                            % ph, ids).fetchone()[0]
        n_valid = cur.execute(
            "SELECT COUNT(*) FROM herb_compound hc JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
            "WHERE hc.herb_id IN (%s) AND %s" % (ph, VALID), ids).fetchone()[0]
        n_marker = cur.execute(
            "SELECT COUNT(*) FROM herb_compound hc JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
            "WHERE hc.herb_id IN (%s) AND %s AND hc.match_level='marker'" % (ph, VALID),
            ids).fetchone()[0]
        print("全部关联行=%d · 通过SMILES过滤=%d · 其中 marker=%d" % (n_all, n_valid, n_marker))

        rows = cur.execute(
            "SELECT c.name_en, c.mol_weight, hc.match_level "
            "FROM herb_compound hc JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
            "WHERE hc.herb_id IN (%s) AND %s ORDER BY %s LIMIT 18" % (ph, VALID, ORDER),
            ids).fetchall()
        print("--- 排序后前 18（marker 优先，其次分子量降序）---")
        for i, (nm, mw, lv) in enumerate(rows, 1):
            print("%3d  MW=%8.2f  %-8s %s" % (i, mw or -1.0, lv or "-", (nm or "")[:44]))

        # 完整排序表（含 SMILES，用于复刻 Python 侧的"按 SMILES 去重"）
        full = cur.execute(
            "SELECT c.name_en, c.mol_weight, hc.match_level, "
            "COALESCE(NULLIF(c.isomeric_smiles,''), c.smiles) "
            "FROM herb_compound hc JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
            "WHERE hc.herb_id IN (%s) AND %s ORDER BY %s" % (ph, VALID, ORDER),
            ids).fetchall()
        dedup = []
        seen = set()
        for nm, mw, lv, iso in full:
            key = (iso or "").strip()
            if key and key not in seen:
                seen.add(key)
                dedup.append((nm, mw))
        print("通过过滤 %d 行 -> 按 SMILES 去重后 %d 个不同分子" % (len(full), len(dedup)))
        print("若 limit=12：行数 12 行 -> 去重后只剩 %d 个不同分子（前 %d 名的名单）："
              % (len(dedup[:12]), 12))
        for i, (nm, mw) in enumerate(dedup[:12], 1):
            print("   %2d  MW=%8.2f  %s" % (i, mw or -1.0, (nm or "")[:52]))

        mws = [mw for nm, mw in dedup if mw]
        if len(mws) >= 12:
            print("前 12 个（去重后）MW 范围：%.1f ~ %.1f" % (min(mws[:12]), max(mws[:12])))
            rest = mws[12:]
            if rest:
                print("其余 %d 个被 limit 截掉，MW 范围：%.1f ~ %.1f（中位 %.1f）"
                      % (len(rest), min(rest), max(rest), sorted(rest)[len(rest) // 2]))
            else:
                print("没有可截的（不足 12 个）")


def main() -> int:
    # 全库规模概览：每味药材的有效成分数（前 8 名 + 中位数）
    with open_db() as conn:
        counts = conn.execute(
            "SELECT h.name_cn, COUNT(*) AS n FROM herb_compound hc "
            "JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
            "JOIN herbs h ON hc.herb_id=h.herb_id "
            "WHERE %s GROUP BY hc.herb_id ORDER BY n DESC" % VALID).fetchall()
    ns = [n for _, n in counts]
    print("全库药材数=%d · 每味有效成分数 中位=%d p90=%d 最大=%d（%s）"
          % (len(ns), sorted(ns)[len(ns) // 2], sorted(ns)[int(0.9 * len(ns))],
             max(ns), counts[0][0]))
    print("成分最多的前 8 味：", ", ".join("%s %d" % (h, n) for h, n in counts[:8]))
    for herb in ("甘草", "黄芪"):
        probe(herb)
    return 0


if __name__ == "__main__":
    sys.exit(main())

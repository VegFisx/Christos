# -*- coding: utf-8 -*-
r"""一次性探针：tcm.db 里"成分等级/marker"的来源与结构（只读）。"""
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


def main() -> int:
    with open_db() as conn:
        cur = conn.cursor()
        # 1) 全库表清单
        tabs = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        print("表清单（%d）：%s" % (len(tabs), ", ".join(tabs)))

        # 2) herb_compound 的列与 match_level 分布
        cols = [r[1] for r in cur.execute("PRAGMA table_info(herb_compound)")]
        print("herb_compound 列：%s" % cols)
        dist = cur.execute(
            "SELECT COALESCE(match_level,'(空)'), COUNT(*) FROM herb_compound "
            "GROUP BY 1 ORDER BY 2 DESC").fetchall()
        print("match_level 全库分布：")
        for k, n in dist:
            print("   %-16s %8d" % (k, n))

        # 3) compounds 表有没有"含量/数量"之类字段
        ccols = [r[1] for r in cur.execute("PRAGMA table_info(compounds)")]
        print("compounds 列：%s" % ccols)
        iccols = [r[1] for r in cur.execute("PRAGMA table_info(ingredients)")] \
            if any(t == "ingredients" for t in tabs) else []
        if iccols:
            print("ingredients 列：%s" % iccols)

        # 4) 含"含量/content/percent/浓度"字样的列（全库扫一遍）
        hits = []
        for t in tabs:
            for r in cur.execute("PRAGMA table_info(%s)" % t):
                name = str(r[1]).lower()
                if any(w in name for w in ("content", "percent", "conc", "amount", "dose", "含量")):
                    hits.append((t, r[1]))
        print("名字像'含量'的列：%s" % (hits if hits else "无"))

        # 5) herb_compound 里有没有来源列（谁写进来的）
        #   先看该表全部列名，若没有 source 列就说明来源没记在行上
        # 6) marker 集中在几味药：看 marker 行数 top10 药材 + marker 覆盖药材数
        n_marker = cur.execute(
            "SELECT COUNT(*) FROM herb_compound WHERE match_level='marker'").fetchone()[0]
        n_herbs_marker = cur.execute(
            "SELECT COUNT(DISTINCT herb_id) FROM herb_compound WHERE match_level='marker'"
        ).fetchone()[0]
        n_herbs_all = cur.execute("SELECT COUNT(DISTINCT herb_id) FROM herb_compound").fetchone()[0]
        print("marker 行=%d · 有 marker 的药材=%d / 全部有成分的药材=%d"
              % (n_marker, n_herbs_marker, n_herbs_all))
        top = cur.execute(
            "SELECT h.name_cn, COUNT(*) FROM herb_compound hc "
            "JOIN herbs h ON hc.herb_id=h.herb_id WHERE hc.match_level='marker' "
            "GROUP BY hc.herb_id ORDER BY 2 DESC LIMIT 10").fetchall()
        print("marker 数最多的药材：%s" % ", ".join("%s %d" % (a, b) for a, b in top))

        # 7) 抽 3 味药看 marker 长啥样（名字+SMILES 有无）
        for herb in ("甘草", "黄芪", "人参"):
            rows = cur.execute(
                "SELECT c.name_en, c.mol_weight FROM herb_compound hc "
                "JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
                "JOIN herbs h ON hc.herb_id=h.herb_id "
                "WHERE h.name_cn=? AND hc.match_level='marker' "
                "ORDER BY c.mol_weight DESC LIMIT 6", (herb,)).fetchall()
            print("  %s marker 样例：%s" % (herb,
                  "; ".join("%s(MW %.0f)" % (n or "?", m or 0) for n, m in rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
r"""一次性探针：tcm.db compounds.alias 里有没有中文名（决定能否自动做中文→库映射）。"""
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

SQL = """SELECT c.name_en, c.alias FROM herb_compound hc
JOIN compounds c ON hc.ingredient_id = c.ingredient_id
JOIN herbs h ON hc.herb_id = h.herb_id
WHERE h.name_cn = ? AND (c.alias LIKE ? OR c.alias LIKE ?) LIMIT 8"""


def main() -> int:
    with open_db() as conn:
        print("--- 甘草里 alias 含「甘草」或「苷」的前 8 行 ---")
        for en, al in conn.execute(SQL, ("甘草", "%甘草%", "%苷%")):
            print("   %-32s | %s" % (en or "?", (al or "")[:70]))
        n1 = conn.execute("SELECT COUNT(*) FROM compounds WHERE alias LIKE ?", ("%苷%",)).fetchone()[0]
        n2 = conn.execute("SELECT COUNT(*) FROM compounds WHERE alias IS NOT NULL AND alias != ''").fetchone()[0]
        print("全库 alias 含「苷」的行数 = %d；alias 非空 = %d" % (n1, n2))
        print("--- 随机看 6 行 alias 样例 ---")
        for en, al in conn.execute(
                "SELECT name_en, alias FROM compounds WHERE alias IS NOT NULL AND alias != '' LIMIT 6"):
            print("   %-32s | %s" % (en or "?", (al or "")[:70]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

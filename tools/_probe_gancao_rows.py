# -*- coding: utf-8 -*-
r"""一次性：看甘草家族的 herbs 行（拼音/英文/拉丁/别名）。"""
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
        rows = cur.execute(
            "SELECT herb_id, name_cn, pinyin, name_en, latin, alias FROM herbs "
            "WHERE name_cn LIKE ? ORDER BY LENGTH(name_cn) LIMIT 12", ("%甘草%",)).fetchall()
        for r in rows:
            print(" | ".join(str(x) for x in r))
    return 0


if __name__ == "__main__":
    sys.exit(main())

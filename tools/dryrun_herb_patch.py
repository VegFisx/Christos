# -*- coding: utf-8 -*-
r"""补库补丁的干跑验证：在 tcm.db 的副本上应用补丁，证明它真能装上。

全程不碰原库：
  1. 用 SQLite 的 backup API 把 D:\TCMAI\tcm.db（只读打开）备份到临时文件；
  2. 在副本上执行 data\patch_missing_herbs\patch_tcmdb.sql；
  3. 核对 PATCH 行数、抽样字段，再执行 rollback_tcmdb.sql 验证可干净回滚；
  4. 临时副本用完即删（临时文件，不是产物）。

用法：``python tools\dryrun_herb_patch.py``
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
SRC = "file:D:/TCMAI/tcm.db?mode=ro"
PATCH = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    STAGE / "data" / "patch_missing_herbs" / "patch_tcmdb.sql")
ROLLBACK = Path(sys.argv[2]) if len(sys.argv) > 2 else (
    PATCH.parent / ("rollback_" + PATCH.name.replace("patch_", "", 1)))
EXPECT = int(sys.argv[3]) if len(sys.argv) > 3 else 52


def main() -> int:
    if not PATCH.exists():
        print("★ 缺补丁文件：%s（先跑 tools\\build_missing_herbs_patch.py）" % PATCH)
        return 1
    ok = False
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / "tcm_copy.db"
        src = sqlite3.connect(SRC, uri=True)
        out = sqlite3.connect(str(dst))
        src.backup(out)                    # SQLite 官方备份 API：一致性快照
        out.close()
        src.close()
        print("  副本已建：%s（%.1f MB）" % (dst.name, dst.stat().st_size / 1e6))
        con = sqlite3.connect(str(dst))
        before = con.execute("SELECT COUNT(*) FROM herbs").fetchone()[0]
        con.executescript(PATCH.read_text(encoding="utf-8"))
        after = con.execute("SELECT COUNT(*) FROM herbs").fetchone()[0]
        n_patch = con.execute(
            "SELECT COUNT(*) FROM herbs WHERE herb_id LIKE 'PATCH%'").fetchone()[0]
        sample = con.execute(
            "SELECT herb_id, name_cn, latin, use_part FROM herbs "
            "WHERE herb_id LIKE 'PATCH%' ORDER BY herb_id LIMIT 3").fetchall()
        print("  herbs 行数：%d → %d（新增 %d）" % (before, after, after - before))
        print("  PATCH 行数 = %d（期望 %d）" % (n_patch, EXPECT))
        for r in sample:
            print("    %s ｜ %s ｜ 拉丁=%s ｜ 部位=%s" % (r[0], r[1], r[2] or "—", r[3] or "—"))
        con.executescript(ROLLBACK.read_text(encoding="utf-8"))
        rolled = con.execute("SELECT COUNT(*) FROM herbs").fetchone()[0]
        n_left = con.execute(
            "SELECT COUNT(*) FROM herbs WHERE herb_id LIKE 'PATCH%'").fetchone()[0]
        print("  回滚后：herbs %d（原 %d）｜ 残留 PATCH 行 %d" % (rolled, before, n_left))
        con.close()
        ok = (n_patch == EXPECT and (after - before) == EXPECT
              and rolled == before and n_left == 0)
    print()
    print("  结论：%s（原库全程只读，一个字节未改）"
          % ("补丁可安全应用 + 可干净回滚 ✓" if ok else "★ 有不符项"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

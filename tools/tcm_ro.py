# -*- coding: utf-8 -*-
r"""tcm_ro.py —— 对 TCMAI 数据库的**只读**访问（`db_utils.open_db` 的替代，用法完全一样）。

为什么要它（2026-10-13）：
  * 用户的 VS Code 里**正在跑爬虫**在建方剂库；`AGENTS.md` 第四节要求「爬虫运行期间不要打开 tcm.db；
    必须访问时一律用只读 URI」。
  * `D:\TCMAI\src\db_utils.py` 的 `open_db()` 是 `sqlite3.connect(str(db_path))` —— **读写**打开。
  * 本模块提供同签名的 `open_db()`（contextmanager，yield 连接），但走 `file:<path>?mode=ro`。
    调用方把 `from db_utils import open_db` 换成 `from tcm_ro import open_db` 即可，其余代码一行不改。

自检：`python tools/tcm_ro.py`（会尝试写一次，必须失败）。
"""
from __future__ import annotations

import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

TCM_DB = Path(r"D:\TCMAI\tcm.db")
COCONUT_DB = Path(r"D:\TCMAI\coconut.db")


@contextmanager
def open_db(db_path=TCM_DB):
    """只读打开（抛错而不是静默降级成读写）。

    ★ 2026-10-14（第四十三轮）：某些环境（如沙箱里 `D:\\TCMAI` 不可写、且 WAL 库当前没有 -shm）
    下 `mode=ro` 会因"无法创建/映射 -shm"直接失败。此时**回退到 immutable=1**：
    仍然是纯只读（SQLite 不加锁、不写任何文件），只是把库当作"不会变化的快照"——
    若爬虫此刻正在写，读到的可能是略旧的快照（不伤库；也绝不会写库）。回退会打警告，不静默。
    """
    p = Path(db_path).resolve()
    uri = "file:" + p.as_posix()
    try:
        conn = sqlite3.connect(uri + "?mode=ro", uri=True)
        conn.execute("SELECT 1")          # sqlite3.connect 是懒的，要真跑一条才发现打不开
    except sqlite3.OperationalError as ex:
        print(f"   [warn] tcm_ro: mode=ro 打不开（{ex}）→ 回退 immutable=1（纯只读快照）")
        conn = sqlite3.connect(uri + "?immutable=1", uri=True)
    try:
        yield conn
    finally:
        conn.close()


def _selftest() -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    with open_db() as conn:
        n = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    print("只读读取 compounds 行数 = %d" % n)
    try:
        with open_db() as conn:
            conn.execute("CREATE TABLE _ro_probe(x INTEGER)")
        print("FAIL：只读连接竟然写成功了")
        return 1
    except sqlite3.OperationalError as ex:
        print("PASS：写入被拒（%s）" % ex)
        return 0


if __name__ == "__main__":
    sys.exit(_selftest())

def use_readonly():
    r"""把 `D:\TCMAI\src\db_utils.open_db` 换成只读版。

    给那些**直接用 `find_compounds` / `find_herbs`** 的脚本用：这些函数内部调的是
    模块级的 `open_db`，所以只要在这里换掉它，整条链就都是只读的。
    """
    import sys as _sys
    _src = Path(r"D:\TCMAI\src")
    if _src.is_dir() and str(_src) not in _sys.path:
        _sys.path.append(str(_src))
    import db_utils
    db_utils.open_db = open_db
    return db_utils

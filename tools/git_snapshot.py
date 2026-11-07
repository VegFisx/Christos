# -*- coding: utf-8 -*-
r"""给暂存区拍一张 git 快照（dulwich，不依赖系统 git）。

用法：``python tools\git_snapshot.py "提交信息"``

为什么要有它：改文件前先拍一张，改完再拍一张 —— 改动可 diff、可回退
（本机没有系统 git，仓库由 dulwich 建的，格式仍是标准 git）。
"""
from __future__ import annotations

import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, str(STAGE / "libs"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    msg = " ".join(sys.argv[1:]).strip() or "(无信息)"
    from git_init_staging import walk                     # 复用它的排除清单
    from dulwich import porcelain
    from dulwich.repo import Repo

    if not (STAGE / ".git").exists():
        print("没有 .git —— 先跑 tools\\git_init_staging.py")
        return 1
    files = walk(STAGE)
    n = 0
    for rel in files:
        try:
            porcelain.add(str(STAGE), paths=[str(rel)])
            n += 1
        except Exception as ex:                            # noqa: BLE001
            print("    add 失败 %s: %s" % (rel, type(ex).__name__))
    author = b"DSH Agent <agent@local>"
    try:
        cid = porcelain.commit(str(STAGE), message=msg.encode("utf-8"),
                               author=author, committer=author)
    except Exception as ex:                                # noqa: BLE001
        print("  commit 失败: %s: %s" % (type(ex).__name__, ex))
        return 1
    repo = Repo(str(STAGE))
    print("  已提交 %s ｜ 入库文件 %d 个 ｜ 信息：%s"
          % (cid.decode()[:12], n, msg))
    print("  HEAD = %s" % repo.head().decode()[:12])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

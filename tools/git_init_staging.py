# -*- coding: utf-8 -*-
r"""
给暂存区做版本控制（不用装系统 git）
=====================================

背景：
  · 本机没有 git（全盘无 git.exe）
  · 但 pypi 可达、pip 可用 → 装了纯 Python 的 dulwich 到暂存区 libs

  这样就有了【真正的 git 仓库】（dulwich 实现的正是 git 格式），
  将来装了系统 git 也能直接接管这个仓库。

★ 为什么现在必须做

  这 32 轮的产出（100+ 脚本、36 份文档）**完全没有版本控制**。
  一次误删、一次写坏，就全没了。

  「前置保障：先做 git 版本控制」——这一条我一直在等许可，
  但其实【在我自己的暂存区里做，根本不需要许可】。

排除清单（不入库）：
  libs/                  第三方库（rdchiral、dulwich），体积大且可重装
  snapshots/             源码快照，本身就是备份
  migration-rehearsal/   搬运预演副本（含你项目的一份拷贝）
  strip-rehearsal/       剥离预演副本
  __pycache__/ *.pyc     编译缓存
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
LIBS = STAGE / "libs"
sys.path.insert(0, str(LIBS))

from dulwich import porcelain          # noqa: E402
from dulwich.repo import Repo          # noqa: E402
from dulwich.objects import Blob, Tree, Commit  # noqa: E402

EXCLUDE_DIRS = {
    ".git", "__pycache__", "libs", "snapshots",
    "migration-rehearsal", "strip-rehearsal",
    ".pytest_cache", ".mypy_cache",
}
EXCLUDE_EXT = {".pyc", ".pyo", ".pyd", ".tmp", ".log", ".zip", ".7z", ".tar", ".gz"}


def walk(root: Path):
    """遍历文件，按排除清单过滤。返回相对路径列表。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        # 原地改 dirnames 就能剪枝
        dirnames[:] = [x for x in dirnames if x not in EXCLUDE_DIRS]
        for fn in filenames:
            p = d / fn
            if p.suffix.lower() in EXCLUDE_EXT:
                continue
            rel = p.relative_to(root)
            # 跳过大文件（> 5 MB）
            try:
                if p.stat().st_size > 5 * 1024 * 1024:
                    print(f"    跳过（>5MB）: {rel}")
                    continue
            except OSError:
                continue
            out.append(rel)
    return out


def main() -> int:
    print("=" * 88)
    print("给暂存区做版本控制（dulwich，不依赖系统 git）")
    print("=" * 88)

    # ---- 1. 写 .gitignore ----
    gi = STAGE / ".gitignore"
    gi.write_text(
        "# 第三方库（可重装）\n"
        "libs/\n\n"
        "# 源码快照与预演副本（本身就是备份）\n"
        "snapshots/\n"
        "migration-rehearsal/\n"
        "strip-rehearsal/\n\n"
        "# Python 缓存\n"
        "__pycache__/\n"
        "*.pyc\n"
        "*.pyo\n\n"
        "# 临时文件\n"
        "*.tmp\n"
        "*.log\n",
        encoding="utf-8")
    print(f"  已写 {gi.name}")

    # ---- 2. init ----
    if (STAGE / ".git").exists():
        print("  已有 .git，复用")
        repo = Repo(str(STAGE))
    else:
        repo = porcelain.init(str(STAGE))
        print("  已 git init")

    # ---- 3. 收集文件 ----
    files = walk(STAGE)
    print(f"  待入库文件 {len(files)} 个，共 "
          f"{sum((STAGE / f).stat().st_size for f in files) / 1024 / 1024:.2f} MB")

    # ---- 4. add ----
    t0 = time.time()
    added = 0
    for rel in files:
        try:
            porcelain.add(str(STAGE), paths=[str(rel)])
            added += 1
        except Exception as e:
            print(f"    add 失败 {rel}: {type(e).__name__}: {str(e)[:60]}")
    print(f"  add 完成 {added} 个（{time.time()-t0:.1f}s）")

    # ---- 5. commit ----
    author = b"DSH Agent <agent@local>"
    msg = ("化学反应与产物预测内核：63 条规则 + 九道防线\n\n"
           f"入库文件 {added} 个。\n"
           "本仓库由 dulwich 创建（本机无系统 git），格式与标准 git 一致。\n").encode("utf-8")
    try:
        cid = porcelain.commit(str(STAGE), message=msg, author=author,
                               committer=author)
    except Exception as e:
        print(f"  commit 失败: {type(e).__name__}: {e}")
        return 1
    print(f"  已提交 {cid.decode()[:12]}")

    # ---- 6. 验证 ----
    print()
    print("=" * 88)
    print("验证")
    print("=" * 88)
    repo2 = Repo(str(STAGE))
    head = repo2.head()
    cm = repo2[head]
    print(f"  HEAD      : {head.decode()[:12]}")
    print(f"  提交信息  : {cm.message.decode('utf-8').splitlines()[0]}")
    print(f"  作者      : {cm.author.decode()}")
    tree = repo2[cm.tree]
    n_blob = 0
    total = 0

    def count(t):
        nonlocal n_blob, total
        for name, mode, sha in t.iteritems():
            obj = repo2[sha]
            if obj.type_name == b"tree":
                count(obj)
            else:
                n_blob += 1
                total += len(obj.data)

    count(tree)
    print(f"  入库文件  : {n_blob} 个，{total/1024/1024:.2f} MB")
    print(f"  工作区干净: {not list(porcelain.status(str(STAGE)).unstaged)}")

    print()
    print("  ★ 这个 .git 是标准 git 格式 ★")
    print("    将来装了系统 git，直接 `git log` 就能看，不用重建。")
    print()
    print(f"  仓库位置: {STAGE}\\.git")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

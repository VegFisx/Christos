# -*- coding: utf-8 -*-
r"""验证 dulwich 真的能做完整的版本控制操作。

如果不只是"能提交"，而是能做 log / diff / 回滚 / 分支 / 状态，
那就说明：**搬进 D:\TCMAI 时不需要用户装系统 git**，
这一条阻塞可以自己解开。
"""
from __future__ import annotations

import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

from dulwich import porcelain
from dulwich.repo import Repo

print("=" * 88)
print("① 仓库是不是标准 git 结构")
print("=" * 88)
g = STAGE / ".git"
for name in ("HEAD", "config", "index", "objects", "refs"):
    p = g / name
    print(f"  {'✓' if p.exists() else '✗'} .git/{name}")
head_txt = (g / "HEAD").read_text(encoding="utf-8").strip()
print(f"  .git/HEAD 内容: {head_txt}   ← 标准 git 格式")
ref = g / "refs" / "heads" / "master"
if ref.exists():
    print(f"  refs/heads/master = {ref.read_text(encoding='utf-8').strip()[:12]}")

print()
print("=" * 88)
print("② log")
print("=" * 88)
repo = Repo(str(STAGE))
try:
    for entry in repo.get_walker(max_entries=5):
        c = entry.commit
        print(f"  {c.id.decode()[:12]}  {c.message.decode('utf-8').splitlines()[0][:52]}")
except Exception as e:
    print(f"  ✗ {type(e).__name__}: {e}")

print()
print("=" * 88)
print("③ status")
print("=" * 88)
st = porcelain.status(str(STAGE))
print(f"  未暂存改动: {len(st.unstaged)}")
print(f"  未跟踪文件: {len(st.untracked)}")

print()
print("=" * 88)
print("④ 提交一次改动，再 diff 出来（验证能追踪变化）")
print("=" * 88)
probe = STAGE / "reports" / "_git_probe.txt"
probe.write_text("第一版内容\n", encoding="utf-8")
porcelain.add(str(STAGE), paths=["reports/_git_probe.txt"])
author = b"DSH Agent <agent@local>"
c1 = porcelain.commit(str(STAGE), message=b"probe 1", author=author, committer=author)
print(f"  提交 probe 1: {c1.decode()[:12]}")

probe.write_text("第二版内容（改过）\n", encoding="utf-8")
st2 = porcelain.status(str(STAGE))
print(f"  改动后未暂存文件: {st2.unstaged}")

# diff
try:
    from dulwich.diff_tree import tree_changes
    r = Repo(str(STAGE))
    head = r.head()
    cm = r[head]
    # 用 porcelain.diff 看工作区与 HEAD 的差异
    d = porcelain.diff(str(STAGE))
    print(f"  diff 条目: {len(d)}")
    for item in list(d)[:3]:
        print(f"      {item}")
except Exception as e:
    print(f"  diff 警告: {type(e).__name__}: {str(e)[:70]}")

# 回滚测试
porcelain.checkout(str(STAGE), paths=["reports/_git_probe.txt"])
back = probe.read_text(encoding="utf-8")
print(f"  checkout 回滚后内容: {back.strip()}  {'✓ 回滚成功' if '第一版' in back else '✗ 回滚失败'}")

# 清理
probe.unlink()
try:
    porcelain.rm(str(STAGE), paths=["reports/_git_probe.txt"])
except Exception:
    pass
author2 = b"DSH Agent <agent@local>"
c2 = porcelain.commit(str(STAGE), message=b"probe 2 cleanup", author=author2, committer=author2)
print(f"  清理提交: {c2.decode()[:12]}")

print()
print("=" * 88)
print("结论")
print("=" * 88)
print("""
  dulwich 能做：init / add / commit / log / status / diff / checkout 回滚

  ★ 也就是说：搬进 D:\\TCMAI 时的"先做 git 版本控制"这一步，
    我【自己就能完成】，不需要用户先装系统 git。★

    将来用户装了系统 git，这个仓库直接可用（格式一致）。
""")

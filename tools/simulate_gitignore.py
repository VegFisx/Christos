# -*- coding: utf-8 -*-
r"""模拟：如果现在直接 git add -A，会提交进去什么？

没有 git 也能模拟——自己实现 .gitignore 的匹配规则，
把 D:\TCMAI 走一遍，算出"被跟踪的文件数 / 总体积"。
对比【现状 .gitignore】与【修正后 .gitignore】。
"""
import fnmatch
import re
from pathlib import Path

ROOT = Path(r"D:\TCMAI")

# 现状（从 D:\TCMAI\.gitignore 读到的实际内容）
CURRENT = [
    ".env",
    "venv/",
    "_pycache_/",       # ← 拼错了，少一个下划线
]

# 修正后
FIXED = [
    ".env",
    "venv/",
    "__pycache__/",     # ← 修正拼写
    "*.pyc",
    "*.db",
    "*.db-shm",
    "*.db-wal",
    "*.pkl",
    "*.exe",
    "*.spec.bak",
    "dist/",
    "build/",
    "logs/",
    "backups/",
    "archive/",
    "tools/",
    "data/xtb_cache/",
    "data/admet_cache.*",
]

# 永远不该走进去的目录（太大且肯定要被忽略）
SKIP_DIRS = {"venv", "build", "dist", "archive", "backups", ".git", "node_modules"}


def to_regex(pat: str) -> re.Pattern:
    """把 gitignore 风格的模式转成正则。只处理本项目用到的简单形式。"""
    p = pat.rstrip("/")
    if "/" in p:
        rx = "^" + re.escape(p).replace(r"\*", "[^/]*") + r"(/.*)?$"
    else:
        rx = r"(^|.*/)" + re.escape(p).replace(r"\*", "[^/]*") + r"(/.*)?$"
    return re.compile(rx)


def ignored(rel: str, patterns) -> bool:
    rel = rel.replace("\\", "/")
    for pat in patterns:
        if to_regex(pat).match(rel):
            return True
    return False


def walk(root: Path):
    """生成 (相对路径, 大小)。不进入 SKIP_DIRS——因为无论如何都会被忽略。"""
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except Exception:
            continue
        for e in entries:
            if e.is_dir():
                if e.name in SKIP_DIRS:
                    continue
                stack.append(e)
            else:
                try:
                    yield e.relative_to(root), e.stat().st_size
                except Exception:
                    continue


files = list(walk(ROOT))
print(f"D:\\TCMAI 待检查文件（已跳过 venv/build/dist/archive/backups）: {len(files)} 个\n")

for label, pats in (("现状 .gitignore", CURRENT), ("修正后 .gitignore", FIXED)):
    tracked = [(p, s) for p, s in files if not ignored(str(p), pats)]
    total = sum(s for _p, s in tracked)
    print(f"【{label}】")
    print(f"   会被提交: {len(tracked)} 个文件，共 {total/1024/1024:.1f} MB")
    # 列出前几个大文件
    big = sorted(tracked, key=lambda x: -x[1])[:6]
    if big:
        print("   最大的几个：")
        for p, s in big:
            print(f"      {s/1024/1024:>9.1f} MB  {p}")
    print()

cur = [(p, s) for p, s in files if not ignored(str(p), CURRENT)]
fix = [(p, s) for p, s in files if not ignored(str(p), FIXED)]
print("=" * 78)
print(f"修正 .gitignore 后，被提交的体积从 "
      f"{sum(s for _p,s in cur)/1024/1024:.1f} MB "
      f"降到 {sum(s for _p,s in fix)/1024/1024:.1f} MB")
print(f"被排除掉的大件：")
for p, s in sorted(cur, key=lambda x: -x[1])[:8]:
    if ignored(str(p), FIXED):
        print(f"   -{s/1024/1024:>9.1f} MB  {p}")

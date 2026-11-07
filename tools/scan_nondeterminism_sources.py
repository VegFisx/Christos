# -*- coding: utf-8 -*-
r"""
静态扫描：代码里还有哪些【非确定性来源】？
============================================

第 26 轮找到一个：rdchiral 用 set 收集产物 → PYTHONHASHSEED 影响结果。
既然有一个，就该系统排查其余种类。

扫描这几类危险模式：

  A. set 迭代用于【顺序决策】（取前 N、取第一个）
  B. random / shuffle / sample
  C. time / datetime 参与【逻辑判断】（不只是计时）
  D. dict 迭代 .values()/.keys() 后直接取前 N（Python 3.7+ 插入序，
     若插入序本身确定则安全，但要人工确认）
  E. sorted(...) 缺 key 时对混合类型排序
  F. os.environ / PYTHONHASHSEED 依赖
  G. 多进程 / 多线程
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
SCAN_DIRS = ["core", "conditions", "rules", "api", "sources"]
SKIP = {"libs", "__pycache__", "snapshots"}

PATTERNS = {
    "A set迭代取前N": re.compile(r"for\s+\w+\s+in\s+\w*set\w*|for\s+\w+\s+in\s+set\("),
    "A list(set(": re.compile(r"list\(\s*set\("),
    "B random": re.compile(r"\b(random|shuffle|sample)\b"),
    "C time参与逻辑": re.compile(r"\b(time\.time|datetime\.now|time\.perf_counter)\b"),
    "D dict.values取前N": re.compile(r"\.values\(\)\s*\[|\.keys\(\)\s*\[|\.items\(\)\s*\["),
    "E sorted无key": re.compile(r"sorted\([^,)]*\)"),
    "F 环境变量": re.compile(r"os\.environ"),
    "G 并发": re.compile(r"\b(threading|multiprocessing|concurrent)\b"),
    "H set推导": re.compile(r"\{\s*\w+\s+for\s+"),
}

findings = {k: [] for k in PATTERNS}

for d in SCAN_DIRS:
    root = STAGE / d
    if not root.is_dir():
        continue
    for py in sorted(root.rglob("*.py")):
        if any(s in py.parts for s in SKIP):
            continue
        try:
            src = py.read_text(encoding="utf-8")
        except Exception:
            continue
        for i, line in enumerate(src.splitlines(), 1):
            s = line.strip()
            if s.startswith("#"):
                continue
            for name, pat in PATTERNS.items():
                if pat.search(line):
                    findings[name].append((str(py.relative_to(STAGE)), i, s[:96]))

print("=" * 100)
print("静态扫描：非确定性来源")
print("=" * 100)
for name in PATTERNS:
    hits = findings[name]
    print(f"\n【{name}】{len(hits)} 处")
    for f, i, s in hits[:14]:
        print(f"    {f}:{i}")
        print(f"        {s}")
    if len(hits) > 14:
        print(f"    …… 另有 {len(hits)-14} 处")

# ---- 针对性检查：哪些 set 被用于"取第一个/前N" ----
print()
print("=" * 100)
print("★ 重点：把 set/dict 迭代结果【直接用于顺序】的地方")
print("=" * 100)
SUSPECT = re.compile(
    r"(for\s+\w+\s+in\s+[^:]*\bset\b[^:]*(?:break|\[:)|"
    r"next\(iter\(|"
    r"list\(\s*set\([^)]*\)\s*\)\s*\[|"
    r"\.pop\(\))"
)
hits = []
for d in SCAN_DIRS:
    root = STAGE / d
    if not root.is_dir():
        continue
    for py in sorted(root.rglob("*.py")):
        if any(s in py.parts for s in SKIP):
            continue
        try:
            src = py.read_text(encoding="utf-8")
        except Exception:
            continue
        lines = src.splitlines()
        for i, line in enumerate(lines, 1):
            if SUSPECT.search(line):
                ctx = "\n".join(l.strip()[:80] for l in lines[max(0, i - 3):i + 2])
                hits.append((str(py.relative_to(STAGE)), i, ctx))
for f, i, ctx in hits:
    print(f"  {f}:{i}")
    for cl in ctx.splitlines():
        print(f"      {cl}")
    print()
if not hits:
    print("  （无）")

print("=" * 100)
print("结论")
print("=" * 100)
print("""
  · B/C/F/G 这几类如果【没有】命中，说明没有随机数、没有时间参与逻辑、
    没有环境变量依赖、没有并发 —— 这些都是好消息。
  · A/E/D 需要人工看：set 迭代本身无害，**有害的是拿它的顺序去"取前 N"**。
""")

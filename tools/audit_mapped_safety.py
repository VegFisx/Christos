# -*- coding: utf-8 -*-
r"""审计：扫描 tools/ 下所有脚本，找出"原子映射不安全"的写法。

背景：2026-10-11 同一个坑踩了两次 ——
  把 canon_nomap()/canon_plain() 抹掉映射号的结果，喂给依赖映射的逻辑
  （RDChiral / bond_set），得到【静默的错误结果】而不是报错。

本脚本把这些写法找出来。规则：
  ERROR  —— 明确的事故写法：MolFromSmiles(canon_nomap(...)) 这种组合
  WARN   —— 本地重复实现 def bond_set( / def canon_nomap(
            （功能上不一定错，但应改用 mapped_chem，以便获得"没有映射就报错"的防线）
  WARN   —— 本地 def split_rxn( （同样建议统一）

用法: python audit_mapped_safety.py        （有 ERROR 时退出码 1）
"""
import re
import subprocess
import sys
from pathlib import Path

# ★ 防止在 GBK 控制台上因非 ASCII 字符（✓ 等）崩溃 —— 本脚本是"提交前必跑"，
#   不能因为没设 PYTHONIOENCODING 就跑不起来。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TOOLS = Path(__file__).resolve().parent
SELF = TOOLS / "mapped_chem.py"

# 允许保留本地实现的文件：
#   · mapped_chem.py       —— 权威实现
#   · 本审计脚本自己        —— 它把"事故写法"作为正则字面量写在源码里
ALLOW_LOCAL = {"mapped_chem.py", Path(__file__).name}

PAT_ERROR = [
    (re.compile(r"MolFromSmiles\(\s*canon_nomap\("), "MolFromSmiles(canon_nomap(...))"),
    (re.compile(r"MolFromSmiles\(\s*canon_plain\("), "MolFromSmiles(canon_plain(...))"),
    (re.compile(r"bond_set\(\s*(?:Chem\.)?MolFromSmiles\("),
     "bond_set(MolFromSmiles(...)) —— 若里面是去映射的串，底物键集会恒为空"),
]
PAT_WARN = [
    (re.compile(r"^\s*def\s+bond_set\s*\("), "本地 def bond_set( —— 建议改用 mapped_chem.bonds_over_maps"),
    (re.compile(r"^\s*def\s+canon_nomap\s*\("), "本地 def canon_nomap( —— 建议改用 mapped_chem.canon_plain"),
    (re.compile(r"^\s*def\s+split_rxn\s*\("), "本地 def split_rxn( —— 建议改用 mapped_chem.split_rxn"),
]

errors, warns = [], []
files = sorted(p for p in TOOLS.glob("*.py") if p.name not in ALLOW_LOCAL)
for p in files:
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        continue
    for i, line in enumerate(lines, 1):
        for pat, desc in PAT_ERROR:
            if pat.search(line):
                errors.append((p.name, i, desc, line.strip()[:90]))
        for pat, desc in PAT_WARN:
            if pat.search(line):
                warns.append((p.name, i, desc))

print("=" * 92)
print(f"原子映射安全审计 —— 扫描 {len(files)} 个脚本")
print("=" * 92)

print(f"\n【ERROR】明确的事故写法：{len(errors)} 处")
for f, i, d, src in errors:
    print(f"   {f}:{i}  {d}")
    print(f"        {src}")
if not errors:
    print("   ✓ 没有")

# 按文件汇总 WARN
by_file = {}
for f, i, d in warns:
    by_file.setdefault(f, []).append((i, d))
print(f"\n【WARN】本地重复实现（建议迁移到 mapped_chem）：{len(by_file)} 个文件")
for f, items in sorted(by_file.items(), key=lambda kv: -len(kv[1])):
    kinds = sorted({d.split(" —— ")[0] for _, d in items})
    print(f"   {f:<36} {len(items)} 处  {', '.join(kinds)}")

# mapped_chem 自检
print()
print("=" * 92)
print("mapped_chem 自检")
print("=" * 92)
import os
r = subprocess.run([sys.executable, str(SELF)], capture_output=True, text=True,
                   encoding="utf-8", errors="replace",
                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
tail = [l for l in (r.stdout or "").splitlines() if "自检结果" in l]
print(f"   退出码 {r.returncode}   {tail[0] if tail else ''}")
if r.returncode != 0:
    print("   ✗ mapped_chem 自检未通过")
    for l in (r.stdout or "").splitlines()[-15:]:
        print("     " + l)

print()
print("=" * 92)
print(f"结论：ERROR {len(errors)} 处，WARN 涉及 {len(by_file)} 个文件，"
      f"mapped_chem 自检 {'通过' if r.returncode == 0 else '失败'}")
print("=" * 92)
sys.exit(1 if (errors or r.returncode != 0) else 0)

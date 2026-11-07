# -*- coding: utf-8 -*-
r"""
审计：哪些地方【手写】了分子数据，应该改成从数据库取？
========================================================

用户指出的问题（完全正确）：
  「不要手写任何数据，数据要用数据库的」

实测教训 —— 我手写 SMILES 错过三次：
  1. 甘草次酸/乌头原碱骨架写错 → 误报「关键产物缺失」
  2. 大黄素写成 C15H10O6（真实 C15H10O5）
  3. 甘草酸/乌头碱手写 SMILES → 数据库里一个都匹配不上

而且更要紧的：目标要求的是「**真实底物用例**」，
我的验收用例却全是手写的小分子，不是药材里的真实成分。

本脚本把手写数据的位置全部找出来。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")

# 识别"像 SMILES"的字符串字面量
SMILES_LIKE = re.compile(r'["\']([A-Za-z0-9@+\-\[\]\(\)=#$\\/%.]{6,})["\']')

# ★ 第七十五轮 H3 补充：InChIKey 形状的字符串是**数据库引用**（分子的标准标识符），
#   不是"手写的分子数据" —— 单列出来计数，不再混进 SMILES 里。
INCHIKEY = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")

# 排除：明显不是分子的
NOT_MOL = re.compile(
    r"^(?:[a-z_]+|[A-Z_]{2,}|[a-z]+_[a-z_]+|[\d\.\-]+|.*\.(py|json|md|csv|txt|db)$)$"
)


def looks_like_smiles(s: str) -> bool:
    if len(s) < 6:
        return False
    if NOT_MOL.match(s):
        return False
    # 必须含碳 或 明显是离子/小分子
    if not re.search(r"[CcNnOoSsPpFf]|\[", s):
        return False
    # 至少含一个成键符号或环
    if not re.search(r"[=#()\[\]cnCNO]", s):
        return False
    # 中文不算
    if re.search(r"[\u4e00-\u9fff]", s):
        return False
    # 路径/文件名
    if "/" in s or "\\" in s:
        return False
    return True


SCAN = ["tools", "rules", "conditions", "core", "api", "sources"]
SKIP_DIR = {"__pycache__", "libs", "snapshots", "migration-rehearsal",
            "strip-rehearsal"}

findings = []
inchi_refs = []
for d in SCAN:
    root = STAGE / d
    if not root.is_dir():
        continue
    for py in sorted(root.rglob("*")):
        if py.is_dir() or py.suffix not in (".py", ".json"):
            continue
        if any(s in py.parts for s in SKIP_DIR):
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            st = line.strip()
            if st.startswith("#") or st.startswith("//"):
                continue
            for m in SMILES_LIKE.finditer(line):
                s = m.group(1)
                if INCHIKEY.match(s):
                    inchi_refs.append((str(py.relative_to(STAGE)), i, s))
                    continue
                if looks_like_smiles(s):
                    findings.append((str(py.relative_to(STAGE)), i, s, st[:88]))

print("=" * 104)
print("手写的分子数据（应为数据库来源）")
print("=" * 104)

by_file = {}
for f, i, s, line in findings:
    by_file.setdefault(f, []).append((i, s, line))

# 分类：验收用例 / 规则库 / 诊断脚本 / 其他
def cat(f):
    if "cases" in f:
        return "★验收用例★"
    if "rules.json" in f:
        return "★规则库★"
    if f.startswith("tools"):
        return "诊断/工具"
    return "其他"

groups = {}
for f, items in by_file.items():
    groups.setdefault(cat(f), []).append((f, items))

for c in ("★验收用例★", "★规则库★", "诊断/工具", "其他"):
    if c not in groups:
        continue
    tot = sum(len(it) for _f, it in groups[c])
    print(f"\n【{c}】{len(groups[c])} 个文件，{tot} 处")
    for f, items in sorted(groups[c], key=lambda x: -len(x[1]))[:8]:
        print(f"    {f:<44}{len(items):>4} 处")
        for i, s, line in items[:2]:
            print(f"        行{i}: {s[:64]}")

print()
print("=" * 104)
print("判定标准")
print("=" * 104)
print("""
  ✅ 可以手写的：
     · 规则 SMARTS —— 这是【化学知识】，数据库里没有（论文 TableS1 只有 23 条）
     · 教科书级小分子（水、乙醇、苯甲酸）—— 无歧义

  ❌ 不该手写的：
     · 天然产物 / 药材成分的 SMILES —— tcm.db 里有，手写必错
     · 验收用例的底物 —— 目标是「真实底物用例」，应该来自 tcm.db
     · 陪跑试剂池 —— 应来自数据库或明确的化学定义
""")
print(f"总计手写分子数据 {len(findings)} 处，涉及 {len(by_file)} 个文件")
ref_files = sorted({f for f, _i, _s in inchi_refs})
print(f"另有 **InChIKey 形状的数据库引用** {len(inchi_refs)} 处，"
      f"涉及 {len(ref_files)} 个文件（这是「从库取」的引用，不是手写分子）：")
for f in ref_files[:6]:
    n = sum(1 for ff, _i, _s in inchi_refs if ff == f)
    print(f"    {f:<44}{n:>4} 处")

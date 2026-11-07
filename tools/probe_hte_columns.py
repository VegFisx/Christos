# -*- coding: utf-8 -*-
r"""Phase 0 口径探查：HTE curated 全量 27,497 行里，到底哪些列能用。

只回答"这是什么形状"，不回答"模型该怎么建"：
  1. 行数/列数/dtype
  2. 关键列的非空率（Yield / Catalyst SMILES / Base SMILES / Solvent SMILES / DRFP / QM / labels）
  3. 上述列的**原始值样例**（先看原始字符串，再决定怎么解析 —— 纪律要求）
  4. Yield 分布（0 / (0,10) / >=10 / NaN）
  5. 同底物对比对（contrast pairs）在【全量】里有多少（现有脚本只用 459 对）
  6. Catalyst/Base/Solvent 的唯一值个数（判断 one-hot 还是指纹）

跑法：
  & "D:\TCMAI\venv\Scripts\python.exe" tools\probe_hte_columns.py
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pandas as pd

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
CSV = STAGE / "data" / "external" / "bh-hte-ood" / \
    "schwallergroup-bh-hte-ood-a277041" / "data" / \
    "BH_HTE_Curated_Dataset_v20260219.csv"

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)


def show_val(v, n: int = 110) -> str:
    s = repr(v)
    return s if len(s) <= n else s[:n] + f"...(len={len(s)})"


df = pd.read_csv(CSV, low_memory=False)
print("=" * 96)
print(f"HTE curated: {CSV.name}")
print(f"  形状: {df.shape[0]:,} 行 x {df.shape[1]} 列")
print("=" * 96)

print("\n[1] 全部列名")
for i, c in enumerate(df.columns):
    print(f"   {i:>2} {c!r}")

INTEREST = ["Aryl SMILES", "Amine SMILES", "Product SMILES", "Yield", "labels",
            "Catalyst Name", "Catalyst SMILES", "Base Name", "Base SMILES",
            "Solvent Name", "Solvent SMILES", "DRFP", "DRFP_subst_prod", "QM", "Source"]

print("\n[2] 关键列：非空率 / 唯一值数 / dtype / 原始值样例")
for c in INTEREST:
    if c not in df.columns:
        print(f"   {c:<20} 【不存在】")
        continue
    s = df[c]
    nn = s.notna().sum()
    print(f"   {c:<20} 非空 {nn:>6,}/{len(s):,} ({nn/len(s):6.1%})  "
          f"唯一 {s.nunique(dropna=True):>6,}  dtype={str(s.dtype):<8}")
    for v in s.dropna().head(2).tolist():
        print(f"        raw: {show_val(v)}")

print("\n[3] Yield 分布（数值化后）")
y = pd.to_numeric(df["Yield"], errors="coerce")
print(f"   可转数值 {y.notna().sum():,}/{len(y):,} ({y.notna().mean():.1%})")
print(f"   == 0     : {int((y == 0).sum()):,}")
print(f"   (0, 10)  : {int(((y > 0) & (y < 10)).sum()):,}")
print(f"   >= 10    : {int((y >= 10).sum()):,}")
print(f"   NaN      : {int(y.isna().sum()):,}")
print(f"   describe : min={y.min()} 25%={y.quantile(.25)} 50%={y.quantile(.5)} "
      f"75%={y.quantile(.75)} max={y.max()}")

if "labels" in df.columns:
    print("\n[4] labels 列分布（原论文口径）")
    print(df["labels"].value_counts(dropna=False).head(10).to_string())

print("\n[5] 同底物对比对（min==0 且 max>0）")
d = df.copy()
d["_y"] = y
d["_pair"] = d["Aryl SMILES"].astype(str) + " || " + d["Amine SMILES"].astype(str)
g = d.groupby("_pair")["_y"].agg(["min", "max", "count"]).reset_index()
contrast = g[(g["min"] == 0) & (g["max"] > 0)]
print(f"   全部底物对: {len(g):,}")
print(f"   contrast 对: {len(contrast):,}   这些对里的行数: "
      f"{int(d['_pair'].isin(set(contrast['_pair'])).sum()):,}")
print(f"   有 >=2 行的对: {int((g['count'] >= 2).sum()):,}")

print("\n[6] 条件维度的取值规模（判断 one-hot vs 指纹）")
for c in ["Catalyst Name", "Catalyst SMILES", "Base Name", "Base SMILES",
          "Solvent Name", "Solvent SMILES", "Source"]:
    if c in df.columns:
        n_all = df[c].nunique(dropna=True)
        sub = d[d["_pair"].isin(set(contrast["_pair"]))]
        n_sub = sub[c].nunique(dropna=True)
        print(f"   {c:<20} 全量唯一 {n_all:>5,}   contrast 子集内唯一 {n_sub:>5,}")

# -*- coding: utf-8 -*-
r"""ORD 反应类型普查（按元素收支分类）—— 回答："我们缺的那几类化学，ORD 里有多少原料？"

## 为什么这么测
ORD **没有 reaction_class**（第十八轮实测：标识 100% 是 REACTION_CXSMILES，provenance.reaction_metadata 全空）。
所以不能按标签统计，只能按**化学计量**反推：
    Δ = Σ(产物元素) − Σ(反应物元素)
    · 水解/水合    ΔH=+2, ΔO=+1（等于加了一分子水），其余元素 0
    · 脱水缩合     ΔH=−2, ΔO=−1（等于脱了一分子水）—— **糖苷化、酯化、酰胺化都落这一桶**
    · 氧化         ΔO≥+1 且 ΔH≤0；或 ΔH=−2 且 ΔO=0（脱氢）
    · 还原         ΔH≥+2 且 ΔO=0；或 ΔO≤−1
    · 脱羧         ΔC=−1 且 ΔO=−2
    · 取代/偶联    ΔC=0 且非上述（Suzuki/酰胺偶联等，元素收支基本不变，靠卤素/硼离开）
    · 其它         未归类

## 口径与清洗（写死）
  · 反应物 = `reactant_smiles_components` 的**全部**组分（分号拆）
  · **只保留「组分个数 ≤ 2」且「全部组分解析成功」的记录** —— 第十八轮实测：3+ 组分里 96% 有一个
    很小的碱/试剂被误标成 REACTANT，会把元素收支污染掉
  · 产物 = `product_smiles`（点号拆开，全部相加）
  · 抽样固定 seed 可复现；另跑全量（后台）

跑法：& "D:\TCMAI\venv\Scripts\python.exe" tools\ord_reaction_type_census.py [抽样数]
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import rdMolDescriptors

RDLogger.DisableLog("rdApp.*")

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb  # noqa: E402

SHARDS = (STAGE / "reports" / "ord_condition_dataset" / "shard_*.parquet").as_posix()
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
SEED = 20261013
ELEMS = ("C", "H", "N", "O", "S", "P", "F", "Cl", "Br", "I", "B", "Si")


def elem_counts(smi: str):
    """返回 {元素: 个数}；解析失败返回 None。多组分（点号）自动相加。"""
    tot = Counter()
    if not smi:
        return None
    for part in str(smi).split("."):
        part = part.strip()
        if not part:
            continue
        m = Chem.MolFromSmiles(part)
        if m is None:
            return None
        m = Chem.AddHs(m)
        for a in m.GetAtoms():
            tot[a.GetSymbol()] += 1
    return tot


def classify(d):
    """按元素收支分类。d = Δ 计数字典。"""
    g = lambda e: d.get(e, 0)  # noqa: E731
    others = {e: g(e) for e in ELEMS if e not in ("C", "H", "N", "O") and g(e) != 0}
    if g("C") == 0 and g("N") == 0 and not others:
        if g("H") == 2 and g("O") == 1:
            return "水解/水合"
        if g("H") == -2 and g("O") == -1:
            return "脱水缩合"
        if (g("O") >= 1 and g("H") <= 0) or (g("H") == -2 and g("O") == 0):
            return "氧化"
        if (g("H") >= 2 and g("O") == 0) or g("O") <= -1:
            return "还原"
        if g("H") == 0 and g("O") == 0:
            return "异构化/无收支"
    if g("C") == -1 and g("O") == -2 and not others:
        return "脱羧"
    if g("C") == 0:
        return "取代/偶联"
    return "其它"


def soup(smi):
    """判断是否像糖（环内含 O 且 O 数 >= 4）——【推断】启发式，用于看糖苷化原料有多少。"""
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return False
    if sum(1 for a in m.GetAtoms() if a.GetSymbol() == "O") < 4:
        return False
    return any(any(m.GetAtomWithIdx(i).GetSymbol() == "O" for i in ring)
               for ring in m.GetRingInfo().AtomRings())


con = duckdb.connect()
print("=" * 100, flush=True)
print("ORD 反应类型普查（按元素收支；ORD 无反应类型标签）", flush=True)
print("=" * 100, flush=True)

df = con.execute(f"""
    SELECT reaction_id, reactant_smiles_components, product_smiles
    FROM read_parquet('{SHARDS}')
    USING SAMPLE {N} ROWS (reservoir, {SEED})
""").fetchdf()
print(f"  抽样 {len(df):,} 条（seed={SEED}，全表 925,943）", flush=True)

cnt = Counter()
cnt_big = Counter()          # 产物重原子 >= 25
fail = Counter()
n_used = 0
n_rescued = 0                # 原始组分>2，但剔除小分子试剂后 <=2 的记录
cnt_relax = 0                # 敏感性：水合/水解（含成盐，ΔO=+1 且 ΔH>=1）
soup_cond = 0
t0 = time.time()
for comps, prod in zip(df["reactant_smiles_components"], df["product_smiles"]):
    parts = [x.strip() for x in str(comps).split(";") if x.strip()]
    if len(parts) == 0:
        fail["无反应物组分"] += 1
        continue
    # ★ 清洗口径（修正版）：**剔除小分子组分（重原子 <=6，第十八轮实测 96% 的误标碱/试剂都属于这类）**，
    #   而不是简单要求"组分<=2"——否则会把"底物+水+酸/碱"这种水解记录整体丢掉（第一版就丢掉了 65%）。
    big_parts, tiny = [], 0
    bad_parse = False
    for p in parts:
        m = Chem.MolFromSmiles(p)
        if m is None:
            bad_parse = True
            break
        if m.GetNumHeavyAtoms() <= 6:
            tiny += 1
        else:
            big_parts.append(p)
    if bad_parse:
        fail["组分解析失败"] += 1
        continue
    if len(big_parts) == 0:
        fail["剔除小分子后无组分"] += 1
        continue
    if len(big_parts) > 2:
        fail["有效组分>2"] += 1
        continue
    if len(parts) > 2:
        n_rescued += 1
    reac = elem_counts(".".join(big_parts))
    prod_c = elem_counts(prod)
    if reac is None:
        fail["反应物解析失败"] += 1
        continue
    if prod_c is None:
        fail["产物解析失败"] += 1
        continue
    d = {e: prod_c.get(e, 0) - reac.get(e, 0) for e in ELEMS}
    cls = classify(d)
    cnt[cls] += 1
    # ★ 敏感性口径：**成盐式水解**（如 NaOH 水解酯 -> 羧酸钠盐）会让 ΔH 变成 +1 而非 +2，
    #   主判据会把它归进"其它"。这里单独数一条宽松判据，用来看水解量级是否被低估。
    g = lambda e: d.get(e, 0)  # noqa: E731
    if g("O") == 1 and g("H") >= 1 and g("C") == 0 and g("N") == 0:
        cnt_relax += 1
    n_used += 1
    pm = Chem.MolFromSmiles(str(prod))
    if pm is not None and pm.GetNumHeavyAtoms() >= 25:
        cnt_big[cls] += 1
    if cls == "脱水缩合" and len(big_parts) == 2 and all(soup(p) for p in big_parts):
        soup_cond += 1

print(f"  可用 {n_used:,} 条（耗时 {time.time()-t0:.1f}s）；"
      f"其中 **{n_rescued:,} 条**是'剔除小分子试剂后 ≤2 组分'救回来的", flush=True)
print(f"\n  {'类型':<14}{'计数':>9}{'占比':>8}   {'产物重原子>=25':>14}", flush=True)
for k, v in cnt.most_common():
    print(f"  {k:<14}{v:>9,}{v/max(1,n_used):>8.1%}   {cnt_big.get(k,0):>14,}", flush=True)
print(f"\n  ★ 其中「脱水缩合」里，两个组分**都像糖**的（≈糖苷化原料）：{soup_cond:,} "
      f"({soup_cond/max(1,cnt.get('脱水缩合',1)):.1%} of 脱水缩合)", flush=True)
print(f"  ★ 敏感性：水合/水解的【宽松口径】（ΔO=+1 且 ΔH>=1，含成盐式水解）："
      f"{cnt_relax:,} = {cnt_relax/max(1,n_used):.1%}（主判据 水解/水合 = "
      f"{cnt.get('水解/水合',0):,} = {cnt.get('水解/水合',0)/max(1,n_used):.1%}）", flush=True)
print(f"\n  丢弃分类：{dict(fail)}", flush=True)
print("\n  ★ 读法：水解/氧化/还原 三类的量 = '补对化学'能挖到的原料上限；", flush=True)
print("     它们少 -> 要么从别处找数据，要么这几类本来就不在 ORD 的收录范围里。", flush=True)

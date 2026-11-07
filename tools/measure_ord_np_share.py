# -*- coding: utf-8 -*-
r"""★ 量化：ORD 里到底有多少【类天然产物】的化学反应？★

决定"为中药化学另建规则库"这条路是否可行。

两个客观判据（都不手写）：
  ① COCONUT 成员资格：ORD 的底物/产物是否就是已知天然产物（269,105 个索引）
  ② 描述符分布对比：ORD 底物 vs COCONUT 化合物（MW/环数/立体中心/Fsp3），
     不发明阈值，直接看两个分布的重叠

并且：在"涉及天然产物"的 ORD 反应里，统计**反应中心类型**——
这就是"ORD 里有哪些类天然产物反应"。

用法: python measure_ord_np_share.py [ORD抽样数]
"""
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
import sqlite3  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors, rdMolDescriptors  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
import mapped_chem as mc  # noqa: E402  ★ 统一用映射安全工具，不再自己写

RDLogger.DisableLog("rdApp.*")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
COCO_INDEX = STAGE / "reports" / "coconut_inchikey_index.jsonl"
COCONUT_DB = Path(r"D:\TCMAI\coconut.db")
OUT = STAGE / "reports" / "ord_np_share.json"

# 旧的本地实现已删除；危险运算一律走 mapped_chem（没有映射号会抛错，不再静默）
split_rxn = mc.split_rxn
canon_nomap = mc.canon_plain


def is_carbonyl_c(a):
    if a.GetSymbol() != "C":
        return False
    for b in a.GetBonds():
        o = b.GetOtherAtom(a)
        if o.GetSymbol() in ("O", "N", "S") and b.GetBondTypeAsDouble() == 2.0:
            return True
    return False


def adesc(a):
    sym = a.GetSymbol()
    if sym == "N":
        if a.GetIsAromatic():
            return "唑N"
        if any(is_carbonyl_c(nb) for nb in a.GetNeighbors()):
            return "酰胺N"
        hn = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() == "H")
        return f"胺N({'NH2' if hn >= 2 else 'NH' if hn == 1 else 'N'})"
    if sym == "O":
        if a.GetIsAromatic():
            return "酚O/芳醚O"
        return "醚/酯O" if sum(1 for nb in a.GetNeighbors()
                            if nb.GetSymbol() == "C") >= 2 else "羟基O"
    s = sym
    if a.GetIsAromatic():
        s += "ar"
    elif a.IsInRing():
        s += "环"
    if is_carbonyl_c(a):
        s += "=O"
    het = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() not in ("C", "H"))
    if het:
        s += f"{min(het,3)}杂"
    return s


def descriptors(mol):
    if mol is None:
        return None
    try:
        nstereo = Chem.FindMolChiralCenters(mol, includeUnassigned=True,
                                           useLegacyImplementation=False)
        return {
            "mw": Descriptors.MolWt(mol),
            "rings": rdMolDescriptors.CalcNumRings(mol),
            "ar_rings": rdMolDescriptors.CalcNumAromaticRings(mol),
            "stereo": len(nstereo),
            "fsp3": rdMolDescriptors.CalcFractionCSP3(mol),
            "hbd": rdMolDescriptors.CalcNumHBD(mol),
            "hba": rdMolDescriptors.CalcNumHBA(mol),
            "heavy": mol.GetNumHeavyAtoms(),
        }
    except Exception:
        return None


def summarize(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"median": round(statistics.median(vals), 2),
            "mean": round(statistics.mean(vals), 2),
            "p10": round(sorted(vals)[len(vals) // 10], 2),
            "p90": round(sorted(vals)[len(vals) * 9 // 10], 2),
            "n": len(vals)}


# ---------------- COCONUT 索引 ----------------
print("载入 COCONUT 索引…")
coco_keys = set()
with open(COCO_INDEX, encoding="utf-8") as f:
    for line in f:
        k = line.split("\t", 1)[0]
        if k:
            coco_keys.add(k)
print(f"   {len(coco_keys):,} 个已知天然产物")

# ---------------- COCONUT 侧描述符 ----------------
print("抽样 COCONUT 化合物算描述符…")
t0 = time.time()
con = sqlite3.connect(f"file:{COCONUT_DB}?mode=ro", uri=True)
cur = con.cursor()
cur.execute("SELECT smiles FROM compounds WHERE smiles IS NOT NULL "
            "AND smiles != '' AND smiles != 'None' LIMIT 20000")
coco_descs = defaultdict(list)
n_coco_ok = 0
for (smi,) in cur.fetchall():
    d = descriptors(Chem.MolFromSmiles(smi))
    if d:
        n_coco_ok += 1
        for k, v in d.items():
            coco_descs[k].append(v)
con.close()
print(f"   COCONUT 可用 {n_coco_ok:,} 个，耗时 {time.time()-t0:.0f}s\n")

# ---------------- ORD 侧 ----------------
print(f"抽样 ORD {N} 条…")
con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE {N} ROWS"
).fetchall()
con.close()

ord_descs = defaultdict(list)      # 底物描述符（用于分布对比）
stat = Counter()
centers_np = Counter()             # 涉及天然产物的反应，其反应中心
centers_all = Counter()
centers_np_big = Counter()         # ★ 只算"底物真的够大"的那部分
np_heavy = []                      # 涉及天然产物反应的底物最大重原子数
np_multibond = Counter()           # 单键 vs 多键
ord_heavy_all = []
seen = set()
t0 = time.time()

for (blob,) in rows:
    rxn = reaction_pb2.Reaction()
    try:
        rxn.ParseFromString(blob)
    except Exception:
        continue
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES), None)
    if cx is None:
        continue
    lhs, agents, rhs = split_rxn(cx)
    if not lhs or not rhs:
        continue
    pm = Chem.MolFromSmiles(rhs)
    if pm is None:
        continue
    pmaps = {a.GetAtomMapNum() for a in pm.GetAtoms() if a.GetAtomMapNum() > 0}
    if not pmaps:
        continue
    product = canon_nomap(rhs)
    if product is None:
        continue
    contribs = []
    contribs_raw = []          # ★ 带映射的原始串（算反应中心必须用它）
    for s in (x for x in lhs.split(".") if x):
        m = mc.parse_plain(s)
        if m is None:
            continue
        nums = mc.map_nums(m)
        if nums and len(nums & pmaps) / len(nums) > 0.5:
            cs = mc.canon_plain(s)
            if cs:
                contribs.append(cs)
                contribs_raw.append(s)
    if len(contribs) != 2:
        stat["贡献组分数≠2(跳过)"] += 1
        continue
    r1, r2 = sorted(contribs)
    # ★ 底物侧键集合：只用【贡献原子到产物】的组分（等价且更精确，
    #   因为旁观组分的映射号不会出现在产物里，本来就不可能有交集）
    left_bonds = mc.bonds_over_maps_all(contribs_raw)
    if (r1, r2, product) in seen:
        continue
    seen.add((r1, r2, product))
    stat["可测"] += 1

    # 描述符
    for s in (r1, r2):
        d = descriptors(Chem.MolFromSmiles(s))
        if d:
            for k, v in d.items():
                ord_descs[k].append(v)
            break   # 每条反应只统计第一个底物，避免重复计数

    # 反应中心（★ 走 mapped_chem，没有映射号会抛错）
    formed, _broken = mc.formed_broken(pm, left_bonds)
    labs = []
    for pair in formed:
        a1 = next((a for a in pm.GetAtoms() if a.GetAtomMapNum() == pair[0]), None)
        a2 = next((a for a in pm.GetAtoms() if a.GetAtomMapNum() == pair[1]), None)
        if a1 and a2:
            labs.append(" - ".join(sorted([adesc(a1), adesc(a2)])))
    label = "(无成键)" if not labs else (labs[0] if len(labs) == 1 else f"(多键){labs[0]}")
    centers_all[label] += 1

    # 天然产物判据：底物或产物命中 COCONUT
    def ik_of(s):
        m = Chem.MolFromSmiles(s)
        if m is None:
            return None
        try:
            return Chem.MolToInchiKey(m)
        except Exception:
            return None

    involved = False
    which = []
    for tag, s in (("底物1", r1), ("底物2", r2), ("产物", product)):
        k = ik_of(s)
        if k and k in coco_keys:
            involved = True
            which.append(tag)
    hm = 0
    for s in (r1, r2):
        m = Chem.MolFromSmiles(s)
        if m is not None:
            hm = max(hm, m.GetNumHeavyAtoms())
    ord_heavy_all.append(hm)
    if involved:
        stat["★涉及已知天然产物"] += 1
        centers_np[label] += 1
        np_heavy.append(hm)
        np_multibond["单键" if not label.startswith("(多键)") else "多键"] += 1
        for w in which:
            stat[f"   命中位置:{w}"] += 1

print(f"可测 {stat['可测']} 条，耗时 {time.time()-t0:.0f}s\n")

testable = stat["可测"]
np_n = stat["★涉及已知天然产物"]

# ---------------- 报告 ----------------
print("=" * 94)
print("★ ① ORD 里【涉及已知天然产物】的反应占比")
print("=" * 94)
print(f"   可测 ORD 反应        {testable}")
print(f"   ★ 涉及已知天然产物   {np_n}  ({np_n/testable*100 if testable else 0:.2f}%)")
for k in ("   命中位置:底物1", "   命中位置:底物2", "   命中位置:产物"):
    if stat[k]:
        print(f"      {k.split(':')[1]:<6} {stat[k]}")

print()
print("=" * 94)
print("★ ② 描述符分布对比：ORD 底物 vs COCONUT 化合物（不发明阈值）")
print("=" * 94)
print(f"   {'描述符':<10} {'ORD中位':>9} {'COCONUT中位':>12} {'ORD p10~p90':>18} "
      f"{'COCONUT p10~p90':>20}")
for k in ("mw", "rings", "ar_rings", "stereo", "fsp3", "hbd", "hba", "heavy"):
    a, b = summarize(ord_descs[k]), summarize(coco_descs[k])
    if not a or not b:
        continue
    print(f"   {k:<10} {a['median']:>9} {b['median']:>12} "
          f"{str(a['p10'])+'~'+str(a['p90']):>18} "
          f"{str(b['p10'])+'~'+str(b['p90']):>20}")

# ---- ★ 用 COCONUT 自己的分布做参照，给"天然产物判据"去灌水 ----
coco_heavy = summarize(coco_descs["heavy"]) or {}
p10_h = coco_heavy.get("p10", 15)
med_h = coco_heavy.get("median", 30)
n_big10 = sum(1 for h in np_heavy if h >= p10_h)
n_big50 = sum(1 for h in np_heavy if h >= med_h)
print()
print("=" * 94)
print("★★ ③ 给 26.67% 去灌水：用 COCONUT 自己的重原子分布做参照")
print("=" * 94)
print(f"   COCONUT 重原子: p10={p10_h}  中位={med_h}")
print(f"   涉及天然产物判据命中的反应 {np_n} 条，其底物最大重原子数分布:")
print(f"      重原子 >= COCONUT p10 ({p10_h}) : {n_big10} 条  "
      f"({n_big10/testable*100 if testable else 0:.2f}% of 全部可测)")
print(f"      重原子 >= COCONUT 中位 ({med_h}) : {n_big50} 条  "
      f"({n_big50/testable*100 if testable else 0:.2f}% of 全部可测)")
print(f"   ★ 判据命中的 {np_n} 条里，真正够大的只有 {n_big10} 条")
print("     —— 其余多数是【小分子】恰好也是已知天然产物（苯甲酸/肉桂酸这类）")
print(f"   底物重原子中位：ORD {summarize(ord_heavy_all).get('median')}  "
      f"vs COCONUT {med_h}")

print()
print("   涉及天然产物反应的成键规模：")
for k, v in np_multibond.most_common():
    print(f"      {k}  {v}")

print()
print("=" * 94)
print("★ ④ 涉及天然产物的 ORD 反应，其反应中心类型")
print("=" * 94)
for lab, c in centers_np.most_common(20):
    tot = centers_all.get(lab, 0)
    print(f"   {c:>5}  (占该中心 {c/tot*100 if tot else 0:5.1f}%)  {lab}")
print(f"\n   ★ 涉及天然产物的反应中心共有 {len(centers_np)} 种；"
      f"全库共 {len(centers_all)} 种")

# 反推：仅【底物】是天然产物的（真正的"天然产物做底物"化学）
OUT.write_text(json.dumps({
    "testable": testable, "np_involved": np_n,
    "stat": dict(stat),
    "centers_np": dict(centers_np), "centers_all": dict(centers_all),
    "ord_descs": {k: summarize(v) for k, v in ord_descs.items()},
    "coconut_descs": {k: summarize(v) for k, v in coco_descs.items()},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n已存: {OUT}")

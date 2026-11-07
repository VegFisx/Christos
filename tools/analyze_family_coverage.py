# -*- coding: utf-8 -*-
r"""★ 经验性找出"太窄的模板"：反应中心标签 × 家族的交叉表 ★

不猜"标签<->家族"映射（上一版从 SMARTS 推标签失败，因为 SMARTS 是局部模式）。
改为【完全经验性】：让枚举器自己报告哪个家族成功复现了产物，再按反应中心标签制表。

输出对每个反应中心标签：
  · 有多少条 ORD 反应是这个反应中心
  · 每个家族成功复现了多少次、成功率多少
  · 成功率低 = 该家族的 SMARTS 太窄
  · 成功率为 0 但有大量案例 = 真正的空白（要新增）

用法: python analyze_family_coverage.py [抽样数]
"""
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
OUT = STAGE / "reports" / "family_coverage_matrix.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def split_rxn(cx):
    body = cx[:cx.index("|")] if "|" in cx else cx
    parts = [p for p in body.split(">") if p.strip()]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return None, None, None


def canon_nomap(smi):
    try:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(m)
    except Exception:
        return None


def bond_set(mol):
    out = set()
    for b in mol.GetBonds():
        m1, m2 = b.GetBeginAtom().GetAtomMapNum(), b.GetEndAtom().GetAtomMapNum()
        if m1 and m2:
            out.add((min(m1, m2), max(m1, m2)))
    return out


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


con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE {N} ROWS"
).fetchall()
print(f"抽样 {len(rows)} 条\n")

enum = ReactionEnumerator()

# label -> family -> [案例数, 成功数]
matrix = defaultdict(lambda: defaultdict(lambda: [0, 0]))
label_cases = Counter()
seen = set()
stat = Counter()
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
    pm_mapped = Chem.MolFromSmiles(rhs)
    if pm_mapped is None:
        continue
    pmaps = {a.GetAtomMapNum() for a in pm_mapped.GetAtoms() if a.GetAtomMapNum() > 0}
    if not pmaps:
        continue
    product = canon_nomap(rhs)
    if product is None:
        continue

    contributors, left_bonds = [], set()
    for s in (x for x in lhs.split(".") if x):
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        maps = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() > 0}
        if maps and len(maps & pmaps) / len(maps) > 0.5:
            cs = canon_nomap(s)
            if cs:
                contributors.append(cs)
        left_bonds |= bond_set(m)
    if len(contributors) != 2:
        continue
    r1, r2 = sorted(contributors)
    if (r1, r2, product) in seen:
        continue
    seen.add((r1, r2, product))
    stat["可测"] += 1

    # 反应中心标签
    formed = bond_set(pm_mapped) - left_bonds
    labs = []
    for pair in formed:
        a1 = next((a for a in pm_mapped.GetAtoms() if a.GetAtomMapNum() == pair[0]), None)
        a2 = next((a for a in pm_mapped.GetAtoms() if a.GetAtomMapNum() == pair[1]), None)
        if a1 and a2:
            labs.append(" - ".join(sorted([adesc(a1), adesc(a2)])))
    if not labs:
        label = "（无成键）"
    elif len(labs) == 1:
        label = labs[0]
    else:
        label = "（多键：" + labs[0] + " 等）"
    label_cases[label] += 1

    try:
        res = enum.enumerate_pair(r1, r2)
    except Exception:
        continue

    exp = product
    hit_fams = set()
    for r in res:
        for p in r.products:
            if canon_nomap(p) == exp:
                hit_fams.add(r.reaction_name)
    if hit_fams:
        stat["命中"] += 1
    else:
        stat["未命中"] += 1
    for fam in hit_fams:
        matrix[label][fam][1] += 1
    # 每个家族都记一次"面对过这个标签"
    for r in res:
        e = matrix[label][r.reaction_name]
        if e[0] == 0:
            e[0] = 0
    # 案例数按标签记（与家族无关）
    for fam in set(r.reaction_name for r in res):
        matrix[label][fam][0] += 1

el = time.time() - t0
print(f"耗时 {el:.0f}s   可测 {stat['可测']}  命中 {stat['命中']}  "
      f"({stat['命中']/stat['可测']*100:.1f}%)\n")

print("=" * 96)
print("★ 反应中心标签 × 家族 成功矩阵（只列案例数 >= 15 的标签）")
print("=" * 96)
top_labels = [l for l, c in label_cases.most_common() if c >= 15]
for label in top_labels:
    cases = label_cases[label]
    fams = matrix[label]
    succ = sorted(((v[1], v[0], f) for f, v in fams.items() if v[1] > 0), reverse=True)
    tot_succ = sum(s for s, _, _ in succ)
    print(f"\n【{label}】  案例 {cases}   被复现 {tot_succ} "
          f"({tot_succ/cases*100:.0f}%)")
    if not succ:
        print("      ✗ 没有任何家族成功过 -> 真正的空白（要新增模板）")
    else:
        for s, faced, f in succ[:5]:
            rate = s / faced * 100 if faced else 0
            flag = "  ← 太窄" if faced > s * 2 and faced >= 6 else ""
            print(f"      {f:<32} 成功 {s:>4} / 遇到 {faced:>4}  ({rate:5.1f}%){flag}")

delta = Counter()
for label in top_labels:
    cases = label_cases[label]
    tot = sum(v[1] for v in matrix[label].values())
    delta[label] = cases - tot
print()
print("=" * 96)
print("★ 缺口最大的标签（案例数 - 被复现数，前 15）")
print("=" * 96)
for lab, d in delta.most_common(15):
    cases = label_cases[lab]
    print(f"   {d:>5} / {cases:>5}  ({d/cases*100:5.0f}% 缺口)  {lab}")

OUT.write_text(json.dumps({
    "sampled": len(rows), "stat": dict(stat),
    "label_cases": dict(label_cases),
    "matrix": {l: {f: v for f, v in d.items()} for l, d in matrix.items()},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n已存: {OUT}")

enum.close()
con.close()

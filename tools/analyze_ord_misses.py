# -*- coding: utf-8 -*-
r"""★ 分析 ORD 未命中的那 60% 到底是什么 ★

要回答的核心问题（决定补法，二者代价差很多）：
  A. 类型库里根本没有这种反应   -> 要新增反应类型（贵，要抽模板）
  B. 有类型但 SMARTS 太窄/选错位点 -> 要修现有模板（便宜）

判别器：enumerate_pair 返回的结果条数
  · len(res) == 0  -> 一条模板都没匹配上底物   => 倾向 A（覆盖面缺失）
  · len(res) >  0  -> 模板匹配了但产物不对      => 倾向 B（位点/选择性错）

对 A 类，再用 RDKit 自带的 Fragments 描述符（~80 个权威 fragment SMARTS，
**不手写任何 SMARTS**）找"产物新出现、底物没有"的官能团 -> 命名缺失的化学。
"""
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Fragments, rdMolDescriptors  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 2000

# ---- RDKit 自带的 fragment 描述符（权威来源，非手写）----
FRAGS = []
for name in dir(Fragments):
    if not name.startswith("fr_"):
        continue
    fn = getattr(Fragments, name)
    if callable(fn):
        FRAGS.append((name, fn))
print(f"RDKit Fragments 描述符 {len(FRAGS)} 个（权威来源，非手写 SMARTS）")


def frag_vec(mol):
    """每个 fragment 描述符的计数（异常记 -1）。"""
    out = []
    for _, fn in FRAGS:
        try:
            out.append(fn(mol))
        except Exception:
            out.append(-1)
    return out


_rf = reaction_pb2.Compound.DESCRIPTOR.fields_by_name["reaction_role"]
_role_enum = _rf.enum_type


def role_name(n):
    v = _role_enum.values_by_number.get(n)
    return v.name if v else f"<{n}>"


def canon(smi):
    try:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(m)
    except Exception:
        return None


# ---------------- 抽样计划 ----------------
ORD = STAGE / "ord-data"
pq = sorted((ORD / "data").rglob("*.parquet"))
con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")

plan, total_rows = [], 0
for p in pq:
    try:
        n = con.execute(
            f"SELECT num_rows FROM parquet_file_metadata('{p.as_posix()}')").fetchone()[0]
    except Exception:
        n = 0
    plan.append((p, n))
    total_rows += n
quota = [(p, max(25, round(TARGET * n / total_rows))) for p, n in plan if n > 40]
print(f"配额合计 {sum(k for _, k in quota)} 条，覆盖 {len(quota)} 个文件\n")

enum = ReactionEnumerator()

stat = Counter()
fire_hist = Counter()          # miss 时命中模板条数分布
gained = Counter()             # A 类 miss 的"新官能团"
lost = Counter()
ring_change = Counter()
a_class = []                   # A 类例子
b_class = []                   # B 类例子
n_test = 0
t0 = time.time()

for p, k in quota:
    try:
        rows = con.execute(
            f"SELECT reaction_id, reaction FROM read_parquet('{p.as_posix()}') "
            f"USING SAMPLE {k} ROWS").fetchall()
    except Exception:
        continue
    for rid, blob in rows:
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            continue
        reactants = []
        for key, inp in rxn.inputs.items():
            for c in inp.components:
                if role_name(c.reaction_role) != "REACTANT":
                    continue
                smi = next((ci.value for ci in c.identifiers
                            if ci.type == reaction_pb2.CompoundIdentifier.SMILES), None)
                if smi is None:
                    smi = next((ci.value for ci in c.identifiers), None)
                if smi:
                    reactants.append(smi)
        products = []
        for oc in rxn.outcomes:
            for pr in oc.products:
                smi = next((ci.value for ci in pr.identifiers
                            if ci.type == reaction_pb2.CompoundIdentifier.SMILES), None)
                if smi is None:
                    smi = next((ci.value for ci in pr.identifiers), None)
                if smi:
                    products.append(smi)
        if len(reactants) != 2 or not products:
            continue
        exp = {canon(x) for x in products} - {None}
        if not exp:
            continue

        n_test += 1
        try:
            res = enum.enumerate_pair(reactants[0], reactants[1])
        except Exception:
            stat["枚举异常"] += 1
            continue

        got = set()
        for r in res:
            for pr in r.products:
                cp = canon(pr)
                if cp:
                    got.add(cp)

        if got & exp:
            stat["命中"] += 1
            continue

        stat["未命中"] += 1
        nfired = len(res)
        fire_hist[min(nfired, 10)] += 1

        if nfired == 0:
            stat["  └ A类: 一条模板都没触发"] += 1
            category = "A"
        else:
            stat["  └ B类: 模板触发了但产物不对"] += 1
            category = "B"

        # 官能团增益分析
        try:
            rmols = [Chem.MolFromSmiles(s) for s in reactants]
            pmol = Chem.MolFromSmiles(products[0])
            if pmol is not None and all(m is not None for m in rmols):
                pv = frag_vec(pmol)
                rv_sum = [0] * len(FRAGS)
                for m in rmols:
                    for i, v in enumerate(frag_vec(m)):
                        if v > 0:
                            rv_sum[i] += v
                for i, (name, _) in enumerate(FRAGS):
                    d = pv[i] - rv_sum[i]
                    if d > 0:
                        gained[name] += 1
                    elif d < 0:
                        lost[name] += 1
                rr = sum(rdMolDescriptors.CalcNumRings(m) for m in rmols)
                pr_ = rdMolDescriptors.CalcNumRings(pmol)
                ring_change[pr_ - max(0, rr - 1)] += 1
        except Exception:
            pass

        rec = {"reaction_id": rid, "reactants": reactants,
               "expected": list(exp), "n_fired": nfired,
               "n_products_got": len(got)}
        if category == "A" and len(a_class) < 30:
            a_class.append(rec)
        if category == "B" and len(b_class) < 15:
            b_class.append(rec)

print(f"可测 {n_test} 条，耗时 {time.time()-t0:.0f}s\n")

# ---------------- 报告 ----------------
print("=" * 92)
print("★ 未命中的构成（这决定补法）★")
print("=" * 92)
miss = stat["未命中"]
a = stat["  └ A类: 一条模板都没触发"]
b = stat["  └ B类: 模板触发了但产物不对"]
print(f"  命中     {stat['命中']:>5}  ({stat['命中']/n_test*100:.1f}%)")
print(f"  未命中   {miss:>5}  ({miss/n_test*100:.1f}%)")
if miss:
    print(f"     A 类（无模板匹配底物）  {a:>5}  ({a/miss*100:.1f}% of miss)")
    print(f"     B 类（匹配了但产物错）  {b:>5}  ({b/miss*100:.1f}% of miss)")
print()
print("  未命中时触发的模板条数分布:")
for k in sorted(fire_hist):
    label = "0 条（A类）" if k == 0 else ("≥10 条" if k == 10 else f"{k} 条")
    print(f"      {label:<14} {fire_hist[k]}")

print()
print("=" * 92)
print("A 类缺失的化学：产物中【新出现】的官能团（RDKit 权威 fragment 定义）")
print("=" * 92)
for name, v in gained.most_common(25):
    print(f"      {v:>5}  {name}")
print()
print("  同时【消失】的官能团（前 15）:")
for name, v in lost.most_common(15):
    print(f"      {v:>5}  {name}")

print()
print("=" * 92)
print("A 类未命中实例（一条模板都没触发的）")
print("=" * 92)
for e in a_class[:14]:
    print(f"  {e['reaction_id']}  触发模板 {e['n_fired']} 条")
    print(f"      底物: {e['reactants']}")
    print(f"      真实产物: {e['expected']}")
    print()

enum.close()
con.close()

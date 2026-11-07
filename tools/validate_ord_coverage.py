# -*- coding: utf-8 -*-
r"""★ P0：用 ORD 真实文献反应做泛化验收 ★

这才是回答"反应全不全面"的测试：
  SmartReact 的 9770 条模板是从【它自己的 example】抽出来的，
  拿自己的例子考自己必然 ~100%（已验证）。
  必须拿【模板没见过的真实反应】去考。

方法（每条 ORD 反应）：
  1. 从 inputs 里取 reaction_role=REACTANT 的组分  -> 底物
  2. 从 outcomes 里取 products                     -> 真实产物
  3. 恰好 2 个底物时，喂进 ReactionEnumerator.enumerate_pair
  4. 看真实产物能否被枚举出来

指标：
  · 覆盖命中率 = 能复现的反应 / 可测反应
  · 命中的模板是哪些（看规则库的覆盖面偏向）

跨全部 53 个文件按行数比例抽样，保证化学多样性（不只依赖那个 177 万行的大文件）。

用法: python validate_ord_coverage.py [抽样总数]
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

TARGET_TOTAL = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
REPORTS = STAGE / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)
OUT = REPORTS / "ord_coverage_validation.json"

_rf = reaction_pb2.Compound.DESCRIPTOR.fields_by_name["reaction_role"]
_role_enum = _rf.enum_type


def role_name(n):
    v = _role_enum.values_by_number.get(n)
    return v.name if v else f"<{n}>"


def canon(smi):
    """规范化 SMILES（并清掉原子映射号，避免写法差异）。"""
    try:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(m)
    except Exception:
        return None


# ---------------- 选文件、按比例定抽样数 ----------------
ORD = STAGE / "ord-data"
pq = sorted((ORD / "data").rglob("*.parquet"))

con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")

plan = []
total_rows = 0
for p in pq:
    try:
        n = con.execute(
            f"SELECT num_rows FROM parquet_file_metadata('{p.as_posix()}')").fetchone()[0]
    except Exception:
        n = 0
    plan.append((p, n))
    total_rows += n

print("=" * 78)
print(f"ORD 泛化验收 —— 目标抽样 {TARGET_TOTAL} 条（全库 {total_rows:,} 条）")
print("=" * 78)

quota = []
for p, n in plan:
    if n <= 0:
        continue
    k = max(20, round(TARGET_TOTAL * n / total_rows)) if n > 40 else n
    quota.append((p, min(k, n)))
print(f"覆盖 {len(quota)} 个文件，配额合计 {sum(k for _, k in quota)} 条\n")

# ---------------- 跑 ----------------
enum = ReactionEnumerator()
stat = Counter()
hit_templates = Counter()
by_nreact = defaultdict(lambda: [0, 0])   # n_reactants -> [可测, 命中]
miss_examples = []
t0 = time.time()
n_seen = 0

for p, k in quota:
    try:
        rows = con.execute(
            f"SELECT reaction_id, reaction FROM read_parquet('{p.as_posix()}') "
            f"USING SAMPLE {k} ROWS").fetchall()
    except Exception:
        rows = con.execute(
            f"SELECT reaction_id, reaction FROM read_parquet('{p.as_posix()}') "
            f"LIMIT {k}").fetchall()

    for rid, blob in rows:
        n_seen += 1
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            stat["protobuf 解析失败"] += 1
            continue

        # 底物：role == REACTANT
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

        # 产物
        products = []
        for oc in rxn.outcomes:
            for pr in oc.products:
                smi = next((ci.value for ci in pr.identifiers
                            if ci.type == reaction_pb2.CompoundIdentifier.SMILES), None)
                if smi is None:
                    smi = next((ci.value for ci in pr.identifiers), None)
                if smi:
                    products.append(smi)

        if not products:
            stat["无产物(跳过)"] += 1
            continue

        nr = len(reactants)
        if nr != 2:
            stat[f"底物数={nr}(跳过)"] += 1
            if 1 <= nr <= 4:
                by_nreact[nr][0] += 0   # 不可测，不计入
            continue

        exp = {canon(x) for x in products} - {None}
        if not exp:
            stat["产物SMILES非法(跳过)"] += 1
            continue

        by_nreact[2][0] += 1
        try:
            res = enum.enumerate_pair(reactants[0], reactants[1])
        except Exception as ex:
            stat[f"枚举异常:{type(ex).__name__}"] += 1
            continue

        got = set()
        hit_names = set()
        for r in res:
            for pr in r.products:
                cp = canon(pr)
                if cp:
                    got.add(cp)
                    if cp in exp:
                        hit_names.add(r.reaction_name)
        if got & exp:
            stat["命中"] += 1
            by_nreact[2][1] += 1
            for nm in hit_names:
                hit_templates[nm] += 1
        else:
            stat["未命中"] += 1
            if len(miss_examples) < 25:
                miss_examples.append({
                    "reaction_id": rid,
                    "file": p.name,
                    "reactants": reactants,
                    "expected": list(exp),
                    "n_enumerated": len(got),
                })

        if n_seen % 500 == 0:
            el = time.time() - t0
            print(f"  已处理 {n_seen}  命中 {stat['命中']}  未命中 {stat['未命中']}  "
                  f"耗时 {el:.0f}s", flush=True)

el = time.time() - t0
print(f"\n跑完，共处理 {n_seen} 条，耗时 {el/60:.1f} 分钟\n")

# ---------------- 汇总 ----------------
testable = by_nreact[2][0]
hits = by_nreact[2][1]

print("=" * 78)
print("总成绩")
print("=" * 78)
print(f"  抽样处理          {n_seen}")
print(f"  可测（恰 2 底物）  {testable}")
print(f"  ├ 命中            {hits}")
print(f"  └ 未命中          {testable - hits}")
if testable:
    print(f"\n  ★★ ORD 覆盖率（泛化命中率）= {hits/testable*100:.1f}% ★★")
print()
print("  跳过原因分布:")
for k, v in stat.most_common(12):
    print(f"      {k:<28} {v}")

print()
print("=" * 78)
print("命中的是哪些模板（覆盖面偏向）")
print("=" * 78)
for k, v in hit_templates.most_common(25):
    print(f"      {v:>5}  {k}")

OUT.write_text(json.dumps({
    "sampled": n_seen,
    "testable": testable,
    "hits": hits,
    "coverage": (hits / testable) if testable else None,
    "stat": dict(stat),
    "hit_templates": dict(hit_templates),
    "miss_examples": miss_examples,
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n明细已存: {OUT}")

enum.close()
con.close()

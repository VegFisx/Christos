# -*- coding: utf-8 -*-
r"""第十二轮（探针）：ORD 里 DEAD / PPh3 是按什么【角色】声明的？

背景：覆盖率口径沿用 build_condition_table.py 的
      「声明为 REACTANT、但原子没进产物」。
      实测结果：mitsunobu 1831 条里 PPh3 覆盖 59%，但 DEAD 只有 18% —— 明显偏低。
      假设：很多记录把 DEAD 声明成 REAGENT（不是 REACTANT），被口径漏掉了。
本探针只回答这一件事：按 role 分类计数（不猜）。

口径：扫描前 N 条（默认 400000，与覆盖率表同一批），
      对每个 input 的每个 component 的 SMILES 片段跑角色 SMARTS，
      统计命中时该 input 的 reaction_role。

用法: python probe_input_roles.py [N]
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"

PATTERNS = {
    "azodicarboxylate(DEAD/DIAD)": Chem.MolFromSmarts("[NX2]=[NX2][CX3](=[OX1])[OX2]"),
    "phosphine(PPh3/PBu3)": Chem.MolFromSmarts("[PX3]([#6])([#6])[#6]"),
    "borohydride": Chem.MolFromSmarts("[BH1,BH2,BH3,BH4]"),
}
N = int(sys.argv[1]) if len(sys.argv) > 1 else 400000


def role_name(key: str) -> str:
    """这份 ord_schema 的 ReactionInput **没有 reaction_role 字段** —— 角色写在 inputs 的 key 里
    （实测：DESCRIPTOR 里只有 components/addition_* 等）。所以这里规范化 key。"""
    s = str(key).strip().lower()
    for known in ("reactant", "reagent", "solvent", "catalyst", "workup", "product",
                  "internal standard", "authentic standard"):
        if s.startswith(known):
            return known
    return s or "<空 key>"

con = duckdb.connect()
con.execute("SET memory_limit='1000MB'")
con.execute("SET threads=2")
cur = con.execute(f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') LIMIT {N}")

roles = {k: Counter() for k in PATTERNS}
recs_with = Counter()
n_parsed = 0
t0 = time.time()
while True:
    rows = cur.fetchmany(5000)
    if not rows:
        break
    for (blob,) in rows:
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            continue
        n_parsed += 1
        seen = set()
        for key, inp in rxn.inputs.items():
            role = role_name(key)
            for comp in inp.components:
                smis = [i.value for i in comp.identifiers
                        if i.type in (reaction_pb2.CompoundIdentifier.SMILES,
                                      reaction_pb2.CompoundIdentifier.CXSMILES) and i.value]
                for smi in smis:
                    for frag in smi.split("."):
                        m = Chem.MolFromSmiles(frag)
                        if m is None:
                            continue
                        for pname, patt in PATTERNS.items():
                            if patt is not None and m.HasSubstructMatch(patt):
                                roles[pname][role] += 1
                                seen.add(pname)
        for pname in seen:
            recs_with[pname] += 1
    if n_parsed % 100000 < 5000:
        print(f"  {n_parsed:,}  {time.time()-t0:.0f}s", flush=True)

print()
print("=" * 96)
print(f"扫描 {n_parsed:,} 条，用时 {time.time()-t0:.0f}s")
print("=" * 96)
for pname in PATTERNS:
    tot = sum(roles[pname].values())
    print(f"{pname}：命中片段 {tot:,} 次，出现在 {recs_with[pname]:,} 条记录里")
    for role, n in roles[pname].most_common():
        print(f"    {role:<20} {n:,}  ({n/tot:.0%})")
    print()
print("结论口径：若某个角色占了绝大多数，说明覆盖率口径漏了它。")
print(json.dumps({"n_scanned": n_parsed,
                  "roles": {k: dict(v) for k, v in roles.items()},
                  "records_with": dict(recs_with)},
                 ensure_ascii=False, indent=2))

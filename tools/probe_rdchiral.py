# -*- coding: utf-8 -*-
r"""验证 RDChiral 能否在 ORD 的原子映射反应上抽模板。

RDChiral 是原子映射模板抽取的权威实现（AAM 论文配套），不自己写。
先拿几条 ORD 反应试通。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402

RDLogger.DisableLog("rdApp.*")

print("尝试导入 rdchiral …")
try:
    from rdchiral.template_extractor import extract_from_reaction
    print("  ✓ rdchiral.template_extractor.extract_from_reaction")
except Exception as ex:
    print(f"  ✗ {type(ex).__name__}: {ex}")
    sys.exit(1)


def split_rxn(cx):
    body = cx[:cx.index("|")] if "|" in cx else cx
    parts = [p for p in body.split(">") if p.strip()]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return None, None, None


BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
con = duckdb.connect()
con.execute("SET memory_limit='1200MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE 400 ROWS"
).fetchall()

done = 0
ok = 0
fails = []
for (blob,) in rows:
    if done >= 8:
        break
    rxn = reaction_pb2.Reaction()
    rxn.ParseFromString(blob)
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES), None)
    if cx is None:
        continue
    lhs, agents, rhs = split_rxn(cx)
    if not lhs or not rhs:
        continue

    # 只要贡献原子到产物的组分作为 reactants
    pm = Chem.MolFromSmiles(rhs)
    if pm is None:
        continue
    pmaps = {a.GetAtomMapNum() for a in pm.GetAtoms() if a.GetAtomMapNum() > 0}
    if not pmaps:
        continue
    keep = []
    for s in (x for x in lhs.split(".") if x):
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        maps = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() > 0}
        if maps and len(maps & pmaps) / len(maps) > 0.5:
            keep.append(s)
    if len(keep) != 2:
        continue

    done += 1
    d = {"reactants": ".".join(keep), "reagents": agents or "", "products": rhs,
         "_id": f"x{done}"}
    print("=" * 90)
    print(f"【{done}】reactants ({len(keep)} 个):")
    for s in keep:
        print(f"    {s[:110]}")
    print(f"  products: {rhs[:110]}")
    for radius in (1, 2):
        try:
            t = extract_from_reaction(d, radius=radius, template_format="smarts")
            rs = t.get("reaction_smarts", "")
            print(f"  radius={radius} -> {rs[:220]}")
            ok += 1
        except Exception as ex:
            fails.append(f"{type(ex).__name__}: {str(ex)[:120]}")
            print(f"  radius={radius} ✗ {type(ex).__name__}: {str(ex)[:120]}")
    print()

print("=" * 90)
print(f"抽取调用成功 {ok} 次，失败 {len(fails)} 次")
for f in fails[:5]:
    print(f"   {f}")

con.close()

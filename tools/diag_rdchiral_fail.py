# -*- coding: utf-8 -*-
r"""诊断：为什么 RDChiral 在 ORD 反应上抽不出模板。"""
import sys
import traceback
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
import rdchiral.template_extractor as te  # noqa: E402
from rdchiral.template_extractor import extract_from_reaction  # noqa: E402

RDLogger.DisableLog("rdApp.*")
te.VERBOSE = True


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
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE 300 ROWS"
).fetchall()

shown = 0
for (blob,) in rows:
    if shown >= 5:
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

    shown += 1
    print("=" * 92)
    print(f"【{shown}】")
    print(f"  reactants ({len(keep)}): {'.'.join(keep)[:180]}")
    print(f"  products: {rhs[:180]}")
    print(f"  agents: {agents[:80]}")

    # 产物里未映射原子数（rdchiral 上限 5）
    for pi, ps in enumerate(x for x in rhs.split(".") if x):
        m = Chem.MolFromSmiles(ps)
        if m is None:
            print(f"    产物片段{pi} 解析失败")
            continue
        n_un = sum(1 for a in m.GetAtoms() if a.GetAtomMapNum() == 0)
        print(f"    产物片段{pi}: 原子 {m.GetNumAtoms()}，未映射 {n_un}")

    print("  --- 调用 extract_from_reaction ---")
    try:
        out = extract_from_reaction({
            "reactants": ".".join(keep), "reagents": agents or "",
            "products": rhs, "_id": f"d{shown}",
        })
        print(f"  返回: {type(out)}")
        if out is None:
            print("  ✗ 返回 None")
        elif "reaction_smarts" not in out:
            print(f"  ✗ 没有 reaction_smarts，键 = {list(out.keys())}")
        else:
            print(f"  ✓ {out['reaction_smarts'][:200]}")
    except Exception as ex:
        print(f"  ✗ 异常 {type(ex).__name__}: {ex}")
        traceback.print_exc()
    print()

te.VERBOSE = False
con.close()

# -*- coding: utf-8 -*-
r"""查：为什么 mitsunobu 抓不到 PPh3 / DEAD？

假设：这些试剂在 ORD 里被标成 REACTANT，而不是 REAGENT，
      而我只采集了 SOLVENT/CATALYST/REAGENT 三种角色 -> 漏掉了。
"""
import sys
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

_ci = reaction_pb2.CompoundIdentifier
_rf = reaction_pb2.Compound.DESCRIPTOR.fields_by_name["reaction_role"]
_re = _rf.enum_type
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"


def role_name(n):
    v = _re.values_by_number.get(n)
    return v.name if v else f"<{n}>"


def label_of(c):
    name, smi = None, None
    for x in c.identifiers:
        tn = _ci.CompoundIdentifierType.Name(x.type)
        if "NAME" in tn.upper() and x.value:
            name = x.value
        if "SMILES" in tn.upper() and x.value:
            smi = x.value
    if name:
        return name, smi
    return None, smi


def split_rxn(cx):
    body = cx[:cx.index("|")] if "|" in cx else cx
    parts = [p for p in body.split(">") if p.strip()]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return None, None, None


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


con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE 4000 ROWS"
).fetchall()

enum = ReactionEnumerator()
role_counter = Counter()
shown = 0

for (blob,) in rows:
    if shown >= 4:
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
    product = canon(rhs)
    if product is None:
        continue
    contribs = []
    for s in (x for x in lhs.split(".") if x):
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        maps = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() > 0}
        if maps and len(maps & pmaps) / len(maps) > 0.5:
            cs = canon(s)
            if cs:
                contribs.append(cs)
    if len(contribs) != 2:
        continue

    try:
        res = enum.enumerate_pair(*sorted(contribs))
    except Exception:
        continue
    hit = any(canon(p) == product for r in res for p in r.products
              if r.reaction_name == "mitsunobu")
    if not hit:
        continue

    shown += 1
    print("=" * 92)
    print(f"【mitsunobu 命中 {shown}】产物: {product[:90]}")
    print(f"  2 个贡献原子到产物的组分: {[c[:50] for c in sorted(contribs)]}")
    print(f"  该 ORD 反应的【全部】输入组分：")
    for key, inp in rxn.inputs.items():
        for c in inp.components:
            nm, smi = label_of(c)
            rn = role_name(c.reaction_role)
            role_counter[rn] += 1
            cs = canon(smi) if smi else None
            is_contrib = cs in contribs if cs else False
            mark = "★贡献" if is_contrib else "   旁观"
            # 找含磷的
            phos = ""
            if smi and ("P(" in smi or "[P" in smi or "p(" in smi.lower()):
                phos = "  ←含磷"
            print(f"     key='{key}' 角色={rn:<16}{mark}  {nm or '(无名)'}  "
                  f"{(smi or '')[:55]}{phos}")
    print()

print("=" * 92)
print("这些反应里出现过的角色统计：")
for r, c in role_counter.most_common():
    print(f"   {r:<20} {c}")

enum.close()
con.close()

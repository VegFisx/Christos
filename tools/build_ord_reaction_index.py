# -*- coding: utf-8 -*-
r"""建 **ORD 反应先例索引**：产物 → 反应物集合 + 条件样例（第七十五轮）。

用途（用户 2026-10-17）：「没有反应条件说什么也白费」——用**真实做过的反应**当行为标签：
某条切断若能对上 ORD 里的记录反应（产物相同、反应物集合相同），就是"有人做过"。

必须用 **venv 3.12**（duckdb + ord_schema + rdkit）：

    D:\TCMAI\venv\Scripts\python.exe tools\build_ord_reaction_index.py --limit 5000
    D:\TCMAI\venv\Scripts\python.exe tools\build_ord_reaction_index.py

产出：`data\ord_reaction_index.jsonl`，每行：
    {"rid","products":[…规范 SMILES…],"reactants":[…],"catalysts":[…],
     "reagents":[…],"solvents":[…],"temp":"…","n_reactants":N}
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\libs")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import duckdb
from rdkit import Chem, RDLogger
from ord_schema.proto import reaction_pb2

RDLogger.DisableLog("rdApp.*")
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
PQ = (STAGE / "ord-data" / "data" / "11"
      / "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet")
OUT = STAGE / "data" / "ord_reaction_index.jsonl"

ROLE = reaction_pb2.ReactionRole
IDT = reaction_pb2.CompoundIdentifier


def canon(smi: str) -> str:
    m = Chem.MolFromSmiles(smi) if smi else None
    return Chem.MolToSmiles(m) if m else ""


def smiles_of(c) -> str:
    for x in c.identifiers:
        if x.type == IDT.SMILES and x.value:
            return x.value
    return ""


def name_of(c) -> str:
    for x in c.identifiers:
        if x.type == IDT.NAME and x.value:
            return x.value
    return smiles_of(c)


def row_of(rid: str, blob: bytes):
    r = reaction_pb2.Reaction()
    try:
        r.ParseFromString(blob)
    except Exception:                                        # noqa: BLE001
        return None
    reactants, cats, reag, solv = [], [], [], []
    for inp in r.inputs.values():
        for c in inp.components:
            rn = c.reaction_role
            if rn == ROLE.REACTANT:
                s = smiles_of(c)
                if s:
                    reactants.append(s)
            elif rn == getattr(ROLE, "CATALYST", -99):
                nm = name_of(c)
                if nm:
                    cats.append(nm)
            elif rn == ROLE.REAGENT:
                nm = name_of(c)
                if nm:
                    reag.append(nm)
            elif rn == getattr(ROLE, "SOLVENT", -98):
                nm = name_of(c)
                if nm:
                    solv.append(nm)
    prods = []
    for oc in r.outcomes:
        for p in oc.products:
            s = smiles_of(p)
            if s:
                prods.append(s)
    if not prods or not reactants:
        return None
    temp = ""
    if r.conditions.HasField("temperature") and r.conditions.temperature.HasField("setpoint"):
        sp = r.conditions.temperature.setpoint
        temp = "%g %s" % (sp.value, sp.units)
    return {"rid": rid,
            "products": sorted({canon(s) for s in prods if canon(s)}),
            "reactants": sorted({canon(s) for s in reactants if canon(s)}),
            "catalysts": sorted(set(cats))[:4], "reagents": sorted(set(reag))[:6],
            "solvents": sorted(set(solv))[:3], "temp": temp}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 行（0=全量）")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    con = duckdb.connect(":memory:")
    q = "SELECT reaction_id, reaction FROM read_parquet(?)"
    if a.limit:
        q += " LIMIT %d" % a.limit
    t0 = time.time()
    n = bad = 0
    with open(a.out, "w", encoding="utf-8") as fh:
        for rid, blob in con.execute(q, [str(PQ)]).fetchall():
            n += 1
            d = row_of(rid, blob)
            if not d:
                bad += 1
            else:
                fh.write(json.dumps(d, ensure_ascii=False) + "\n")
            if n % 50000 == 0:
                el = time.time() - t0
                print("  ... %d 行（%.0fs，%.0f 行/s，丢弃 %d）"
                      % (n, el, n / max(1e-9, el), bad))
    el = time.time() - t0
    print("完成：%d 行，丢弃 %d（无产物/无反应物/解析失败），用时 %.0fs -> %s"
          % (n, bad, el, a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

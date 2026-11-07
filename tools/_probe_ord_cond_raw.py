# -*- coding: utf-8 -*-
r"""一次性探针：先打印【原始记录】原文（yields / conditions / inputs 角色），再谈统计。

用法: python tools\_probe_ord_cond_raw.py [抽样数] [seed] [打印条数]
"""
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
for _p in (STAGE / "libs", STAGE / "tools"):
    sys.path.insert(0, str(_p))

import duckdb  # noqa: E402
from google.protobuf import text_format  # noqa: E402
from ord_schema.proto import reaction_pb2 as R  # noqa: E402

import ord_condition_dataset as ocd  # noqa: E402  （复用条件解析，不重写）
import mapped_chem as mc  # noqa: E402

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"

N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20261012
KRAW = int(sys.argv[3]) if len(sys.argv) > 3 else 5


def clip(s, n):
    s = s.replace("\n", " | ")
    return s if len(s) <= n else s[:n] + f" ...[裁剪,原文{len(s)}字符]"


def main():
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    rows = con.execute(
        f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') "
        f"USING SAMPLE {N} ROWS (reservoir, {SEED})").fetchall()
    print(f"抽样 {len(rows)} 条 seed={SEED}")

    role_counts = Counter()
    temp_units = Counter()
    temp_src = Counter()
    n_raw = 0
    n_cx = 0
    n_with_solvcomp = 0
    n_with_temp = 0
    t0 = time.time()
    for (blob,) in rows:
        rxn = R.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            continue
        cx = next((i.value for i in rxn.identifiers
                   if i.type == R.ReactionIdentifier.REACTION_CXSMILES and i.value), None)
        if not cx:
            continue
        n_cx += 1
        lhs, agents, rhs = mc.split_rxn(cx)

        # ---- 角色枚举反查（复用 ocd 的 field descriptor 方案）----
        roles = []
        for _, inp in rxn.inputs.items():
            for comp in inp.components:
                rn = ocd.ROLE_NAME.get(comp.reaction_role, "?")
                role_counts[rn] += 1
                if rn == "SOLVENT":
                    sn, sm = ocd._compound_smiles_name(comp)
                    roles.append(("SOLVENT", sn, sm))
        if roles:
            n_with_solvcomp += 1

        tc = rxn.conditions.temperature
        tval = None
        if tc.HasField("setpoint"):
            tval = ocd._temp_to_celsius(tc.setpoint, temp_units)
            temp_src["setpoint" if tval is not None else "setpoint_单位未知"] += 1
        if tval is None and tc.measurements:
            for t in tc.measurements:
                tval = ocd._temp_to_celsius(t, temp_units)
                if tval is not None:
                    temp_src["measurement"] += 1
                    break
        if tval is not None:
            n_with_temp += 1

        if n_raw < KRAW:
            n_raw += 1
            print("\n" + "=" * 78)
            print(f"[原始记录 {n_raw}]  temp_C={tval!r}  temp_source={temp_src and ''}"
                  f"setpoint_field={tc.HasField('setpoint')}  "
                  f"n_meas={len(tc.measurements)}  n_inputs={len(rxn.inputs)}")
            print("--- identifiers（原文）---")
            for i in rxn.identifiers:
                print("   type=%s  value=%s" % (
                    ocd.RXN_IDENT_TYPE_NAME.get(i.type, "?"), clip(i.value, 180)))
            print("--- inputs 组分角色（原文 NAME/SMILES 摘要）---")
            for k, inp in rxn.inputs.items():
                print(f"   input key={k!r}  n_components={len(inp.components)}")
                for comp in inp.components:
                    rn = ocd.ROLE_NAME.get(comp.reaction_role, "?")
                    sm, nm = ocd._compound_smiles_name(comp)
                    print(f"      role={rn!r} name={nm!r} smiles={clip(str(sm), 90)!r}")
                    if comp.amount.HasField("volume"):
                        print(f"         amount.volume={comp.amount.volume.value}"
                              f" units={comp.amount.volume.units}")
            print("--- outcomes（含 yield 原文）---")
            # ★ 坑：RepeatedCompositeContainer 没有 DESCRIPTOR，不能整体 MessageToString
            for oi, oc in enumerate(rxn.outcomes):
                print(f"   [outcome {oi}] " + clip(text_format.MessageToString(oc), 1500))
            print("--- conditions（原文）---")
            print("   " + clip(text_format.MessageToString(rxn.conditions), 1200))

    print("\n" + "=" * 78)
    print(f"抽样 {len(rows)}  有CXSMILES {n_cx}  有SOLVENT组分 {n_with_solvcomp}  "
          f"有温度 {n_with_temp}  {time.time()-t0:.0f}s")
    print(f"role_counts={dict(role_counts.most_common(8))}")
    print(f"temp_units={dict(temp_units)}")
    print(f"temp_source={dict(temp_src)}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

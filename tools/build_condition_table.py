# -*- coding: utf-8 -*-
r"""给每种 SmartReact 反应类型建【条件表】——数据驱动，不手写。

两个来源：
  A. 模板自带的 reactant_categories（作者给的类别名）
  B. ★ ORD 真实实验条件 ★：对每种类型，统计被它复现的那些 ORD 反应
     实际用了什么溶剂 / 催化剂 / 试剂 / 温度

输出 conditions_by_reaction_type.json，供预测工具标注条件。

用法: python build_condition_table.py [ORD抽样数]
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
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
OUT = STAGE / "reports" / "conditions_by_reaction_type.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

_ci = reaction_pb2.CompoundIdentifier
_rf = reaction_pb2.Compound.DESCRIPTOR.fields_by_name["reaction_role"]
_re = _rf.enum_type


def role_name(n):
    v = _re.values_by_number.get(n)
    return v.name if v else f"<{n}>"


def comp_info(c):
    """返回 (可读名, 规范SMILES)。优先 NAME 类标识符。"""
    name, smi = None, None
    for x in c.identifiers:
        try:
            tn = _ci.CompoundIdentifierType.Name(x.type)
        except Exception:
            tn = str(x.type)
        if "NAME" in tn.upper() and x.value:
            name = x.value
        if "SMILES" in tn.upper() and x.value:
            smi = x.value
    cs = None
    if smi:
        m = Chem.MolFromSmiles(smi)
        cs = Chem.MolToSmiles(m) if m is not None else None
    return (name or cs or smi), cs


def comp_label(c):
    return comp_info(c)[0]


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


# ---------------- A. 模板自带的类别 ----------------
P = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
cat_by_type = defaultdict(Counter)
for line in P.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
    f = line.split("\t")
    if len(f) == 5:
        for cat in f[4].split("."):
            cat = cat.strip()
            if cat:
                cat_by_type[f[0]][cat] += 1
print(f"模板类别：覆盖 {len(cat_by_type)} 种反应类型")

# ---------------- B. ORD 真实条件 ----------------
con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE {N} ROWS"
).fetchall()
print(f"ORD 抽样 {len(rows)} 条\n")

enum = ReactionEnumerator()
cond = defaultdict(lambda: {
    "n_matched": 0,
    "solvents": Counter(), "catalysts": Counter(),
    "reagents": Counter(), "bases": Counter(),
    "aux_reactants": Counter(),          # ★ 被标成 REACTANT 但其实是试剂（如 PPh3/DEAD）
    "temps": [], "temp_units": Counter(),
    "times_min": [], "controls": Counter(), "ph": [], "reflux": 0,
})
seen = set()
t0 = time.time()
n_test = 0

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
    for s in (x for x in lhs.split(".") if x):
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        maps = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() > 0}
        if maps and len(maps & pmaps) / len(maps) > 0.5:
            cs = canon_nomap(s)
            if cs:
                contribs.append(cs)
    if len(contribs) != 2:
        continue
    r1, r2 = sorted(contribs)
    if (r1, r2, product) in seen:
        continue
    seen.add((r1, r2, product))
    n_test += 1

    try:
        res = enum.enumerate_pair(r1, r2)
    except Exception:
        continue

    hit_fams = set()
    for rr in res:
        for p in rr.products:
            if canon_nomap(p) == product:
                hit_fams.add(rr.reaction_name)
    if not hit_fams:
        continue

    # 抽取该 ORD 反应的条件
    # ★ 关键：按【是否贡献原子到产物】区分真反应物与辅助试剂，
    #   而不是只看声明的角色 —— ORD 里 PPh3/DEAD 常被标成 REACTANT
    contrib_set = {r1, r2}
    by_role = defaultdict(list)
    aux_reactants = Counter()
    for key, inp in rxn.inputs.items():
        for c in inp.components:
            lab, cs = comp_info(c)
            if not lab:
                continue
            role = role_name(c.reaction_role)
            k = key.strip().lower()
            if role == "SOLVENT":
                by_role["SOLVENT"].append((k, lab))
            elif role == "CATALYST":
                by_role["CATALYST"].append((k, lab))
            elif role == "REAGENT":
                by_role["REAGENT"].append((k, lab))
            elif role == "REACTANT" and cs not in contrib_set:
                # 声明是反应物、但原子没进产物 -> 实际上是试剂
                aux_reactants[lab] += 1
    temp = None
    tunits = ""
    control = None
    ph = None
    reflux = False
    time_min = None
    try:
        if rxn.HasField("conditions"):
            c = rxn.conditions
            if c.HasField("temperature"):
                tc = c.temperature
                if tc.HasField("setpoint"):
                    temp = tc.setpoint.value
                    try:
                        tunits = reaction_pb2.Temperature.TemperatureUnit.Name(tc.setpoint.units)
                    except Exception:
                        tunits = str(tc.setpoint.units)
                if tc.HasField("control"):
                    try:
                        control = reaction_pb2.TemperatureControl.TemperatureControlType.Name(
                            tc.control.type)
                    except Exception:
                        pass
            if c.HasField("ph"):
                ph = c.ph
            if c.HasField("reflux"):
                reflux = bool(c.reflux)
    except Exception:
        pass
    try:
        for oc in rxn.outcomes:
            if oc.HasField("reaction_time"):
                rt = oc.reaction_time
                u = reaction_pb2.Time.TimeUnit.Name(rt.units)
                mult = {"SECOND": 1 / 60, "MINUTE": 1, "HOUR": 60, "DAY": 1440}.get(u)
                if mult:
                    time_min = rt.value * mult
                break
    except Exception:
        pass

    for fam in hit_fams:
        d = cond[fam]
        d["n_matched"] += 1
        for key, lab in by_role.get("SOLVENT", []):
            d["solvents"][lab] += 1
        for key, lab in by_role.get("CATALYST", []):
            d["catalysts"][lab] += 1
        for key, lab in by_role.get("REAGENT", []):
            d["reagents"][lab] += 1
            if key in ("base", "碱"):
                d["bases"][lab] += 1
        for lab, n in aux_reactants.items():
            d["aux_reactants"][lab] += n
        if temp is not None:
            d["temps"].append(temp)
            d["temp_units"][tunits] += 1
        if control:
            d["controls"][control] += 1
        if ph is not None:
            d["ph"].append(ph)
        if reflux:
            d["reflux"] += 1
        if time_min is not None:
            d["times_min"].append(time_min)

print(f"可测 ORD 反应 {n_test} 条，耗时 {time.time()-t0:.0f}s\n")

# ---------------- 输出 ----------------
result = {}
for fam in sorted(set(list(cond) + list(cat_by_type))):
    d = cond.get(fam, {})
    temps = d.get("temps", []) or []
    times = d.get("times_min", []) or []
    phs = d.get("ph", []) or []
    entry = {
        "n_ord_matched": d.get("n_matched", 0),
        "template_categories": [c for c, _ in cat_by_type.get(fam, Counter()).most_common(8)],
        "solvents": [s for s, _ in (d.get("solvents") or Counter()).most_common(6)],
        "catalysts": [s for s, _ in (d.get("catalysts") or Counter()).most_common(6)],
        "reagents": [s for s, _ in (d.get("reagents") or Counter()).most_common(6)],
        "auxiliary_reagents": [s for s, _ in (d.get("aux_reactants") or Counter()).most_common(6)],
        "bases": [s for s, _ in (d.get("bases") or Counter()).most_common(4)],
        "controls": [s for s, _ in (d.get("controls") or Counter()).most_common(3)],
        "reflux_n": d.get("reflux", 0),
        "temp_C": None if not temps else {
            "min": round(min(temps), 1),
            "median": round(statistics.median(temps), 1),
            "max": round(max(temps), 1),
            "n": len(temps),
            "units": [u for u, _ in (d.get("temp_units") or Counter()).most_common(2)],
        },
        "time_min": None if not times else {
            "median": round(statistics.median(times), 1),
            "min": round(min(times), 1),
            "max": round(max(times), 1),
            "n": len(times),
        },
        "ph": None if not phs else {
            "median": round(statistics.median(phs), 2),
            "min": round(min(phs), 2),
            "max": round(max(phs), 2),
            "n": len(phs),
        },
    }
    result[fam] = entry

OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

# 控制台摘要
print("=" * 94)
print("★ 各反应类型的条件表（来自 ORD 真实实验）")
print("=" * 94)
for fam, e in sorted(result.items(), key=lambda kv: -kv[1]["n_ord_matched"]):
    if e["n_ord_matched"] == 0 and not e["template_categories"]:
        continue
    print(f"\n【{fam}】  ORD 命中 {e['n_ord_matched']} 条")
    if e["temp_C"]:
        t = e["temp_C"]
        print(f"   温度: 中位 {t['median']} (范围 {t['min']}~{t['max']}, n={t['n']}) "
              f"单位 {t['units']}")
    else:
        print(f"   温度: 无数据")
    if e["controls"]:
        print(f"   控温方式: {', '.join(e['controls'])}   回流提及 {e['reflux_n']} 次")
    if e["time_min"]:
        tm = e["time_min"]
        print(f"   时间: 中位 {tm['median']} 分钟 (范围 {tm['min']}~{tm['max']}, n={tm['n']})")
    if e["ph"]:
        p = e["ph"]
        print(f"   pH: 中位 {p['median']} (范围 {p['min']}~{p['max']}, n={p['n']})")
    if e["solvents"]:
        print(f"   溶剂: {', '.join(e['solvents'][:5])}")
    if e["catalysts"]:
        print(f"   催化剂: {', '.join(e['catalysts'][:5])}")
    if e["bases"]:
        print(f"   碱: {', '.join(e['bases'][:4])}")
    if e["reagents"]:
        print(f"   试剂: {', '.join(e['reagents'][:5])}")
    if e["auxiliary_reagents"]:
        print(f"   ★辅助试剂(ORD标为REACTANT): {', '.join(e['auxiliary_reagents'][:5])}")
    if e["template_categories"]:
        print(f"   模板类别: {', '.join(e['template_categories'][:6])}")

print(f"\n已存: {OUT}")

enum.close()
con.close()

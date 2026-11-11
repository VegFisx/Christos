"""把「模板级」条件包络聚合成「反应类型级」条件包络。

为什么要这一步：`reports/template_conditions.json` 的键是**逐字的模板 SMARTS**，
而中药路径用的模板来自另一套挖掘池，两者只有 1.7% 能对上（甘草 2,176 个产物里 38 个）。
反应中心类型（成/断键条数 + 反应中心原子的元素/电荷/度/芳香/环/氢数）是跨语料可迁移的，
所以按类型聚合后再查，覆盖面会大得多。

口径两条，写清楚避免以后误读：
1. 类型签名取自**模板 SMARTS 的左侧与右侧**（rdchiral 挖出来的模板，括号里带了真实的 H 数与度）。
   与 `tools/bench_class_strata.py::class_sig` 用完整分子算的签名，在「同一反应类型」上应一致，
   但不是逐位相同（SMARTS 只保留模板化后的环境）。
2. 温度/时间只保留区间与样本数（各模板的直方图分箱不同，不能逐箱相加）；
   `n` 为落在该类型下的观测总数。

用法：
    python tools\build_envelope_type.py
输出：reports/envelope_types.json
"""

import io
import json
import os
import sys

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "reports", "template_conditions.json")
OUT = os.path.join(ROOT, "reports", "envelope_types.json")


def _atom_sig(a):
    """反应中心原子的指纹；SMARTS 里没写的属性会退化成默认值（0/False），这是已知近似。

    GetTotalNumHs() 在少数 SMARTS 上会因为隐式价态算不出来而抛 RuntimeError
    （本次实测踩到过：Failed Expression: d_implicitValence > -1），
    所以这里退回到显式氢数，宁可少一位信息也不让整张表崩掉。
    """
    try:
        hs = a.GetTotalNumHs()
    except Exception:                              # noqa: BLE001
        hs = a.GetNumExplicitHs()
    return (a.GetSymbol(), a.GetFormalCharge(), a.GetDegree(),
            a.GetIsAromatic(), a.IsInRing(), hs)


def _bonds(mol):
    out = {}
    atoms = {}
    for b in mol.GetBonds():
        a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
        m1, m2 = a1.GetAtomMapNum(), a2.GetAtomMapNum()
        if m1 and m2:
            out[(min(m1, m2), max(m1, m2))] = b.GetBondTypeAsDouble()
        if m1:
            atoms[m1] = a1
        if m2:
            atoms[m2] = a2
    return out, atoms


def type_of_smarts(smarts):
    """模板 SMARTS -> 反应中心类型签名；解析不了返回 None。"""
    if not smarts or ">>" not in smarts:
        return None
    left_s, right_s = smarts.split(">>", 1)
    left, right = Chem.MolFromSmarts(left_s), Chem.MolFromSmarts(right_s)
    if left is None or right is None:
        return None
    lb, latch = _bonds(left)
    rb, ratph = _bonds(right)
    if not lb and not rb:
        return None
    formed = [k for k in rb if k not in lb or abs(rb[k] - lb[k]) > 0.01]
    broken = [k for k in lb if k not in rb or abs(rb[k] - lb[k]) > 0.01]
    if not formed and not broken:
        return None
    idx = set()
    for a, b in formed + broken:
        idx.add(a)
        idx.add(b)
    sig = []
    for n in sorted(idx):
        at = ratph.get(n) or latch.get(n)
        if at is not None:
            sig.append(_atom_sig(at))
    if not sig:
        return None
    return repr((len(formed), len(broken), tuple(sorted(sig))))


def main() -> int:
    if not os.path.exists(SRC):
        print("缺 %s，先跑 tools\\build_template_conditions.py" % SRC)
        return 2
    table = json.load(io.open(SRC, encoding="utf-8"))
    print("模板 %d 条" % len(table))

    out = {}
    miss = 0
    for smarts, st in table.items():
        key = type_of_smarts(smarts)
        if key is None:
            miss += 1
            continue
        n = int(st.get("n") or 0)
        if n <= 0:
            continue
        cur = out.get(key)
        t_min, t_max = st.get("t_min"), st.get("t_max")
        tm_min, tm_max = st.get("tm_min"), st.get("tm_max")
        if cur is None:
            out[key] = {"n": n, "templates": 1,
                        "t_min": t_min, "t_max": t_max,
                        "tm_min": tm_min, "tm_max": tm_max}
            continue
        cur["n"] += n
        cur["templates"] += 1
        for field, val, pick in (("t_min", t_min, min), ("t_max", t_max, max),
                                 ("tm_min", tm_min, min), ("tm_max", tm_max, max)):
            if val is None:
                continue
            cur[field] = val if cur.get(field) is None else pick(cur[field], val)

    payload = {
        "generated_at": "2026-11-11",
        "source": "reports/template_conditions.json（由 reports/ord_condition_dataset 逐模板统计）",
        "note": "按反应中心类型聚合（成/断键条数 + 中心原子元素/电荷/度/芳香/环/氢数）；"
                "温度与时间只保留区间与样本数，不保留分布。",
        "template_rows": len(table),
        "unparsed": miss,
        "types": out,
    }
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(payload, ensure_ascii=False))
    sizes = sorted((v["n"] for v in out.values()), reverse=True)
    print("类型 %d 个；未解析模板 %d 条；观测 %d 条（最大类型 %s，中位 %s）"
          % (len(out), miss, sum(sizes), sizes[0] if sizes else 0,
             sizes[len(sizes) // 2] if sizes else 0))
    print("写出：%s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

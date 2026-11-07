# -*- coding: utf-8 -*-
r"""独立校验 mined_forward_templates_v2.jsonl（不依赖挖掘脚本的自述，自己重算一遍）。

用法: python chemreact-staging\tools\_verify_v2_templates.py
"""
import json
import sys
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
V1 = STAGE / "reports" / "mined_forward_templates.jsonl"
V2 = STAGE / "reports" / "mined_forward_templates_v2.jsonl"


def load(p):
    rows = []
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main():
    r1, r2 = load(V1), load(V2)
    print(f"v1 行数 {len(r1)}   v2 行数 {len(r2)}")
    print(f"v2 字段：{sorted(r2[0].keys())}")
    print(f"模板顺序前 5 是否与 v1 一致："
          f"{[a['template'] == b['template'] for a, b in zip(r1[:5], r2[:5])]}")

    d1 = {d["template"]: (d["support"], d["generalized"]) for d in r1}
    d2 = {d["template"]: (d["support"], d["generalized"]) for d in r2}
    print(f"template 集合：v1 {len(d1)}  v2 {len(d2)}  相同 {len(set(d1) & set(d2))}  "
          f"仅v1 {len(set(d1) - set(d2))}  仅v2 {len(set(d2) - set(d1))}")
    sup_mm = sum(1 for t in d1 if t in d2 and d1[t][0] != d2[t][0])
    gen_mm = sum(1 for t in d1 if t in d2 and d1[t][1] != d2[t][1])
    print(f"support 不一致 {sup_mm}   generalized 不一致 {gen_mm}   （期望都 0）")

    only1 = sorted(set(d1) - set(d2))
    only2 = sorted(set(d2) - set(d1))
    print(f"\n仅 v1 有的 {len(only1)} 条（含 support）：")
    for t in only1:
        print(f"   sup={d1[t][0]:>2}  {t}")
    print(f"仅 v2 有的 {len(only2)} 条（含 support）：")
    for t in only2:
        print(f"   sup={d2[t][0]:>2}  {t}")

    print("\n配对比较（按最长公共前缀配对；只看差异位置）：")

    def pair_up(x, y):
        n = 0
        while n < min(len(x), len(y)) and x[n] == y[n]:
            n += 1
        return n

    def diffs(a, b):
        """返回两串的差异片段（去掉公共前缀/后缀后）。"""
        p = pair_up(a, b)
        s = 0
        while (s < min(len(a), len(b)) - p
               and a[len(a) - 1 - s] == b[len(b) - 1 - s]):
            s += 1
        return a[p:len(a) - s], b[p:len(b) - s]

    for a in only1:
        # 用最长公共前缀最长的来配对
        best = max(only2, key=lambda b: pair_up(a, b))
        da, db = diffs(a, best)
        ga, gb = d1[a][1], d2[best][1]
        print(f"   v1 sup={d1[a][0]} vs v2 sup={d2[best][0]}  差异片段 {da!r} <-> {db!r}")
        print(f"      去掉所有 '@' 后完全相同："
              f"{a.replace('@', '') == best.replace('@', '')}")
        print(f"      generalized 完全相同：{ga == gb}")

    bad = Counter()
    cov = Counter()
    for d in r2:
        cov["total"] += 1
        n_src, nt, ns = d["n_src"], d["n_temp_known"], d["n_solv_known"]
        if n_src != d["support"]:
            bad["n_src!=support"] += 1
        if nt > n_src or ns > n_src:
            bad["known>n_src"] += 1
        t = d["temp_C"]
        if (t is None) != (nt == 0):
            bad["temp_C为null与n_temp_known不匹配"] += 1
        if t is not None:
            if t["n"] != nt:
                bad["temp_C.n != n_temp_known"] += 1
            seq = [t["min"], t["p25"], t["median"], t["p75"], t["max"]]
            if seq != sorted(seq):
                bad["分位数非单调"] += 1
            if not (-273.15 <= t["min"] and t["max"] <= 1200):
                bad["温度越界"] += 1
        if (len(d["solvents"]) > 0) != (ns > 0):
            bad["solvents空与n_solv_known不匹配"] += 1
        if sum(d["solvents"].values()) < ns:
            bad["溶剂计数<可得记录数"] += 1
        cov["有温度分布" if nt else "无温度分布"] += 1
        cov["有溶剂分布" if ns else "无溶剂分布"] += 1
        cov["温度溶剂都有" if (nt and ns) else "不齐全"] += 1
        cov["温度n>=2" if nt >= 2 else "温度n<2"] += 1
        cov["温度n>=3" if nt >= 3 else "温度n<3"] += 1
    print(f"v2 自洽性异常：{dict(bad) if bad else '无（全 0）'}")
    print(f"v2 全档覆盖：{ {k: cov[k] for k in sorted(cov)} }")

    # ---- 引擎默认 K1 档（加载 600 -> 编译 590）独立重算 ----
    import importlib.util
    lib_py = STAGE / "tools" / "rdkit_template_lib.py"
    spec = importlib.util.spec_from_file_location("rdkit_template_lib", lib_py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rdkit_template_lib"] = mod
    spec.loader.exec_module(mod)
    tpls = mod.load_mined_templates(V1, min_support=1, limit=600)
    compiled, n_fail = mod.compile_templates(tpls)
    k1 = Counter()
    full2 = {d["template"]: d for d in r2}
    for sm, _rx in compiled:
        e = full2.get(sm)
        k1["K1总数"] += 1
        if e is None:
            k1["不在v2"] += 1
            continue
        v2row = e
        k1["有温度分布" if v2row["n_temp_known"] else "无温度分布"] += 1
        k1["有溶剂分布" if v2row["n_solv_known"] else "无溶剂分布"] += 1
        k1["温度溶剂都有" if (v2row["n_temp_known"] and v2row["n_solv_known"]) else "不齐全"] += 1
        if v2row["n_temp_known"] >= 3:
            k1["温度n>=3"] += 1
    print(f"引擎 K1 档：加载 {len(tpls)}  编译通过 {len(compiled)}  编译失败 {n_fail}")
    print(f"  条件覆盖：{dict(k1)}")

    # ---- 报告用聚合（全部现场重算，不手抄）----
    n_src = sum(d["n_src"] for d in r2)
    n_t = sum(d["n_temp_known"] for d in r2)
    n_s = sum(d["n_solv_known"] for d in r2)
    print(f"\n来源记录合计 {n_src}；其中有温度 {n_t}（{n_t/n_src:.1%}）、"
          f"有溶剂 {n_s}（{n_s/n_src:.1%}）")
    solv, solv_smi = Counter(), Counter()
    for d in r2:
        for k, v in d["solvents"].items():
            solv[k] += v
        for k, v in d["solvent_smiles"].items():
            solv_smi[k] += v
    print(f"不同溶剂名 {len(solv)} 个，不同溶剂 SMILES {len(solv_smi)} 个")
    print(f"溶剂名 top10：{solv.most_common(10)}")

    iqrs, spans, meds = [], [], []
    for sm, _rx in compiled:
        e = full2.get(sm)
        if not e or not e["temp_C"]:
            continue
        t = e["temp_C"]
        meds.append(t["median"])
        if t["n"] >= 2:
            iqrs.append(t["p75"] - t["p25"])
            spans.append(t["max"] - t["min"])
    for arr in (iqrs, spans, meds):
        arr.sort()
    med = lambda a: (a[len(a) // 2] if a else None)
    print(f"K1 档温度分布：有温度 {k1['有温度分布']}/{k1['K1总数']}；"
          f"温度中位数（跨模板）中位 {med(meds)} ℃")
    print(f"  n>=2 的 {len(iqrs)} 条：IQR(p75-p25) 中位 {med(iqrs)} ℃，"
          f"IQR<=30℃ 的 {sum(1 for x in iqrs if x <= 30)} 条；"
          f"max-min<=30℃ 的 {sum(1 for x in spans if x <= 30)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())

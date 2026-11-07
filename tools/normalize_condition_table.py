# -*- coding: utf-8 -*-
r"""规范化条件表：让它可以真正用来做条件门控。

现有条件表（conditions_by_reaction_type.json）的 4 个缺陷（实测）：
  1. 温度键是 median，而 resolve_conditions/activation_score 要的是 default -> 温度门控完全失效
  2. 溶剂名 43 个但大量同义重复（DMF / dimethylformamide / N,N-dimethylformamide；
     THF / tetrahydrofuran；DCM / CH2Cl2 / dichloromethane / methylene chloride）
     -> solvent_score() 做字符串匹配必然漏
  3. 催化剂 83 个不同字符串（Pd(OAc)2 / palladium acetate）
  4. reagents / bases 字段是空的（实际信息在 auxiliary_reagents 里）

本脚本输出 reports/conditions_normalized.json：
  - 溶剂名归一（同义词表 + 去重）
  - 温度补 default = median
  - 催化剂/辅助试剂归一 + 去重
用法: python normalize_condition_table.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
SRC = STAGE / "reports" / "conditions_by_reaction_type.json"
OUT = STAGE / "reports" / "conditions_normalized.json"

# ---------------- 溶剂同义词（只收实测出现的那些写法） ----------------
SOLVENT_ALIAS = {
    "dmf": "DMF", "dimethylformamide": "DMF", "n,n-dimethylformamide": "DMF",
    "thf": "THF", "tetrahydrofuran": "THF",
    "dcm": "DCM", "ch2cl2": "DCM", "dichloromethane": "DCM",
    "methylene chloride": "DCM", "methylene chlo": "DCM",
    "etoac": "EtOAc", "ethyl acetate": "EtOAc",
    "meoh": "MeOH", "methanol": "MeOH",
    "etoh": "EtOH", "ethanol": "EtOH",
    "h2o": "water", "water": "water",
    "dioxane": "1,4-dioxane", "1,4-dioxane": "1,4-dioxane",
    "dmso": "DMSO",
    "nmp": "NMP", "n-methylpyrrolidone": "NMP", "n-methylpyrrolidinone": "NMP",
    "dma": "DMA", "n,n-dimethylacetamide": "DMA",
    "dme": "DME",
    "et3n": "Et3N", "triethylamine": "Et3N",
    "dipea": "DIPEA", "n,n-diisopropylethylamine": "DIPEA",
    "ether": "Et2O", "ethyl ether": "Et2O",
    "toluene": "toluene", "acetonitrile": "MeCN", "pyridine": "pyridine",
    "acetic acid": "AcOH", "chloroform": "CHCl3", "benzene": "benzene",
    "acetone": "acetone", "1,2-dichloroethane": "DCE",
}
# ---------------- 催化剂同义词 ----------------
CAT_ALIAS = {
    "pd(oac)2": "Pd(OAc)2", "palladium acetate": "Pd(OAc)2",
    "pd2(dba)3": "Pd2(dba)3",
    "tris(dibenzylideneacetone)dipalladium": "Pd2(dba)3",
    "tris(dibenzylideneacetone)dipalladium(0)": "Pd2(dba)3",
    "copper (i) iodide": "CuI", "copper iodide": "CuI",
    "binap": "BINAP",
}


def norm(name, alias):
    if name is None:
        return None
    s = str(name).strip()
    key = s.lower()
    return alias.get(key, s)


def main():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    out = {}
    stat = Counter()
    for rxtype, v in d.items():
        # 溶剂：归一 + 去重 + 保持频次顺序
        raw_sol = [str(s) for s in (v.get("solvents") or [])]
        seen, sols = set(), []
        for s in raw_sol:
            n = norm(s, SOLVENT_ALIAS)
            if n and n not in seen:
                seen.add(n)
                sols.append(n)
        if len(raw_sol) != len(sols):
            stat["溶剂去重"] += len(raw_sol) - len(sols)

        # 催化剂 / 辅助试剂 / 碱：归一
        def dedup(vals, alias):
            seen2, res = set(), []
            for x in vals:
                n = norm(x, alias)
                if n and n not in seen2:
                    seen2.add(n)
                    res.append(n)
            return res

        cats = dedup(v.get("catalysts") or [], CAT_ALIAS)
        aux = dedup(v.get("auxiliary_reagents") or [], {})
        bases = dedup(v.get("bases") or [], {})
        reags = dedup(v.get("reagents") or [], {})

        # 温度：补 default = median（这是门控真正读的键）
        t = v.get("temp_C")
        if isinstance(t, dict) and t.get("median") is not None:
            t = dict(t)
            t["default"] = t["median"]
            stat["温度补 default"] += 1
        # 时间 / pH 同样补 default
        for key in ("time_min", "ph"):
            x = v.get(key)
            if isinstance(x, dict) and x.get("median") is not None:
                x = dict(x)
                x["default"] = x["median"]
                v[key] = x

        out[rxtype] = {
            "n_ord_matched": v.get("n_ord_matched", 0),
            "solvents": sols[:8],
            "catalysts": cats[:8],
            "auxiliary_reagents": aux[:10],
            "bases": bases[:8],
            "reagents": reags[:8],
            "temp_C": t,
            "time_min": v.get("time_min"),
            "ph": v.get("ph"),
            "template_categories": v.get("template_categories", []),
        }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 92)
    print("规范化完成")
    print("=" * 92)
    for k, v in stat.items():
        print(f"  {k}: {v}")
    print(f"\n  输出: {OUT.name}")
    print()
    print("  抽查 4 类（看溶剂是否归一、温度是否有 default）:")
    for k in ("amide_coupling", "mitsunobu", "suzuki", "esterification"):
        e = out[k]
        t = e["temp_C"]
        print(f"   {k:<18} 溶剂 {e['solvents'][:4]}")
        print(f"   {'':<18} 温度 min={t['min'] if t else None} "
              f"default={t.get('default') if t else None} max={t['max'] if t else None}")
        print(f"   {'':<18} 催化剂 {e['catalysts'][:3]}  辅助 {e['auxiliary_reagents'][:3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

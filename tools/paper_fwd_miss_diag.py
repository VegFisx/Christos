# -*- coding: utf-8 -*-
r"""L2 替代版（2026-10-14）：正向失败的归因诊断 —— 用既有全量评测数据回答
"哪些类失败、失败是'缺配料'还是'缺模板'"。

说明：50k 这个镜像文件的试剂列是空的（试剂/催化剂没随记录进来），所以做不了"含试剂评测"；
这里用更便宜、同样有信息量的口径：
  * 按记录反应物个数（1 / 2 / ≥3）看召回差异 —— 单反应物记录往往意味着"另一个偶联对象
    和催化剂没被记进反应物列"，这类失败是**数据缺配料**，不是引擎问题
  * 按类看失败构成；分别统计 n_products==0（连候选都没有=模板缺口）与 >0（有候选但没命中）
输出：reports/paper/results/forward_miss_diag.json
"""
from __future__ import annotations

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
RES = STAGE / "reports" / "paper" / "results"


def main() -> int:
    rows = [json.loads(l) for l in open(RES / "forward_per_reaction.jsonl",
                                        encoding="utf-8") if l.strip()]
    n_react = {}
    for l in open(STAGE / "reports" / "paper" / "data" / "uspto50k_canon.jsonl",
                  encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            n_react[r["i"]] = len(r["reactants"])
    ok = [r for r in rows if "error" not in r]
    for r in ok:
        r["n_react"] = n_react.get(r["i"], 0)

    def rate(rs):
        return (sum(1 for r in rs if r["hit"]) / max(1, len(rs)),
                sum(1 for r in rs if r["hit"]), len(rs))

    by_cnt = {}
    for cnt in (1, 2, 3, 4, 5):
        rs = [r for r in ok if r["n_react"] == cnt]
        if rs:
            rt, h, n = rate(rs)
            by_cnt[str(cnt)] = {"n": n, "hit": h, "rate": round(rt, 4)}
    fail = [r for r in ok if not r["hit"]]
    zero = [r for r in fail if r["n_products"] == 0]
    print("总 %d · 失败 %d（其中无任何候选 %d = %.0f%%；有候选没命中 %d）"
          % (len(ok), len(fail), len(zero), 100 * len(zero) / max(1, len(fail)),
             len(fail) - len(zero)))
    print("按记录反应物个数：")
    for k, v in by_cnt.items():
        print("   %s 个反应物：n=%5d · 召回 %.1f%%" % (k, v["n"], 100 * v["rate"]))
    by_cls = {}
    for c in sorted({str(r["class"]) for r in ok}, key=int):
        rs = [r for r in ok if str(r["class"]) == c]
        f = [r for r in rs if not r["hit"]]
        fz = [r for r in f if r["n_products"] == 0]
        rt, h, n = rate(rs)
        by_cls[c] = {"n": n, "rate": round(rt, 4), "n_fail": len(f),
                     "fail_zero_candidate": len(fz)}
        print("   class %-2s：n=%5d · 召回 %4.1f%% · 失败 %5d（无候选 %4d）"
              % (c, n, 100 * rt, len(f), len(fz)))
    out = {"n": len(ok), "n_fail": len(fail), "n_fail_zero_candidate": len(zero),
           "by_reactant_count": by_cnt, "by_class": by_cls,
           "note": "50k 镜像文件试剂列为空——单反应物记录多对应'另一反应物/催化剂未入列'，属数据缺口"}
    (RES / "forward_miss_diag.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("写出：forward_miss_diag.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

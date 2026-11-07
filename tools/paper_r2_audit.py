# -*- coding: utf-8 -*-
r"""论文配套（B7）：R2（"前体比目标还大"）的专项归因 —— 全部来自既有实测数据，不重跑。

输入：
  * reports/paper/results/usability_per_cut.jsonl（50k 抽样逐切断：t=模板序号, why, bl, t_hac）
  * reports/paper/data/lib_uspto50k_excl.jsonl（模板序号 -> smarts/freq）
  * reports/retro_template_audit.jsonl（56 目标侧的逐模板 R2 计数，做交叉）
  * reports/retro_template_blacklist.json（黑名单之内的 smarts）
输出：reports/paper/results/r2_audit.json + 屏幕摘要（含 top-10 模板的 smarts 供人眼判读）
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
LIB = STAGE / "reports" / "paper" / "data" / "lib_uspto50k_excl.jsonl"


def main() -> int:
    # 重建模板序号表（与 usability 脚本一致：跳过不可编译/多反应物）
    from rdkit import Chem
    from rdkit.Chem import rdChemReactions
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
    lib = []
    for line in open(LIB, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        try:
            rx = rdChemReactions.ReactionFromSmarts(r["template"])
        except Exception:
            rx = None
        if rx is None or rx.GetNumReactantTemplates() != 1:
            continue
        lib.append({"smarts": r["template"], "freq": int(r.get("freq") or 0)})

    rows = [json.loads(l) for l in open(RES / "usability_per_cut.jsonl", encoding="utf-8")
            if l.strip()]
    n = len(rows)
    r2 = [r for r in rows if str(r.get("why", "")).startswith("R2")]
    print("切断总数 %d · R2 %d（%.2f%%）" % (n, len(r2), 100.0 * len(r2) / max(1, n)))

    by_t = Counter(r["t"] for r in r2)
    ranked = by_t.most_common()
    tot = len(r2)
    cum = {}
    acc = 0
    for i, (t, c) in enumerate(ranked, 1):
        acc += c
        for k in (5, 10, 20, 50, 100):
            if i == k:
                cum["top%d_share" % k] = round(acc / max(1, tot), 4)
    # 黑名单影响
    bl = json.loads((STAGE / "reports" / "retro_template_blacklist.json")
                    .read_text(encoding="utf-8"))
    blset = {str(e.get("smarts")) for e in bl.get("entries", [])} | \
            {str(e.get("smarts")) for e in bl.get("noop_entries", [])}
    r2_bl = sum(1 for r in r2 if r.get("bl"))
    # 56 目标侧交叉
    old = {}
    old_f = STAGE / "reports" / "retro_template_audit.jsonl"
    if old_f.exists():
        for l in open(old_f, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                old[str(r.get("smarts"))] = r

    # 目标尺寸分桶（R2 触发与否与目标大小无关；看它主要出现在哪类目标上）
    buckets = Counter()
    for r in r2:
        h = int(r.get("t_hac") or 0)
        b = "<15" if h < 15 else ("15-25" if h < 25 else ("25-40" if h < 40 else ">=40"))
        buckets[b] += 1

    top = []
    for t, c in ranked[:12]:
        sm = lib[t]["smarts"] if 0 <= t < len(lib) else "?"
        top.append({"t": t, "n_r2": c, "freq": lib[t]["freq"] if 0 <= t < len(lib) else None,
                    "in_blacklist": sm in blset, "smarts": sm[:110],
                    "old56_r2": int(old.get(sm, {}).get("R2_前体大于目标", -1)),
                    "old56_try": int(old.get(sm, {}).get("n_try", -1))})
    out = {
        "n_cuts": n, "n_r2": tot, "r2_share": round(tot / max(1, n), 4),
        "distinct_templates_with_r2": len(by_t),
        "cumulative": cum,
        "r2_from_blacklisted": r2_bl,
        "r2_blacklisted_share": round(r2_bl / max(1, tot), 4),
        "t_hac_buckets": dict(buckets),
        "top_templates": top,
    }
    (RES / "r2_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print("R2 出自 %d 条不同模板 · 集中度：" % len(by_t),
          {k: "%.1f%%" % (100 * v) for k, v in cum.items()})
    print("R2 中来自黑名单模板：%d（%.1f%%）" % (r2_bl, 100.0 * r2_bl / max(1, tot)))
    print("按目标大小分桶：", dict(buckets))
    print("top-10 模板（人眼看化学）：")
    for x in top[:10]:
        print("   %6d 次 R2 · freq %-4s · 黑名单=%-5s · %s"
              % (x["n_r2"], x["freq"], x["in_blacklist"], x["smarts"][:84]))
    print("写出：r2_audit.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

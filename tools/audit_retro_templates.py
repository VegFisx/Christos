# -*- coding: utf-8 -*-
r"""D7（2026-10-13）：逆模板**逐条体检** —— 找出「只会产出残基路线/惰性小分子」的坏模板。

问题（`reports/B-搜索层过滤-报告.md`）：端到端形式成功率 82%，但**化学可用率只有 41%**，
最大假路线模式是 **R1 残基路线**（"把目标换个基团再变回来"）。报告说"要压到源头得改评分"，
但打分排序已经停工 —— 所以这里换一条不改评分的路：**在模板层做体检，把系统性只会产出
不可用切断的模板列出来**（白名单/黑名单），让搜索不再浪费在这些模板上。

口径（写死）：
  * 目标样本：默认取 `reports/query_inventory_paths.csv` 的 `product_smiles` 去重后前 N 个
    （这些是**我们自己的产物**，与"用引擎做逆合成"同一个分布）；也可 --targets-file。
  * 对每条逆模板、每个目标：套用一次 -> 得到前体集合 -> 用 `retro_search.step_usability` 判。
  * 逐模板累计：n_try / n_usable / n_R1 / n_R2 / n_R3 / n_R4 / n_parse_fail。
  * 输出 `reports/retro_template_audit.jsonl`（每模板一行）+ 一个汇总 json。

★ D7 增补（2026-10-14）：
  * 若 `reports/retro_template_blacklist.json` 存在，每条模板打 `blacklisted` 标记，
    汇总里直接给 **before（全部模板）/ after（砍掉黑名单）** 的可用率与假路线数 ——
    两边同源、同一次体检，不是估计。
  * 可用 `--out` / `--summary` 指定输出（冒烟测试别覆盖正式产物）。

用法: python tools/audit_retro_templates.py [N_TARGETS] [MAX_TEMPLATES] [--out X.jsonl] [--summary Y.json]
"""
from __future__ import annotations

import csv
import json
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
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                       # noqa: E402
import retro_search as rs                              # noqa: E402

RDLogger.DisableLog("rdApp.*")

CSV = STAGE / "reports" / "query_inventory_paths.csv"
OUT = STAGE / "reports" / "retro_template_audit.jsonl"
SUMMARY = STAGE / "reports" / "retro_template_audit_summary.json"


def load_targets(n: int, targets_file=None):
    """目标样本：缺省 = query_inventory_paths.csv 的 product_smiles 前 n 个；
    给了 targets_file 就按文件（每行一个 SMILES，tab 后可选名字，'#' 开头跳过）。"""
    if targets_file:
        path = Path(targets_file)
        if not path.exists():
            print("   [warn] --targets-file 不存在：%s" % path)
            return []
        seen, out = set(), []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                smi = line.split("\t")[0].strip()
                if not smi or smi in seen:
                    continue
                m = Chem.MolFromSmiles(smi)
                if m is None:
                    continue
                seen.add(smi)
                out.append(Chem.MolToSmiles(m))
                if len(out) >= n:
                    break
        return out
    if not CSV.exists():
        return []
    seen, out = set(), []
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            smi = str(row.get("product_smiles") or "").strip()
            if not smi or smi in seen:
                continue
            m = Chem.MolFromSmiles(smi)
            if m is None:
                continue
            seen.add(smi)
            out.append(Chem.MolToSmiles(m))
            if len(out) >= n:
                break
    return out


def main() -> int:
    # 位置参数照旧（N_TARGETS / MAX_TEMPLATES），另加 --out / --summary
    argv = list(sys.argv[1:])
    pos, out_path, summary_path = [], OUT, SUMMARY
    targets_file = None
    i = 0
    while i < len(argv):
        if argv[i] == "--out" and i + 1 < len(argv):
            out_path = Path(argv[i + 1])
            i += 2
        elif argv[i] == "--summary" and i + 1 < len(argv):
            summary_path = Path(argv[i + 1])
            i += 2
        elif argv[i] == "--targets-file" and i + 1 < len(argv):
            targets_file = argv[i + 1]
            i += 2
        else:
            pos.append(argv[i])
            i += 1
    n_targets = int(pos[0]) if len(pos) >= 1 else 120
    max_tmpl = int(pos[1]) if len(pos) >= 2 else 0
    t0 = time.time()
    targets = load_targets(n_targets, targets_file=targets_file)
    print("目标 %d 个（来自 %s）"
          % (len(targets), Path(targets_file).name if targets_file else CSV.name), flush=True)
    tmpl = rs.load_rdchiral_templates()
    lib_smarts = {t.smarts for t in tmpl}          # 全量（截断前），供黑名单核对
    if max_tmpl:
        tmpl = tmpl[:max_tmpl]
    print("逆模板 %d 条" % len(tmpl), flush=True)
    # ★ D7：黑名单（默认关的过滤器）——体检里只用来**标注**每条模板进 before/after 哪一侧
    bl = rs.load_retro_blacklist(verbose=True)
    if bl:
        n_hit = sum(1 for t in tmpl if t.smarts in bl)
        n_missing = sum(1 for s in bl if s not in lib_smarts)
        print("黑名单: %d 条（本次体检范围内命中 %d 条%s）"
              % (len(bl), n_hit, ("；模板库里找不到 %d 条" % n_missing) if n_missing else ""),
              flush=True)

    stats = []
    n_compile_fail = 0
    for i, t in enumerate(tmpl, 1):
        c = Counter()
        smarts = getattr(t, "smarts", "") or getattr(t, "template", "")
        try:
            rx = rs.Chem.rdChemReactions.ReactionFromSmarts(smarts) if hasattr(rs, "Chem") else None
        except Exception:
            rx = None
        if rx is None:
            try:
                from rdkit.Chem import rdChemReactions
                rx = rdChemReactions.ReactionFromSmarts(smarts)
            except Exception:
                rx = None
        if rx is None:
            n_compile_fail += 1
            continue
        for tgt in targets:
            m = Chem.MolFromSmiles(tgt)
            if m is None:
                continue
            try:
                outs = rx.RunReactants((m,))
            except Exception:
                c["run_fail"] += 1
                continue
            for tup in outs:
                prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
                prec = tuple(p for p in prec if p)
                if not prec:
                    continue
                ok, why = rs.step_usability(tgt, prec)
                c["n_try"] += 1
                if ok:
                    c["n_usable"] += 1
                else:
                    c[why] += 1
        if c["n_try"]:
            stats.append({"idx": i, "name": getattr(t, "name", ""), "smarts": smarts,
                          "blacklisted": smarts in bl,
                          **{k: int(v) for k, v in c.items()}})
        if i % 400 == 0:
            print("  ... %d/%d 模板，用时 %.0fs" % (i, len(tmpl), time.time() - t0), flush=True)

    with open(out_path, "w", encoding="utf-8") as f:
        for s in stats:
            f.write(json.dumps(s, ensure_ascii=False) + chr(10))

    def _agg(rows_):
        tot_ = Counter()
        for s_ in rows_:
            for k, v in s_.items():
                if k.startswith("n_") or k.startswith("R"):
                    tot_[k] += v
        t_ = {k: int(v) for k, v in tot_.items()}
        t_["n_unusable"] = t_.get("n_try", 0) - t_.get("n_usable", 0)
        t_["usable_rate"] = round(t_.get("n_usable", 0) / max(1, t_.get("n_try", 0)), 4)
        return t_

    # ★ D7：before = 全部模板；after = 砍掉黑名单。同一次体检、同一批目标 -> 可比。
    before = _agg(stats)
    after = _agg([s for s in stats if not s.get("blacklisted")])
    bad = [s for s in stats if s.get("n_try", 0) >= 5 and s.get("n_usable", 0) == 0]
    n_bad_in_bl = sum(1 for s in bad if s.get("blacklisted"))
    summ = {"n_targets": len(targets), "n_templates": len(tmpl),
            # ★ D7：MCS 是限时搜索 —— 把超时数报出来（否则"可用率"会被机器负载悄悄污染）
            "usability_stats": dict(getattr(rs, "USTAT", {})),
            "n_compile_fail": n_compile_fail, "n_templates_with_hits": len(stats),
            "totals": before,
            "usable_rate": before["usable_rate"],
            "n_never_usable_templates": len(bad),
            "example_bad": [{"idx": s["idx"], "n_try": s["n_try"]} for s in bad[:10]],
            "before_after": {
                "note": "before=全部模板；after=砍掉 reports/retro_template_blacklist.json；"
                        "同一次体检、同源聚合，不是估计。",
                "n_blacklist_loaded": len(bl),
                "n_blacklisted_with_hits": sum(1 for s in stats if s.get("blacklisted")),
                "before": before, "after": after,
                "delta": {"n_try": before["n_try"] - after["n_try"],
                          "n_unusable": before["n_unusable"] - after["n_unusable"],
                          "n_usable": before["n_usable"] - after["n_usable"]},
            },
            "never_usable_now": {"n": len(bad), "n_in_blacklist": n_bad_in_bl,
                                 "n_new_vs_blacklist": len(bad) - n_bad_in_bl},
            "seconds": round(time.time() - t0, 1)}
    summary_path.write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1), flush=True)
    d = summ["before_after"]["delta"]
    print("★ D7 前后对比：before try %d · 可用 %d (%.2f%%)  ||  after try %d · 可用 %d (%.2f%%)"
          % (before["n_try"], before["n_usable"], before["usable_rate"] * 100,
             after["n_try"], after["n_usable"], after["usable_rate"] * 100), flush=True)
    print("   砍掉：try -%d · 假路线 -%d · never-usable(本轮重测) %d 条，其中 %d 条在冻结黑名单里"
          % (d["n_try"], d["n_unusable"], len(bad), n_bad_in_bl), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
r"""论文基准（第三块）：USPTO-50k 上「正向单步预测」的召回（第一个数字）。

口径（写死）：
  * 目标：reports/paper/data/uspto50k_canon.jsonl（记录反应物 -> 记录产物）
  * 分层抽样（按反应类别，每类 ≤ N_PER_CLASS，种子 20261014）
  * 输入 = 该反应的**记录反应物**（1~3 个，去映射号规范化）当底物；正向引擎跑 **1 轮**（round_no=1）
  * 命中 = 记录产物出现在 1 轮候选集合里（集合成员，**不排序**）
  * 同时记录候选规模（过生成指标：均值/中位/0 产物比例）；泄漏标记 in_sources 单列
  * 条件档案固定 "煎煮"（与其余 demo 一致；条件只影响标注，不影响本轮生成口径——如实声明）
输出：reports/paper/results/forward_50k.json + forward_per_reaction.jsonl
用法: python tools/paper_bench_50k_forward.py [N_PER_CLASS=200] [workers=6]
"""
from __future__ import annotations

import json
import multiprocessing as mp
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os as _os_root          # ★ 复现演练（B10）：仓库根可被环境变量覆盖，默认不变
STAGE = Path(_os_root.environ.get("CHEMCREACT_ROOT")
             or r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "rules", STAGE / "libs", STAGE / "tools",
           STAGE / "conditions"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

TARGETS = STAGE / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
OUT_DIR = Path(_os_root.environ.get("CHEMCREACT_BENCH_OUT")
               or (STAGE / "reports" / "paper" / "results"))
SEED = 20261014

_G = {}


def _init(src_products):
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    from engine import Compound
    from smartreact_engine import SmartReactEngine
    import templates as T
    # ★ 消融用：模板集可用环境变量切换（默认路径=现役；不改生产默认）
    import os as _os
    _kw = {}
    if _os.environ.get("CHEMCREACT_BENCH_EXTRA_TPL"):
        _kw["extra_templates_path"] = _os.environ["CHEMCREACT_BENCH_EXTRA_TPL"]
    if _os.environ.get("CHEMCREACT_BENCH_EXTRA_LIMIT"):
        _kw["extra_template_limit"] = int(_os.environ["CHEMCREACT_BENCH_EXTRA_LIMIT"])
    if _os.environ.get("CHEMCREACT_BENCH_EXTRA_MIN_SUPPORT"):
        _kw["extra_template_min_support"] = int(_os.environ["CHEMCREACT_BENCH_EXTRA_MIN_SUPPORT"])
    if _os.environ.get("CHEMCREACT_BENCH_MONO_TPL"):
        _kw["mono_templates_path"] = _os.environ["CHEMCREACT_BENCH_MONO_TPL"]
    if _os.environ.get("CHEMCREACT_BENCH_MONO_LIMIT"):
        _kw["mono_template_limit"] = int(_os.environ["CHEMCREACT_BENCH_MONO_LIMIT"])
    if _os.environ.get("CHEMCREACT_BENCH_MONO_CO_REAGENT"):
        _kw["mono_include_co_reagent"] = True
    if _os.environ.get("CHEMCREACT_BENCH_MAXPROD"):
        _kw["max_products_per_pair"] = int(_os.environ["CHEMCREACT_BENCH_MAXPROD"])
    if _os.environ.get("CHEMCREACT_BENCH_PREFILTER"):
        _kw["prefilter"] = True
    if _os.environ.get("CHEMCREACT_BENCH_NO_PREFILTER"):
        _kw["prefilter"] = False
    # ★ 2026-10-30：当前引擎默认档已是「选定配置」（cap 32、预筛开、默认模板池）。
    #   论文里那个 55.43% 的基线是【旧默认】：每个底物对 8 个产物、无 extra/mono 模板池、
    #   预筛关。要复现它必须显式降档，否则拿到的是选定配置。
    if _os.environ.get("CHEMCREACT_BENCH_LEGACY"):
        _kw.update(max_products_per_pair=8, prefilter=False)
    if _os.environ.get("CHEMCREACT_BENCH_NO_EXTRA"):
        _kw.update(use_extra_templates=False)
    if _os.environ.get("CHEMCREACT_BENCH_NO_MONO"):
        _kw.update(use_mono_templates=False)
    _G["eng"] = SmartReactEngine(**_kw)
    _G["cond"] = T.get_template("煎煮")
    _G["Compound"] = Compound
    _G["src"] = set(src_products)
    _G["canon"] = lambda smi: (lambda m: Chem.MolToSmiles(m) if m else None)(
        Chem.MolFromSmiles(smi))


def _work(batch):
    out = []
    for rec in batch:
        comps = []
        ok = True
        for j, smi in enumerate(rec["reactants"]):
            c = _G["Compound"](smiles=smi, name="R%d" % j, herb="(bench)")
            comps.append(c)
        try:
            prods = _G["eng"].step(comps, _G["cond"], round_no=1)
        except Exception as ex:
            out.append({"i": rec["i"], "error": type(ex).__name__})
            continue
        ss = set()
        for p in prods:
            c = getattr(p, "smiles", None)
            if c:
                ss.add(c)
        hit = rec["product"] in ss
        out.append({"i": rec["i"], "class": rec["class"], "n_products": len(ss),
                    "hit": bool(hit), "in_sources": rec["product"] in _G["src"]})
    return out


def main() -> int:
    t0 = time.time()
    n_per = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 泄漏标记用：原抽取记录里的产物字面
    src_products = set()
    for sp in sorted((STAGE / "reports").glob("_shard_[0-9].jsonl")):
        for line in open(sp, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            rx = json.loads(line).get("rx") or ""
            if ">>" in rx:
                _, _, rsd = rx.partition(">>")
                for frag in rsd.split("."):
                    s = re.sub(r":\d+", "", frag).strip()
                    if s:
                        from rdkit import Chem
                        m = Chem.MolFromSmiles(s)
                        if m is not None:
                            src_products.add(Chem.MolToSmiles(m))

    by_cls = {}
    for line in open(TARGETS, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        by_cls.setdefault(str(r["class"]), []).append(r)
    rng = random.Random(SEED)
    sample = []
    for c, lst in sorted(by_cls.items()):
        rng.shuffle(lst)
        sample.extend(lst[:min(n_per, len(lst))])
    sample.sort(key=lambda r: r["i"])
    # 分片：CHEMCREACT_BENCH_SHARD="i/n"（0-based），用于长跑时分段重置内存。
    _shard = (__import__("os").environ.get("CHEMCREACT_BENCH_SHARD") or "").strip()
    if _shard:
        _si, _sn = (int(x) for x in _shard.split("/"))
        sample = [r for k, r in enumerate(sample) if k % _sn == _si]
        print("分片 %s：本片 %d 条" % (_shard, len(sample)), flush=True)
    print("分层抽样 %d 条（每类≤%d，种子 %d）· %d 进程" % (len(sample), n_per, SEED, workers),
          flush=True)

    batch_sz = 60
    batches = [sample[i:i + batch_sz] for i in range(0, len(sample), batch_sz)]
    rows = []
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers, initializer=_init,
                  initargs=(list(src_products),)) as pool:
        for k, part in enumerate(pool.imap_unordered(_work, batches), 1):
            rows.extend(part)
            if k % 5 == 0:
                print("   ... %d/%d 批（%.0fs）" % (k, len(batches), time.time() - t0),
                      flush=True)
    rows.sort(key=lambda r: r.get("i", -1))
    _TAG = __import__("os").environ.get("CHEMCREACT_BENCH_TAG", "v0")
    with open(OUT_DIR / ("forward_per_reaction__%s.jsonl" % _TAG), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ok = [r for r in rows if "error" not in r]
    n = len(ok)
    hits = sum(1 for r in ok if r["hit"])
    nprod = [r["n_products"] for r in ok]
    by_cls_hit = {}
    for r in ok:
        d = by_cls_hit.setdefault(str(r["class"]), {"n": 0, "hit": 0})
        d["n"] += 1
        d["hit"] += 1 if r["hit"] else 0
    excl = [r for r in ok if r["in_sources"]]
    summary = {
        "n_reactions": n, "n_per_class_cap": n_per, "seed": SEED, "workers": workers,
        "cond": "煎煮", "rounds": 1,
        "recall_1step": round(hits / max(1, n), 4),
        "n_errors": len(rows) - n,
        "candidate_stats": {
            "mean": round(sum(nprod) / max(1, n), 1),
            "median": sorted(nprod)[len(nprod) // 2] if nprod else 0,
            "p90": sorted(nprod)[int(0.9 * len(nprod))] if nprod else 0,
            "zero_share": round(sum(1 for x in nprod if x == 0) / max(1, n), 4)},
        "by_class_recall": {c: {"n": d["n"], "rate": round(d["hit"] / max(1, d["n"]), 4)}
                            for c, d in sorted(by_cls_hit.items())},
        "in_sources_subset": {"n": len(excl),
                              "recall": round(sum(1 for r in excl if r["hit"]) /
                                              max(1, len(excl)), 4)},
        "seconds": round(time.time() - t0, 1),
    }
    (OUT_DIR / ("forward_50k__%s.json" % _TAG)).write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("=" * 74)
    print("USPTO-50k 正向单步召回（1 轮，不排序）：%d/%d = %.2f%%"
          % (hits, n, 100.0 * hits / max(1, n)))
    print("  候选规模：均值 %.1f / 中位 %d / p90 %d / 空集 %.2f%%"
          % (summary["candidate_stats"]["mean"], summary["candidate_stats"]["median"],
             summary["candidate_stats"]["p90"],
             100 * summary["candidate_stats"]["zero_share"]))
    for c, d in sorted(by_cls_hit.items()):
        print("   class %-2s: %5.1f%%（n=%d）" % (c, 100.0 * d["hit"] / max(1, d["n"]),
                                                  d["n"]))
    print("  耗时 %.0fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

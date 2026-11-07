# -*- coding: utf-8 -*-
r"""论文基准（第二块·第一遍）：USPTO-50k 全量「覆盖率 / 频次序 top-k」评估。

口径（写死）：
  * 目标：reports/paper/data/uspto50k_canon.jsonl（50,016 条，product/reactants 已标准化）
  * 库  ：reports/paper/data/lib_uspto50k_excl.jsonl（3,065 条；= 剔除"产物命中 50k"的
          一切抽取记录后重聚类 —— 复现校验通过：不剔除时与现库 3,228 条完全相同）
  * 每个产物：套用全部模板 -> 收集切断（前体集合，canonical）
      - any-hit：记录的反应物集合 == 某个切断的前体集合（严格集合相等）
      - top-k（1/3/5/10/50）：切断按【模板频次 freq 降序, smarts 字典序】排序后取正确切断最好名次
        （频次排序不是"打分"，是一个确定性、可复现的次序；论文里如实声明）
  * 黑名单 54 条：在库内的哪些 + 对全 50k 的命中与**就地可用性**（与生产判据同一函数）
  * 泄漏标记：产物若属于"原抽取记录里出现过"的 2,480 个 -> 单列统计
输出：reports/paper/results/coverage_per_product.jsonl + coverage_summary.json
用法: python tools/paper_bench_50k_coverage.py [workers=6]
"""
from __future__ import annotations

import json
import multiprocessing as mp
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
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

LIB = Path(_os_root.environ.get("CHEMCREACT_LIB")
           or (STAGE / "reports" / "paper" / "data" / "lib_uspto50k_excl.jsonl"))
TARGETS = STAGE / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
BLACKLIST = STAGE / "reports" / "retro_template_blacklist.json"
SHARDS_GLOB = "_shard_[0-9].jsonl"
OUT_DIR = Path(_os_root.environ.get("CHEMCREACT_BENCH_OUT")
               or (STAGE / "reports" / "paper" / "results"))

_G = {}


def _canon(frag):
    s = re.sub(r":\d+", "", frag or "").strip()
    if not s:
        return None
    from rdkit import Chem
    m = Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(m) if m is not None else None


def _avail_gb():
    """系统可用物理内存（GB）；读不到返回 None（非 Windows 等）。"""
    try:
        import ctypes
        from ctypes import wintypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        ms = _MS()
        ms.dwLength = ctypes.sizeof(_MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
            return None
        return ms.ullAvailPhys / 2 ** 30
    except Exception:
        return None


def _init(lib_path, bl_path, src_products, shards_dir):
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdChemReactions
    import retro_search as rs
    RDLogger.DisableLog("rdApp.*")
    lib = []
    bad = 0
    for line in open(lib_path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        sm = str(r["template"])
        try:
            rx = rdChemReactions.ReactionFromSmarts(sm)
        except Exception:
            rx = None
        if rx is None or rx.GetNumReactantTemplates() != 1:
            bad += 1
            continue
        # ★ 内存修复（2026-10-15 死机事故）：只存 (smarts, freq)，编译放到 _work 里**分块流式**做，
        #   每个 worker 的峰值内存从 ~2.6 GB 降到 ~0.6 GB（rx 出作用域即回收，不囤积）。
        lib.append((sm, int(r.get("freq") or 0)))
    _G["lib_raw"] = lib
    _G["lib_bad"] = bad
    _G["rs"] = rs
    bl = json.loads(Path(bl_path).read_text(encoding="utf-8"))
    _G["bl_smarts"] = {str(e.get("smarts")) for e in bl.get("entries", [])} | \
                      {str(e.get("smarts")) for e in bl.get("noop_entries", [])} | \
                      {str(e.get("smarts")) for e in bl.get("r2_family_entries", [])}
    _G["bl_kind"] = {}
    for e in bl.get("entries", []):
        _G["bl_kind"][str(e.get("smarts"))] = "never_usable"
    for e in bl.get("noop_entries", []):
        _G["bl_kind"][str(e.get("smarts"))] = "noop"
    for e in bl.get("r2_family_entries", []):
        _G["bl_kind"][str(e.get("smarts"))] = "r2_family"
    _G["src"] = set(src_products)
    # 原抽取记录里的产物字面（给泄漏标记用）
    return


def _work(batch):
    from rdkit import Chem
    from rdkit.Chem import rdChemReactions
    rs = _G["rs"]
    lib_raw = _G["lib_raw"]
    CHUNK = 8000
    mols = [Chem.MolFromSmiles(rec["product"]) for rec in batch]
    cuts_per = [[] for _ in batch]
    # ★ 内存修复（2026-10-15 死机事故的根因修复）：模板按 8,000 条**分块流式编译**，
    #   跑完这批目标即释放、再进下一块 —— 每 worker 峰值内存从 ~2.6 GB 降到 ~0.6 GB。
    for ci in range(0, len(lib_raw), CHUNK):
        compiled = []
        for sm, fr in lib_raw[ci:ci + CHUNK]:
            try:
                rx = rdChemReactions.ReactionFromSmarts(sm)
            except Exception:
                continue
            if rx is not None and rx.GetNumReactantTemplates() == 1:
                compiled.append((fr, sm, rx))
        for k, rec in enumerate(batch):
            m = mols[k]
            if m is None:
                continue
            for fr, sm, rx in compiled:
                try:
                    outs = rx.RunReactants((m,))
                except Exception:
                    continue
                for tup in outs:
                    prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
                    prec = tuple(p for p in prec if p)
                    if prec:
                        cuts_per[k].append((fr, sm, prec))
        compiled = None
    out, bl_stat = [], {}
    for k, rec in enumerate(batch):
        i = rec["i"]
        smi = rec["product"]
        if mols[k] is None:
            out.append({"i": i, "error": "parse"})
            continue
        cuts = cuts_per[k]
        seen_bl = set()
        for _f, sm, prec in cuts:
            if sm in _G["bl_smarts"]:
                st = bl_stat.setdefault(sm, {"kind": _G["bl_kind"].get(sm, "?"),
                                             "n_prod": 0, "n_cut": 0, "n_usable": 0,
                                             "verdicts": Counter()})
                st["n_cut"] += 1
                ok, why = rs.step_usability(smi, prec)
                if ok:
                    st["n_usable"] += 1
                else:
                    st["verdicts"][why] += 1
                seen_bl.add(sm)
        for sm in seen_bl:
            bl_stat.setdefault(sm, {"kind": _G["bl_kind"].get(sm, "?"),
                                    "n_prod": 0, "n_cut": 0, "n_usable": 0,
                                    "verdicts": Counter()})["n_prod"] += 1
        want = frozenset(rec["reactants"])
        cuts.sort(key=lambda x: (-x[0], x[1]))
        best_rank, n_match = None, 0
        for rank, (_f, _s, prec) in enumerate(cuts, 1):
            if frozenset(prec) == want:
                n_match += 1
                if best_rank is None:
                    best_rank = rank
        out.append({"i": i, "class": rec.get("class"), "n_cuts": len(cuts),
                    "any_hit": n_match > 0, "best_rank": best_rank, "n_match": n_match,
                    "in_sources": smi in _G["src"]})
    return out, bl_stat, dict(rs.USTAT)


def main() -> int:
    t0 = time.time()
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    lib_path = Path(sys.argv[2]) if len(sys.argv) > 2 else LIB
    # ★ v2 大库评测：用固定步长抽样目标（老库/新库同一子集才可比）
    stride = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    # ★ 内存护栏（2026-10-15 死机事故后加）：按"可用内存 - 2 GB 余量 ÷ 每 worker 0.8 GB"自动限并发
    avail = _avail_gb()
    if avail is None:
        print("   [guard] 读不到系统内存信息：按请求并发跑（请自行观察内存）", flush=True)
    else:
        est = 0.8
        safe = max(1, int((avail - 2.0) / est))
        if workers > safe:
            print("   [guard] 可用内存 %.1f GB -> 并发 %d 自动降为 %d（每 worker 预留 ~%.1f GB）"
                  % (avail, workers, safe, est), flush=True)
            workers = safe
        else:
            print("   [guard] 可用内存 %.1f GB · 请求并发 %d ≤ 安全上限 %d，按请求跑"
                  % (avail, workers, safe), flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = []
    for line in open(TARGETS, encoding="utf-8"):
        line = line.strip()
        if line:
            targets.append(json.loads(line))
    if stride > 1:
        targets = targets[::stride]
    print("目标 %d 条 · 库 %s" % (len(targets), lib_path.name), flush=True)
    if stride > 1:
        print("（步长 %d 抽样：全量 50,016 -> %d 条；老库/新库同子集）" % (stride, len(targets)),
              flush=True)

    lib_smarts = [json.loads(l)["template"] for l in open(lib_path, encoding="utf-8") if l.strip()]
    bl_all = {str(e.get("smarts")) for e in
              json.loads(BLACKLIST.read_text(encoding="utf-8")).get("entries", [])}
    bl_extra = {str(e.get("smarts")) for e in
                json.loads(BLACKLIST.read_text(encoding="utf-8")).get("noop_entries", [])}
    bl_r2 = {str(e.get("smarts")) for e in
             json.loads(BLACKLIST.read_text(encoding="utf-8")).get("r2_family_entries", [])}
    bl_n = len(bl_all | bl_extra | bl_r2)
    bl_in_lib = (bl_all | bl_extra | bl_r2) & set(lib_smarts)
    print("库内模板 %d 条 · 黑名单 %d 条中在库内 %d 条" % (len(lib_smarts), bl_n,
                                                      len(bl_in_lib)), flush=True)

    # 原抽取记录里的产物集合（泄漏标记用，与论文口径一致：分片 rx 的产物侧，去映射号）
    src_products = set()
    for sp in sorted((STAGE / "reports").glob(SHARDS_GLOB)):
        for line in open(sp, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            rx = json.loads(line).get("rx") or ""
            if ">>" in rx:
                _, _, rsd = rx.partition(">>")
                for frag in rsd.split("."):
                    c = _canon(frag)
                    if c:
                        src_products.add(c)
    print("原抽取产物字面 %d 个（泄漏标记用）· 启动 %d 进程" % (len(src_products), workers),
          flush=True)

    batch_sz = 250
    batches = [targets[i:i + batch_sz] for i in range(0, len(targets), batch_sz)]
    rows = []
    bl_total = {}
    ustat = Counter()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers, initializer=_init,
                  initargs=(str(lib_path), str(BLACKLIST), list(src_products),
                            str(STAGE / "reports"))) as pool:
        for k, (part, blp, us) in enumerate(pool.imap_unordered(_work, batches), 1):
            rows.extend(part)
            for sm, st in blp.items():
                t = bl_total.setdefault(sm, {"kind": st["kind"], "n_prod": 0, "n_cut": 0,
                                             "n_usable": 0, "verdicts": Counter()})
                t["n_prod"] += st["n_prod"]
                t["n_cut"] += st["n_cut"]
                t["n_usable"] += st["n_usable"]
                t["verdicts"].update(st["verdicts"])
            ustat.update(us)
            if k % 20 == 0:
                print("   ... %d/%d 批（%.0fs）" % (k, len(batches), time.time() - t0), flush=True)

    rows.sort(key=lambda r: r.get("i", -1))
    # ★ 输出文件名带"库名+步长"（2026-10-15：小验证跑曾把 50k 全量结果覆盖——不再用固定名）
    tag = "%s_s%d" % (lib_path.stem, stride)
    with open(OUT_DIR / ("coverage_per_product__%s.jsonl" % tag), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ok = [r for r in rows if "error" not in r]
    n = len(ok)
    any_hit = sum(1 for r in ok if r["any_hit"])
    ks = [1, 3, 5, 10, 50]
    topk = {k: sum(1 for r in ok if r["best_rank"] and r["best_rank"] <= k) for k in ks}
    by_cls = {}
    for r in ok:
        c = str(r.get("class"))
        d = by_cls.setdefault(c, {"n": 0, "any": 0})
        d["n"] += 1
        d["any"] += 1 if r["any_hit"] else 0
    excl = [r for r in ok if r["in_sources"]]
    summary = {
        "n_targets": n, "lib": lib_path.name, "workers": workers,
        "lib_templates": len(lib_smarts), "blacklist_in_lib": len(bl_in_lib),
        "blacklist_missing_n": len((bl_all | bl_extra) - bl_in_lib),
        "cut_stats": {"mean_cuts": sum(r["n_cuts"] for r in ok) / max(1, n),
                      "total_cuts": sum(r["n_cuts"] for r in ok)},
        "any_hit": any_hit, "any_hit_rate": round(any_hit / max(1, n), 4),
        "topk": {("top%d" % k): {"n": v, "rate": round(v / max(1, n), 4)} for k, v in topk.items()},
        "by_class_any_hit": {c: {"n": d["n"], "rate": round(d["any"] / max(1, d["n"]), 4)}
                             for c, d in sorted(by_cls.items())},
        "in_sources_subset": {"n": len(excl),
                              "any_hit_rate": round(sum(1 for r in excl if r["any_hit"]) /
                                                    max(1, len(excl)), 4)},
        "ustat": dict(ustat),
        "blacklist_on_50k": {sm: {"kind": st["kind"], "n_prod": st["n_prod"], "n_cut": st["n_cut"],
                                  "n_usable": st["n_usable"],
                                  "verdicts": dict(st["verdicts"])}
                             for sm, st in bl_total.items()},
        "seconds": round(time.time() - t0, 1),
    }
    (OUT_DIR / ("coverage_summary__%s.json" % tag)).write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=" * 74)
    print("USPTO-50k 覆盖率（库 %d 条模板 · 黑名单 %d 条中在库内 %d）"
          % (len(lib_smarts), bl_n, len(bl_in_lib)))
    print("  any-hit：%d/%d = %.2f%%" % (any_hit, n, 100.0 * any_hit / max(1, n)))
    for k in ks:
        print("  top%-3d ：%d = %.2f%%" % (k, topk[k], 100.0 * topk[k] / max(1, n)))
    print("  平均切断/产物 %.1f · 总切断 %d" % (summary['cut_stats']['mean_cuts'],
                                            summary['cut_stats']['total_cuts']))
    print("  黑名单扫描：命中的条目 %d 条" % len(bl_total))
    nu = sum(st["n_usable"] for st in bl_total.values())
    nc = sum(st["n_cut"] for st in bl_total.values())
    print("  黑名单切断 %d · 其中可用 %d（%.2f%%）" % (nc, nu, 100.0 * nu / max(1, nc)))
    print("  耗时 %.0fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

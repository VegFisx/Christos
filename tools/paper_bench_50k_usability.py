# -*- coding: utf-8 -*-
r"""论文基准（第二块·第二遍）：USPTO-50k 上「化学可用性构成」的抽样评估 + 逐切断记录。

口径：
  * 目标抽样：按反应类别分层，每类 min(类别总数, 300)，固定种子 20261014 -> ~2,930 条
  * 库：lib_uspto50k_excl.jsonl（3,065 条干净库）；判据 = 与生产同一函数 step_usability（无 avail 例外）
  * 逐切断记录：{i, t(模板序号), ok, why, ratio(元素覆盖比), t_hac, p_hac}
      - ratio = Σ_元素 min(目标,前体)/目标重原子（取前体里最大的那个）——给"确定性替代判据"分析用
  * 供专家标注的候选：抽若干条切断存全文（target/precursors/verdict）
输出：reports/paper/results/usability_per_cut.jsonl · usability_summary.json · annotation_candidates.jsonl
用法: python tools/paper_bench_50k_usability.py [workers=4]
"""
from __future__ import annotations

import json
import multiprocessing as mp
import random
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
OUT_DIR = Path(_os_root.environ.get("CHEMCREACT_BENCH_OUT")
               or (STAGE / "reports" / "paper" / "results"))
SEED = 20261014
PER_CLASS = 300

_G = {}


def _avail_gb():
    """系统可用物理内存（GB）；读不到返回 None。"""
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


def _init(lib_path):
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdChemReactions
    import retro_search as rs
    RDLogger.DisableLog("rdApp.*")
    lib = []
    for line in open(lib_path, encoding="utf-8"):
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
        lib.append(str(r["template"]))
    # ★ 内存修复（2026-10-15 死机事故后）：只存 SMARTS，编译放到 _work 里**分块流式**做
    _G["lib_raw"] = lib
    _G["rs"] = rs
    bl = json.loads(Path(BLACKLIST).read_text(encoding="utf-8"))
    _G["bl"] = {str(e.get("smarts")) for e in bl.get("entries", [])} | \
               {str(e.get("smarts")) for e in bl.get("noop_entries", [])} | \
               {str(e.get("smarts")) for e in bl.get("r2_family_entries", [])}


def _work(batch):
    from rdkit import Chem
    from rdkit.Chem import rdChemReactions
    rs = _G["rs"]
    lib = _G["lib_raw"]
    CHUNK = 8000
    blset = _G["bl"]
    mols = [Chem.MolFromSmiles(rec["product"]) for rec in batch]
    rows = [[] for _ in batch]
    detail = []
    for ci in range(0, len(lib), CHUNK):
        compiled = []
        for off, sm in enumerate(lib[ci:ci + CHUNK]):
            try:
                rx = rdChemReactions.ReactionFromSmarts(sm)
            except Exception:
                continue
            if rx is not None and rx.GetNumReactantTemplates() == 1:
                compiled.append((ci + off, sm, rx))
        for k, rec in enumerate(batch):
            m = mols[k]
            if m is None:
                continue
            i = rec["i"]
            smi = rec["product"]
            t_hac = m.GetNumHeavyAtoms()
            for ti, sm, rx in compiled:
                try:
                    outs = rx.RunReactants((m,))
                except Exception:
                    continue
                for tup in outs:
                    prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
                    prec = tuple(p for p in prec if p)
                    if not prec:
                        continue
                    ratio = 0.0
                    for p in prec:
                        ub = rs._common_atom_upper_bound(rs._elem_counts(smi),
                                                         rs._elem_counts(p))
                        ratio = max(ratio, ub / max(1, t_hac))
                    ok, why = rs.step_usability(smi, prec)
                    rows[k].append({"i": i, "t": ti, "ok": bool(ok),
                                    "why": "" if ok else why, "ratio": round(ratio, 3),
                                    "t_hac": t_hac, "bl": 1 if sm in blset else 0})
                    if (i + ti) % 23 == 0 and len(detail) < 8:
                        detail.append({"i": i, "class": rec.get("class"), "target": smi,
                                       "precursors": list(prec),
                                       "usable": bool(ok), "reason": "ok" if ok else why})
        compiled = None
    out = [r for sub in rows for r in sub]
    return out, detail, dict(rs.USTAT)


def main() -> int:
    t0 = time.time()
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    lib_path = Path(sys.argv[2]) if len(sys.argv) > 2 else LIB
    per_class = int(sys.argv[3]) if len(sys.argv) > 3 else PER_CLASS
    # ★ 内存护栏（2026-10-15 死机事故后）：按"可用内存 - 1.5 GB 余量 ÷ 0.4 GB/worker"自动限并发
    avail = _avail_gb()
    if avail is not None:
        est = 0.4
        safe = max(1, int((avail - 1.5) / est))
        if workers > safe:
            print("   [guard] 可用内存 %.1f GB -> 并发 %d 自动降为 %d（每 worker 预留 ~%.1f GB）"
                  % (avail, workers, safe, est), flush=True)
            workers = safe
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    by_cls = {}
    targets = []
    for line in open(TARGETS, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        targets.append(r)
        by_cls.setdefault(str(r.get("class")), []).append(r)
    rng = random.Random(SEED)
    sample = []
    for c, lst in sorted(by_cls.items()):
        rng.shuffle(lst)
        sample.extend(lst[:min(per_class, len(lst))])
    sample.sort(key=lambda r: r["i"])
    print("目标 %d 条 · 分层抽样 %d 条（每类≤%d，种子 %d）· %d 进程"
          % (len(targets), len(sample), per_class, SEED, workers), flush=True)

    batch_sz = 120
    batches = [sample[i:i + batch_sz] for i in range(0, len(sample), batch_sz)]
    rows, detail_rows = [], []
    ustat = Counter()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers, initializer=_init, initargs=(str(lib_path),)) as pool:
        for k, (part, det, us) in enumerate(pool.imap_unordered(_work, batches), 1):
            rows.extend(part)
            detail_rows.extend(det)
            ustat.update(us)
            if k % 5 == 0:
                print("   ... %d/%d 批（%.0fs，切断累计 %d）"
                      % (k, len(batches), time.time() - t0, len(rows)), flush=True)

    # ★ 输出带"库名+样本量"（2026-10-15：防止再互相覆盖）
    tag = "%s_c%d" % (lib_path.stem, per_class)
    with open(OUT_DIR / ("usability_per_cut__%s.jsonl" % tag), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "annotation_candidates.jsonl", "w", encoding="utf-8") as f:
        for r in detail_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n = len(rows)
    verdict = Counter(r["why"] if not r["ok"] else "ok" for r in rows)
    after = [r for r in rows if not r["bl"]]
    na = len(after)
    usable_all = verdict.get("ok", 0)
    usable_after = sum(1 for r in after if r["ok"])
    r1 = [r for r in rows if r["why"].startswith("R1")]
    r1_complete = sum(1 for r in r1 if r["ratio"] >= 0.999)
    summary = {
        "sample_products": len(sample), "n_cuts": n, "workers": workers, "seed": SEED,
        "verdicts": dict(verdict),
        "usable_rate": round(usable_all / max(1, n), 4),
        "usable_rate_after_blacklist": round(usable_after / max(1, na), 4),
        "cuts_after_blacklist": na,
        "r1_n": len(r1), "r1_element_complete": r1_complete,
        "r1_element_complete_share": round(r1_complete / max(1, len(r1)), 4),
        "ustat": dict(ustat),
        "seconds": round(time.time() - t0, 1),
    }
    (OUT_DIR / ("usability_summary__%s.json" % tag)).write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("=" * 74)
    print("USPTO-50k 抽样可用性：%d 产物 · %d 切断" % (len(sample), n))
    for k, v in verdict.most_common():
        print("   %-28s %7d  %5.2f%%" % (k, v, 100.0 * v / max(1, n)))
    print("  可用率 %.2f%% -> 砍黑名单后 %.2f%%（剩 %d 切断）"
          % (100.0 * usable_all / max(1, n), 100.0 * usable_after / max(1, na), na))
    print("  R1 里元素全覆盖（确定性应判死）：%d/%d = %.1f%%"
          % (r1_complete, len(r1), 100.0 * r1_complete / max(1, len(r1))))
    print("  USTAT:", dict(ustat))
    print("  耗时 %.0fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

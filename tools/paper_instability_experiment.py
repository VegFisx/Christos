# -*- coding: utf-8 -*-
r"""论文实验（不稳定性）：同一批切断，在「安静 / 高负载 / 安静」三种机器状态下重判三次。

背景：R1 残基判据在中等分子上调用限时 MCS（rdFMCS timeout=2s）；超时返回的是部分结果，
**判定会随机器负载变化**。本实验量化翻转率（同一对 (目标,前体)，三次判定不一致的比例）。

口径：
  * 切断集：dirty-8 模板 × 56 目标产出的全部切断（与既有审计同一集合）
  * 每一轮：清空 MCS 缓存 -> step_usability 全量重判 -> 记录判定向量与 USTAT
  * 负载：第 2 轮期间另起 8 个 CPU 忙转进程（本机 20 逻辑核）
  * 输出：reports/paper/results/instability.json（含逐切断三轮判定）
用法: python tools/paper_instability_experiment.py
"""
from __future__ import annotations

import csv
import json
import subprocess
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

from rdkit import Chem, RDLogger                       # noqa: E402
import retro_search as rs                              # noqa: E402

RDLogger.DisableLog("rdApp.*")
OUT = STAGE / "reports" / "paper" / "results" / "instability.json"
DIRTY = [451, 452, 1208, 1041, 1042, 1161, 88, 954]
BURN = 8


def load_targets(n):
    seen, out = set(), []
    with open(STAGE / "reports" / "query_inventory_paths.csv",
              encoding="utf-8-sig", newline="") as f:
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


def burn(duration_s: float):
    t0 = time.time()
    x = 0
    while time.time() - t0 < duration_s:
        x = (x * 1103515245 + 12345) % 2147483647
    return x


def run_pass(cuts, label, load=False):
    rs.reset_usability_stats()
    rs._MCS_CACHE.clear()
    burners = []
    if load:
        code = ("import time,sys\n"
                "t0=time.time()\n"
                "x=0\n"
                "while time.time()-t0 < %f:\n"
                "    x=(x*1103515245+12345)%%2147483647\n" % 900.0)
        for _ in range(BURN):
            burners.append(subprocess.Popen([sys.executable, "-c", code],
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL))
        time.sleep(3.0)
    t0 = time.time()
    verdicts = []
    for tgt, prec in cuts:
        ok, why = rs.step_usability(tgt, prec)
        verdicts.append("ok" if ok else why.split("_")[0])
    dt = time.time() - t0
    for p in burners:
        p.terminate()
    print("   [%s] %d 切断 · %.0fs · USTAT=%s" % (label, len(cuts), dt,
          {k: v for k, v in rs.USTAT.items() if v}), flush=True)
    return verdicts, dt, dict(rs.USTAT)


def main() -> int:
    targets = load_targets(56)
    # ★ 2026-10-17（B10）：**优先读审计快照** `reports\_dirty8_r1_pairs.jsonl`（3,320 条），
    #   而不是按硬编码的模板下标重算 —— 模板库顺序变过，下标会漂移（实测重算得 0 条）。
    snap = STAGE / "reports" / "_dirty8_r1_pairs.jsonl"
    cuts = []
    if snap.exists():
        for ln in snap.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except Exception:                                # noqa: BLE001
                continue
            tgt = str(r.get("target") or "")
            prec = r.get("precursors") or []
            if isinstance(prec, str):
                try:
                    prec = json.loads(prec.replace("'", '"'))
                except Exception:                            # noqa: BLE001
                    prec = []
            prec = tuple(p for p in prec if p)
            if tgt and prec:
                cuts.append((tgt, prec))
        print("  切断集来自快照：%s" % snap.name)
    if not cuts:
        tmpl = rs.load_rdchiral_templates()
        by_idx = {i: t for i, t in enumerate(tmpl, 1)}
        for i in DIRTY:
            t = by_idx.get(i)
            if t is None:
                continue
            for tgt in targets:
                try:
                    outs = t.rxn.RunReactants((Chem.MolFromSmiles(tgt),))
                except Exception:
                    continue
                for tup in outs:
                    prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
                    prec = tuple(p for p in prec if p)
                    if prec:
                        cuts.append((tgt, prec))
        print("  切断集来自下标重算（DIRTY=%d 个模板）" % len(DIRTY))
    print("切断集 %d 条 · 三轮：安静 / 负载(%d 忙转) / 安静" % (len(cuts), BURN))

    v1, d1, u1 = run_pass(cuts, "pass1 quiet", load=False)
    v2, d2, u2 = run_pass(cuts, "pass2 loaded", load=True)
    v3, d3, u3 = run_pass(cuts, "pass3 quiet", load=False)

    flips_12 = sum(1 for a, b in zip(v1, v2) if a != b)
    flips_23 = sum(1 for a, b in zip(v2, v3) if a != b)
    flips_13 = sum(1 for a, b in zip(v1, v3) if a != b)
    any_flip = sum(1 for a, b, c in zip(v1, v2, v3) if len({a, b, c}) > 1)
    ok_flip = sum(1 for a, b in zip(v1, v2) if {a, b} == {"ok", "R1"})
    out = {
        "n_cuts": len(cuts),
        "verdict_counts": {label: dict(Counter(v)) for label, v in
                           (("quiet1", v1), ("loaded", v2), ("quiet2", v3))},
        "flips": {"quiet1_vs_loaded": flips_12, "loaded_vs_quiet2": flips_23,
                  "quiet1_vs_quiet2": flips_13, "any_of_three": any_flip,
                  "ok_R1_swaps_quiet1_loaded": ok_flip},
        "seconds": {"quiet1": d1, "loaded": d2, "quiet2": d3},
        "ustat": {"quiet1": u1, "loaded": u2, "quiet2": u3},
        "examples": [
            {"target": cuts[k][0][:70], "precursors": [p[:70] for p in cuts[k][1]],
             "quiet1": v1[k], "loaded": v2[k], "quiet2": v3[k]}
            for k in range(len(cuts)) if len({v1[k], v2[k], v3[k]}) > 1][:8],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("=" * 74)
    print("判定翻转：安静1 vs 负载 %d/%d (%.2f%%) · 负载 vs 安静2 %d/%d (%.2f%%)"
          % (flips_12, len(cuts), 100.0 * flips_12 / len(cuts),
             flips_23, len(cuts), 100.0 * flips_23 / len(cuts)))
    print("        安静1 vs 安静2 %d/%d · 三轮任一不同 %d/%d · ok<->R1 互换 %d"
          % (flips_13, len(cuts), any_flip, len(cuts), ok_flip))
    print("写出：%s" % OUT.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
r"""汇总子代理 ③ 的分片结果（parts dir）—— Lead 侧独立汇总，不依赖子代理自述。

只做三件事：
  1. 先打印一个 part 的**结构**（有哪些键、metrics 里有哪些变体），再写汇总逻辑
  2. 每个 part：ROC AUC / AU-PRC / Brier / ECE 在 test 上的跨 split 分布（raw / platt / iso）
  3. 若有拒识（覆盖率）结构，一并打印

跑法：& "D:\TCMAI\venv\Scripts\python.exe" tools\summarize_abs_parts.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np

PARTS = Path(r"C:\Users\Vegfish\AppData\Local\Temp\dshns_abs_parts")

# ★ 也支持直接指向「合并件」单个文件（如 reports/hte_absolute_model.json）
if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
    files = [Path(sys.argv[1])]
    PARTS = files[0].parent
else:
    files = sorted(p for p in PARTS.glob("*.json") if not p.name.startswith("_"))
print("=" * 100)
print(f"③ 分片汇总：{PARTS}   共 {len(files)} 个 part")
print("=" * 100)

if not files:
    print("没有 part 文件")
    sys.exit(0)

d0 = json.loads(files[0].read_text(encoding="utf-8"))
print(f"\n[结构] 首个 part = {files[0].name}")
print(f"  top-level keys: {list(d0.keys())}")
_runs_raw = d0.get("runs") or {}


def _as_list(x):
    """runs 可能是 list 也可能是 dict(run_id -> run)。"""
    if isinstance(x, dict):
        return list(x.values())
    return list(x)


runs = _as_list(_runs_raw)
print(f"  runs: {len(runs)}  (类型 {type(_runs_raw).__name__})")
if runs:
    print(f"  runs[0] keys: {list(runs[0].keys())}")
    res = runs[0].get("result")
    if isinstance(res, dict):
        print(f"  runs[0]['result'] keys: {list(res.keys())}")
        for k2, v2 in res.items():
            if isinstance(v2, dict):
                print(f"    result[{k2}] keys: {list(v2.keys())[:12]}")
            elif isinstance(v2, list):
                print(f"    result[{k2}] list len={len(v2)}"
                      + (f"  [0] keys={list(v2[0].keys())[:12]}" if v2 and isinstance(v2[0], dict) else ""))
            else:
                print(f"    result[{k2}] = {str(v2)[:80]}")

VARIANTS = ("raw", "platt", "iso")
METRICS = ("roc_auc", "au_prc", "brier", "ece")


def collect(d):
    """递归找出所有形如 {raw:{roc_auc..}, platt:{..}, iso:{..}} 的指标块。"""
    out = {v: {k: [] for k in METRICS} for v in VARIANTS}

    def walk(node):
        if isinstance(node, dict):
            for v in VARIANTS:
                sub = node.get(v)
                if isinstance(sub, dict) and "roc_auc" in sub:
                    for k in METRICS:
                        x = sub.get(k)
                        if isinstance(x, (int, float)) and x == x:
                            out[v][k].append(float(x))
            for v2 in node.values():
                walk(v2)
        elif isinstance(node, list):
            for v2 in node:
                walk(v2)

    walk(d)
    return out


print("\n" + "=" * 100)
print("各 part 的 test 指标（跨 iteration×split 的均值 ± 标准差；n = 有效次数）")
print("=" * 100)
print(f"{'part':<20} {'n':>4} {'AUC(raw)':>16} {'AUC(platt)':>16} {'AU-PRC':>8} "
      f"{'ECE(raw)':>9} {'ECE(platt)':>11} {'Brier':>8}")

rows = []
for p in files:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"{p.name:<20} 解析失败 {type(e).__name__}")
        continue
    c = collect(d)
    a = np.asarray(c["raw"]["roc_auc"], dtype=float)
    if a.size == 0:
        print(f"{p.name:<20} {'—':>4}  无 roc_auc")
        continue
    ap = np.asarray(c["platt"]["roc_auc"], dtype=float)
    pr = np.asarray(c["raw"]["au_prc"], dtype=float)
    er = np.asarray(c["raw"]["ece"], dtype=float)
    ep = np.asarray(c["platt"]["ece"], dtype=float)
    br = np.asarray(c["raw"]["brier"], dtype=float)
    fmt = lambda x: f"{x.mean():.3f}±{x.std():.3f}" if x.size else "—"
    print(f"{p.name[:19]:<20} {a.size:>4} {fmt(a):>16} {fmt(ap):>16} "
          f"{(f'{pr.mean():.3f}' if pr.size else '—'):>8} "
          f"{(f'{er.mean():.3f}' if er.size else '—'):>9} "
          f"{(f'{ep.mean():.3f}' if ep.size else '—'):>11} "
          f"{(f'{br.mean():.3f}' if br.size else '—'):>8}")
    rows.append({"part": p.name, "n": int(a.size),
                 "auc_raw_mean": float(a.mean()), "auc_raw_std": float(a.std()),
                 "auc_raw_min": float(a.min()), "auc_raw_max": float(a.max()),
                 "auc_platt_mean": float(ap.mean()) if ap.size else None,
                 "au_prc_mean": float(pr.mean()) if pr.size else None,
                 "ece_raw_mean": float(er.mean()) if er.size else None,
                 "ece_platt_mean": float(ep.mean()) if ep.size else None,
                 "brier_mean": float(br.mean()) if br.size else None})

out = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports") / "abs_parts_summary.json"


def _fmt(x, n=4):
    return f"{x:.{n}f}" if isinstance(x, (int, float)) and x == x else "—"


print("\n" + "=" * 100)
print("逐 run（合并件专用：核对每条配置的池化指标与拒识）")
print("=" * 100)
for p in files:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    raw = d.get("runs") or {}
    items = list(raw.items()) if isinstance(raw, dict) else list(enumerate(raw))
    if len(items) < 2:
        continue
    print(f"  {'run':<26} {'target':<8} {'模型':<4} {'特征':<4} {'AUC':>7} {'AUPRC':>7} "
          f"{'ECE':>7} {'prec@20%':>9} {'recall_total':>12}")
    for rid, r in items:
        res = r.get("result") or {}
        pooled = (res.get("pooled") or {}).get("raw") or {}
        m = pooled.get("metrics") or {}
        rej = {round(float(x.get("coverage", -1)), 1): x for x in (pooled.get("rejection") or [])}
        q = rej.get(0.2) or {}
        print(f"  {str(rid)[:25]:<26} {str(r.get('target'))[:7]:<8} {str(r.get('model')):<4} "
              f"{str(r.get('features')):<4} {_fmt(m.get('roc_auc')):>7} {_fmt(m.get('au_prc')):>7} "
              f"{_fmt(m.get('ece')):>7} {_fmt(q.get('prec_kept'), 3):>9} "
              f"{_fmt(q.get('recall_total'), 3):>12}")


def pooled_rejection(d):
    """result['pooled'][variant]['rejection'] -> {variant: [行...]}"""
    res = {}
    raw = d.get("runs") or {}
    run_list = list(raw.values()) if isinstance(raw, dict) else list(raw)
    for r in run_list:
        if not isinstance(r, dict):
            continue
        pooled = (r.get("result") or {}).get("pooled") or {}
        for v in VARIANTS:
            if isinstance(pooled.get(v), dict) and "rejection" in pooled[v]:
                res[v] = pooled[v]["rejection"]
    return res


print("\n" + "=" * 100)
print("③ 拒识表（pooled：只对最有把握的 X% 给判决时的精度）")
print("=" * 100)
first_rej = None
for p in files:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    rj = pooled_rejection(d)
    if rj and first_rej is None:
        first_rej = rj
    if not rj:
        continue
    raw_rows = rj.get("raw") or []
    if not raw_rows:
        continue
    covs = [r["coverage"] for r in raw_rows]
    vals = [r.get("prec_kept") for r in raw_rows]
    if p is files[0]:
        print(f"  行字段: {list(raw_rows[0].keys())}")
        print(f"  覆盖率档位: {covs}")
    print(f"  {p.name[:20]:<22} " + "  ".join(
        f"{c:.1f}:{(f'{v:.3f}' if isinstance(v, float) else '—')}" for c, v in zip(covs, vals)))

out.write_text(json.dumps({"parts_dir": str(PARTS), "n_parts": len(rows), "rows": rows,
                           "note": "Lead 侧独立汇总自子代理分片；rejection 见各行"},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n-> {out.name}")

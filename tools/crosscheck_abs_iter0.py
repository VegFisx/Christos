# -*- coding: utf-8 -*-
r"""交叉验证：把【我自己独立跑的 iteration_0/lr/F0】与【子代理 40-split 结果里的 iteration_0 子集】逐条对比。

为什么：③ 的头条数字来自子代理的分片，我要在把它写进结论前，用**另一个进程、另一次运行**在同一批切分上复算。
若逐条吻合 -> 子代理的数字可信；若不符 -> 以我自己的为准并查因。

跑法：& "D:\TCMAI\venv\Scripts\python.exe" tools\crosscheck_abs_iter0.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
PARTS = Path(os.environ.get("DSHNS_ABS_PARTS")
             or (Path(tempfile.gettempdir()) / "dshns_abs_parts"))
MINE = STAGE / "reports" / "hte_absolute_quick_F0_lr.json"
THEIRS = PARTS / "lr_F0_cal.json"


def per_split_iter0(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    raw = d.get("runs") or {}
    run_list = list(raw.values()) if isinstance(raw, dict) else list(raw)
    out = {}
    for r in run_list:
        for s in ((r.get("result") or {}).get("per_split") or []):
            if int(s.get("iteration", -1)) != 0:
                continue
            v = (((s.get("metrics") or {}).get("raw")) or {}).get("roc_auc")
            if isinstance(v, (int, float)):
                out[int(s.get("fold", -1))] = float(v)
    return out


print("=" * 92)
print("交叉验证：iteration_0 / lr / F0 的 raw ROC AUC —— 我的独立跑 vs 子代理分片")
print("=" * 92)
for p in (MINE, THEIRS):
    print(f"  {'存在' if p.exists() else '缺失'}: {p}")

if not (MINE.exists() and THEIRS.exists()):
    print("\n有一侧缺失，无法交叉验证")
    sys.exit(0)

a = per_split_iter0(MINE)
b = per_split_iter0(THEIRS)
print(f"\n  我的（{MINE.name}）: {len(a)} 个 split -> "
      + ", ".join(f"fold{k}={v:.4f}" for k, v in sorted(a.items())))
print(f"  子代理（{THEIRS.name}）: {len(b)} 个 split -> "
      + ", ".join(f"fold{k}={v:.4f}" for k, v in sorted(b.items())))

common = sorted(set(a) & set(b))
print(f"\n  可比 split: {common}")
bad = 0
for k in common:
    d = abs(a[k] - b[k])
    ok = d < 5e-4
    bad += 0 if ok else 1
    print(f"    fold{k}: 我 {a[k]:.6f}  子代理 {b[k]:.6f}  差值 {d:.2e}  {'✅' if ok else '❌'}")
print(f"\n  结论：{'✅ 逐条吻合（<5e-4），子代理数字可信' if bad == 0 else f'❌ {bad} 条不符，需查因'}")
if common:
    print(f"  均值：我 {sum(a[k] for k in common)/len(common):.4f}  "
          f"子代理 {sum(b[k] for k in common)/len(common):.4f}")

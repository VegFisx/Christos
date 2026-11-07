# -*- coding: utf-8 -*-
r"""独立验证 mined_forward_templates_v2.jsonl（子代理产物）：
  1. v1 vs v2 的模板集合/support 是否逐条一致（硬要求：重挖不许改变原有语义）
  2. v2 新增的条件字段覆盖率（多少条真拿到了温度/溶剂分布）
  3. K1 档（支持>=1，按 support 降序取前 600）里有多少条拿到了条件分布 —— 这决定门控能覆盖多少
  4. 打印 3 条原始记录（先看原文再写解析逻辑）

跑法：& "D:\TCMAI\venv\Scripts\python.exe" tools\check_v2_template_conditions.py
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

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
V1 = STAGE / "reports" / "mined_forward_templates.jsonl"
V2 = STAGE / "reports" / "mined_forward_templates_v2.jsonl"


def load(p: Path):
    rows, n_bad = [], 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            n_bad += 1
    return rows, n_bad


r1, bad1 = load(V1)
r2, bad2 = load(V2)
print("=" * 92)
print("独立验证：mined_forward_templates_v2.jsonl")
print("=" * 92)
print(f"  v1: {len(r1):,} 条（JSON 解析失败 {bad1}）   文件 {V1.stat().st_size/1e6:.1f} MB")
print(f"  v2: {len(r2):,} 条（JSON 解析失败 {bad2}）   文件 {V2.stat().st_size/1e6:.1f} MB")

print("\n[1] v2 记录的字段（首条 keys）")
print("   ", list(r2[0].keys()))
print("   原始样例（截断 200 字符）：")
for row in r2[:3]:
    print("    ", json.dumps(row, ensure_ascii=False)[:200])

print("\n[2] ★ 硬要求校验：v1 与 v2 的 (template -> support) 必须逐条一致")
m1 = {r["template"]: int(r.get("support", 0)) for r in r1}
m2 = {r["template"]: int(r.get("support", 0)) for r in r2}
only1 = set(m1) - set(m2)
only2 = set(m2) - set(m1)
diff = [t for t in (set(m1) & set(m2)) if m1[t] != m2[t]]
print(f"   v1 唯一模板 {len(m1):,}   v2 唯一模板 {len(m2):,}")
print(f"   仅 v1 有 {len(only1)}   仅 v2 有 {len(only2)}   support 不一致 {len(diff)}")
print(f"   -> {'✅ 一致' if not (only1 or only2 or diff) else '❌ 不一致，需回退'}")
if diff[:3]:
    for t in diff[:3]:
        print(f"      {t[:60]}  v1={m1[t]} v2={m2[t]}")

print("\n[3] v2 条件字段覆盖率（全部 %d 条）" % len(r2))
n_temp = sum(1 for r in r2 if isinstance(r.get("temp_C"), dict) and (r["temp_C"].get("n") or 0) > 0)
n_solv = sum(1 for r in r2 if isinstance(r.get("solvents"), dict) and len(r["solvents"]) > 0)
n_both = sum(1 for r in r2
             if isinstance(r.get("temp_C"), dict) and (r["temp_C"].get("n") or 0) > 0
             and isinstance(r.get("solvents"), dict) and len(r["solvents"]) > 0)
print(f"   有温度分布 {n_temp:,} ({n_temp/len(r2):.1%})   有溶剂分布 {n_solv:,} ({n_solv/len(r2):.1%})"
      f"   两者都有 {n_both:,} ({n_both/len(r2):.1%})")
if r2 and isinstance(r2[0].get("temp_C"), dict):
    print(f"   temp_C 样例键: {list(r2[0]['temp_C'].keys())}")

print("\n[4] ★ K1 档（支持>=1，support 降序取前 600）里有多少条拿到了条件分布")
srt = sorted(r2, key=lambda t: (-int(t.get("support", 0)), t["template"]))
k1 = srt[:600]
k1_temp = sum(1 for r in k1 if isinstance(r.get("temp_C"), dict) and (r["temp_C"].get("n") or 0) > 0)
k1_solv = sum(1 for r in k1 if isinstance(r.get("solvents"), dict) and len(r["solvents"]) > 0)
print(f"   K1 前 600 条：有温度 {k1_temp} ({k1_temp/len(k1):.1%})   有溶剂 {k1_solv} ({k1_solv/len(k1):.1%})")
print(f"   支持数范围：{k1[-1].get('support')} ~ {k1[0].get('support')}")

print("\n[5] 拿到温度分布的模板，温度区间有多宽（min/max）")
import numpy as np  # noqa: E402
w = [r["temp_C"]["max"] - r["temp_C"]["min"] for r in r2
     if isinstance(r.get("temp_C"), dict) and (r["temp_C"].get("n") or 0) > 0
     and r["temp_C"].get("max") is not None and r["temp_C"].get("min") is not None]
if w:
    a = np.asarray(w, dtype=float)
    print(f"   n={len(a)}  中位宽 {np.median(a):.0f}℃  p10 {np.percentile(a,10):.0f}  "
          f"p90 {np.percentile(a,90):.0f}  宽<=0 的 {int((a<=0).sum())} 条")

print("\n[6] ★ 关键追问：0 宽是不是因为「只有 1 条来源记录」？")
ns = np.asarray([int(r["temp_C"].get("n") or 0) for r in r2
                 if isinstance(r.get("temp_C"), dict)], dtype=int)
for lo, hi, lab in ((1, 1, "n=1"), (2, 2, "n=2"), (3, 5, "n=3-5"), (6, 10**9, "n>5")):
    m = (ns >= lo) & (ns <= hi)
    print(f"   {lab:<6} {int(m.sum()):>5} 条")
for thr in (2, 3):
    sel = [r for r in r2 if isinstance(r.get("temp_C"), dict)
           and (r["temp_C"].get("n") or 0) >= thr
           and r["temp_C"].get("max") is not None]
    if sel:
        b = np.asarray([r["temp_C"]["max"] - r["temp_C"]["min"] for r in sel], dtype=float)
        print(f"   n>={thr}: {len(b):>5} 条 → 中位宽 {np.median(b):.0f}℃  p90 "
              f"{np.percentile(b,90):.0f}℃  宽>0 的 {int((b>0).sum())} 条")

print("\n[7] K1 前 600 条里，温度和溶剂**各自**能门控多少（n>=2 才算有分布）")
k1_n2 = sum(1 for r in k1 if isinstance(r.get("temp_C"), dict) and (r["temp_C"].get("n") or 0) >= 2)
k1_n1 = sum(1 for r in k1 if isinstance(r.get("temp_C"), dict) and (r["temp_C"].get("n") or 0) == 1)
k1_ns = sum(1 for r in k1 if isinstance(r.get("solvents"), dict) and len(r["solvents"]) > 0)
k1_any = sum(1 for r in k1 if (isinstance(r.get("temp_C"), dict) and (r["temp_C"].get("n") or 0) > 0)
             or (isinstance(r.get("solvents"), dict) and len(r["solvents"]) > 0))
print(f"   有温度 n>=2: {k1_n2}   有温度 n==1: {k1_n1}   有溶剂: {k1_ns}   "
      f"任一种: {k1_any}   （共 {len(k1)}）")

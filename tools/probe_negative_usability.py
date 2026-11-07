# -*- coding: utf-8 -*-
r"""第十三轮（探针 3）：反例候选能不能用来测假阳性率？—— 先查可用性。

回答：449 条候选里，多少条有可解析的 CXSMILES / 温度 / 溶剂 / 两组分以上反应物？
（不能解析的候选，后面没法喂给正向引擎，必须先把数字说清楚，别事后才发现样本只剩 10 条。）

用法: python probe_negative_usability.py
"""
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
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")
JSONL = STAGE / "reports" / "negative_examples.jsonl"

recs = [json.loads(l) for l in JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"候选 {len(recs)} 条")

c = Counter()
units = Counter()
n_react = Counter()
examples = []
for r in recs:
    cx = r.get("cxsmiles") or ""
    if not cx:
        c["无CXSMILES"] += 1
        continue
    c["有CXSMILES"] += 1
    body = cx.split("|", 1)[0] if "|" in cx else cx
    parts = body.split(">")
    if len(parts) != 3:
        c[f"段数={len(parts)}"] += 1
        continue
    lhs, agents, rhs = parts
    rs = [p for p in lhs.split(".") if p.strip()]
    ps = [p for p in rhs.split(".") if p.strip()]
    n_react[len(rs)] += 1
    if not ps:
        c["产物侧为空"] += 1
        continue
    ok_r = all(Chem.MolFromSmiles(p.split(":")[0] if False else p) is not None for p in rs)
    ok_p = all(Chem.MolFromSmiles(p) is not None for p in ps)
    if not ok_r:
        c["有反应物SMILES非法"] += 1
    if not ok_p:
        c["有产物SMILES非法"] += 1
    if ok_r and ok_p and len(rs) >= 2:
        c["可喂给引擎(>=2反应物)"] += 1
    t = r.get("temperature")
    if isinstance(t, dict) and t.get("value") is not None:
        c["有温度"] += 1
        units[str(t.get("units"))] += 1
    else:
        c["无温度"] += 1
    if r.get("solvents"):
        c["有溶剂"] += 1
    if len(examples) < 5 and ok_r and ok_p and len(rs) >= 2:
        examples.append(r)

print()
for k in ("有CXSMILES", "无CXSMILES", "产物侧为空", "有反应物SMILES非法", "有产物SMILES非法",
          "可喂给引擎(>=2反应物)", "有温度", "无温度", "有溶剂"):
    print(f"  {k:<26} {c.get(k, 0)}")
print(f"  段数异常: {[ (k,v) for k, v in c.items() if k.startswith('段数') ]}")
print(f"  反应物个数分布: {dict(sorted(n_react.items()))}")
print(f"  温度单位分布: {dict(units)}")
print()
print("  样例（可用于假阳性率测量）:")
for r in examples:
    cx = (r["cxsmiles"] or "")[:150]
    print(f"    id={r['reaction_id']}  匹配={r['matched']}")
    print(f"      T={r['temperature']}  溶剂={r['solvents']}")
    print(f"      CX: {cx}")
    print(f"      上下文: {(r['contexts'][0]['context'] if r['contexts'] else '')[:130]!r}")

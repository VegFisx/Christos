#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A8 自检：21 个预置条件档的出处登记必须完整、可追溯、且与实际数值一致。

跑法：
    python -I tools\\test_template_provenance.py
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

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "conditions",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import templates as T                      # noqa: E402

PROV = json.loads((ROOT / "conditions" / "template_provenance.json").read_text(encoding="utf-8"))
STATUSES = set((PROV.get("status_vocabulary") or {}).keys())
fails = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        fails.append(msg)


print("== 1. 覆盖完整 ==")
entries = PROV.get("templates") or {}
check(set(entries) == set(T.TEMPLATES),
      "登记表与 TEMPLATES 完全一致（%d 个）" % len(T.TEMPLATES))

print("== 2. 状态合法 ==")
bad = [n for n, v in entries.items() if v.get("status") not in STATUSES]
check(not bad, "所有状态都在词表内 %s" % (bad or ""))

print("== 3. cited 必须带 DOI/URL ==")
nodo = []
for n, v in entries.items():
    if v.get("status") != "cited":
        continue
    if not any((c.get("source") or {}).get("doi") or (c.get("source") or {}).get("url")
               for c in v.get("citations") or []):
        nodo.append(n)
check(not nodo, "cited 项都有可追溯标识 %s" % (nodo or ""))

print("== 4. 登记数值 == 实际模板数值 ==")
drift = []
for n, v in entries.items():
    tv = v.get("template_values") or {}
    c = T.TEMPLATES[n]
    if (tv.get("temperature"), tv.get("time_min")) != (c.temperature, c.time_min):
        drift.append((n, tv, (c.temperature, c.time_min)))
check(not drift, "温度/时长无漂移 %s" % (drift or ""))

print("== 5. 引句非空（cited）==")
empty = [n for n, v in entries.items()
         if v.get("status") == "cited"
         and not any((c.get("quote") or "").strip() for c in v.get("citations") or [])]
check(not empty, "cited 项都带原句 %s" % (empty or ""))

print("== 6. provenance_of / list_templates ==")
p = T.provenance_of("炮制·醋炙")
check(p["status"] == "cited" and "10.1002/bmc.70636" in p["doi"],
      "醋炙 → cited + DOI（实际 %s）" % p)
check(T.provenance_of("煎煮")["status"] == "convention", "煎煮 → convention")
check(T.provenance_of("醇提")["status"] == "physics", "醇提 → physics")
check(T.provenance_of("不存在的档")["status"] == "unknown", "未知档 → unknown")
text = T.list_templates()
check(text.count("[") >= len(T.TEMPLATES), "list_templates 每行都带标签")

print("")
if fails:
    print("FAILED %d 项" % len(fails))
    raise SystemExit(1)
print("ALL PASS（6 组检查）")

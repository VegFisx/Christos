# -*- coding: utf-8 -*-
r"""看 mitsunobu / suzuki 这类"需要特定试剂"的规则，字段里有没有可用的试剂信息。"""
import json
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
d = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))
rules = d["rules"]

print("=" * 92)
print("① 全部 64 条规则的 co_reagents / byproducts（看它到底记什么）")
print("=" * 92)
for r in rules:
    cr = r.get("co_reagents") or {}
    bp = r.get("byproducts") or {}
    if cr or bp:
        print(f"  {r['name'][:18]:<20} co={str(cr)[:46]:<48} by={str(bp)[:30]}")

print()
print("=" * 92)
print("② mitsunobu 相关规则的完整内容")
print("=" * 92)
for r in rules:
    if "mitsunobu" in r["name"].lower() or "光延" in r["name"]:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:1500])

print()
print("=" * 92)
print("③ 有没有规则提到 PPh3 / 三苯基膦 / DEAD 这类试剂")
print("=" * 92)
import re
kw = ["PPh3", "三苯基膦", "triphenylphosphine", "DEAD", "偶氮二甲酸", "azodicarboxyl",
      "HATU", "DCC", "Pd(", "钯", "CuI", "NaH", "氢化钠"]
for r in rules:
    blob = json.dumps(r, ensure_ascii=False)
    hits = [k for k in kw if k.lower() in blob.lower()]
    if hits:
        print(f"  {r['name'][:22]:<24} 命中: {hits}")

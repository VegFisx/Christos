# -*- coding: utf-8 -*-
# 一次性探查：剩余假路线最集中的 8 条模板的化学画像（smarts / 反应中心指纹 / 数量）
import json
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

rows = [json.loads(l) for l in open(r"reports\retro_template_audit_r41.jsonl", encoding="utf-8") if l.strip()]
by_idx = {r["idx"]: r for r in rows}

lib = {}
for line in open(r"reports\retro_templates_clustered.jsonl", encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    r = json.loads(line)
    lib[r.get("template")] = r

DIRTY = [451, 452, 1208, 1041, 1042, 1161, 88, 954]
print("== 剩余 R1 最集中的 8 条模板 ==")
for i in DIRTY:
    r = by_idx[i]
    rec = lib.get(r.get("smarts"), {})
    print("-" * 100)
    print("idx %4d try %5d usable %3d R1 %5d | freq %s" % (
        i, r.get("n_try", 0), r.get("n_usable", 0), r.get("R1_残基路线", 0), rec.get("freq")))
    print("  smarts:", str(r.get("smarts"))[:110])
    print("  fp(R|P):", str(rec.get("fp"))[:110])

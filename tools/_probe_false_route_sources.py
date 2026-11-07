# -*- coding: utf-8 -*-
# 一次性探查（第41轮后续）：假路线"按来源封杀"可行性 =
#   ① 模板库有没有来源字段；② 32 条"偶尔能用"模板的 R1 与可用能不能分开
import json
import sys
import collections

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

lib = r"reports\retro_templates_clustered.jsonl"
keys = collections.Counter()
by_smarts = {}
n_lib = 0
for line in open(lib, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    r = json.loads(line)
    n_lib += 1
    keys.update(r.keys())
    by_smarts[r.get("template")] = r
print("== 模板库 retro_templates_clustered.jsonl ==")
print("行数", n_lib)
print("字段出现次数:", dict(keys))
s = next(iter(by_smarts.values()))
print("样例字段预览:", {k: str(v)[:70] for k, v in s.items()})

print()
print("== r41 体检：非黑名单模板的 R1/可用分布 ==")
rows = [json.loads(l) for l in open(r"reports\retro_template_audit_r41.jsonl", encoding="utf-8") if l.strip()]
keep = [r for r in rows if not r.get("blacklisted")]
tot_r1 = sum(r.get("R1_残基路线", 0) for r in keep)
tot_us = sum(r.get("n_usable", 0) for r in keep)
keep.sort(key=lambda r: -r.get("R1_残基路线", 0))
print("模板数 %d · R1 合计 %d · 可用合计 %d" % (len(keep), tot_r1, tot_us))
run = 0
for r in keep[:14]:
    run += r.get("R1_残基路线", 0)
    print("idx %4d try %5d usable %4d R1 %5d R2 %5d | cum R1 %.0f%%" % (
        r["idx"], r.get("n_try", 0), r.get("n_usable", 0), r.get("R1_残基路线", 0),
        r.get("R2_前体大于目标", 0), 100 * run / max(1, tot_r1)))
rest = keep[14:]
print("其余 %d 条: R1 合计 %d · 可用合计 %d" % (
    len(rest), sum(r.get("R1_残基路线", 0) for r in rest),
    sum(r.get("n_usable", 0) for r in rest)))
z_us = [r["idx"] for r in keep if r.get("n_usable", 0) > 0]
big_r1 = [r["idx"] for r in keep if r.get("R1_残基路线", 0) >= 100]
both = sorted(set(z_us) & set(big_r1))
print("有可用产出的 idx：%d 条" % len(z_us))
print("R1>=100 的 idx：%d 条" % len(big_r1))
print("交集（又出可用又大量产 R1）：%d 条 -> %s" % (len(both), both[:14]))
for r in keep[:3]:
    print("smarts:", str(r.get("smarts"))[:84])
    rec = by_smarts.get(r.get("smarts"))
    if rec:
        print("   库里附加字段:", {k: str(v)[:56] for k, v in rec.items() if k != "template"})

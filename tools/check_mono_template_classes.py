# -*- coding: utf-8 -*-
r"""单底物模板分类普查：3,256 条里，多少是"自给自足"、多少需要共试剂？

判据 `rdkit_template_lib.needs_co_reagent`：产物侧出现**未映射重原子** -> 那个原子来自试剂。
"""
from __future__ import annotations

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
sys.path.insert(0, str(STAGE / "tools"))
from rdkit_template_lib import compile_templates_all, needs_co_reagent, MinedTemplate  # noqa: E402

MONO = STAGE / "reports" / "mined_mono_templates.jsonl"
tpls = []
for line in MONO.read_text(encoding="utf-8").splitlines():
    if line.strip():
        d = json.loads(line)
        tpls.append(MinedTemplate(smarts=d["template"], support=int(d.get("support", 0))))

by, nfail = compile_templates_all(tpls)
print("=" * 92)
print(f"单底物模板分类（{MONO.name}，{len(tpls):,} 条）")
print("=" * 92)
print(f"  按元数编译：{ {k: len(v) for k, v in sorted(by.items())} }   编译失败 {nfail}")

arity1 = by.get(1, [])
selfc, needs = [], []
unknown = 0
for sm, rx in arity1:
    r = needs_co_reagent(sm)
    if r is None:
        unknown += 1
    elif r:
        needs.append(sm)
    else:
        selfc.append(sm)
print(f"\n  arity=1 共 {len(arity1):,} 条：")
print(f"    ★ 自给自足（产物侧全映射，可直接套用）：{len(selfc):,}  ({len(selfc)/max(1,len(arity1)):.1%})")
print(f"    ⚠ 需要共试剂（产物侧有未映射原子）：{len(needs):,}  ({len(needs)/max(1,len(arity1)):.1%})")
print(f"    判不了：{unknown}")

# support 加权
sup = {json.loads(l)["template"]: int(json.loads(l).get("support", 0))
       for l in MONO.read_text(encoding="utf-8").splitlines() if l.strip()}
s_self = sum(sup.get(s, 0) for s in selfc)
s_need = sum(sup.get(s, 0) for s in needs)
print(f"\n  support 加权：自给自足 {s_self:,} 次 vs 需共试剂 {s_need:,} 次")

print("\n  自给自足样例（前 6）：")
for s in selfc[:6]:
    print(f"    {s[:120]}")
print("\n  需共试剂样例（前 6）：")
for s in needs[:6]:
    print(f"    {s[:120]}")

out = STAGE / "reports" / "mono_template_classes.json"
out.write_text(json.dumps({
    "n_total": len(tpls), "arity": {str(k): len(v) for k, v in sorted(by.items())},
    "arity1_self_contained": len(selfc), "arity1_needs_co_reagent": len(needs),
    "support_self": s_self, "support_needs": s_need,
    "self_contained_templates": selfc,
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n-> {out.name}")

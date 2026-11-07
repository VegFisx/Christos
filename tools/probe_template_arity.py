# -*- coding: utf-8 -*-
r"""模板"元数"普查：每个反应模板需要几个反应物？

## 为什么要这个
`tools/rdkit_template_lib.py::compile_templates()` **只保留恰好 2 个反应物**的模板：
```python
if rx is None or rx.GetNumReactantTemplates() != 2: n_fail += 1; continue
```
而**水解 / 氧化 / 还原 / 脱羧 / 异构化**这类反应通常是**单底物（+ 试剂）** —— 用 1 个反应物模板描述。
若库里这类模板很多，我们等于**把整类化学丢掉了**（第二十一轮普查：这些类在 ORD 里合计约 8.5 万条）。
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import RDLogger                    # noqa: E402
from rdkit.Chem import rdChemReactions        # noqa: E402

RDLogger.DisableLog("rdApp.*")

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
SR = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
V1 = STAGE / "reports" / "mined_forward_templates.jsonl"
V2 = STAGE / "reports" / "mined_forward_templates_v2.jsonl"


def arity(smarts: str):
    try:
        rx = rdChemReactions.ReactionFromSmarts(smarts)
    except Exception:
        return None
    if rx is None:
        return None
    return (rx.GetNumReactantTemplates(), rx.GetNumProductTemplates())


print("=" * 100)
print("模板元数普查：需要几个反应物？")
print("=" * 100)

# ---------------- SmartReact 官方库 ----------------
dist = Counter()
per_class = defaultdict(Counter)
n = 0
for i, line in enumerate(SR.read_text(encoding="utf-8", errors="replace").splitlines()):
    if i == 0 or not line.strip():
        continue
    f = line.split("\t")
    if len(f) < 4:
        continue
    name, tmpl = f[0], f[3]
    a = arity(tmpl)
    n += 1
    if a is None:
        dist["解析失败"] += 1
        continue
    dist[a[0]] += 1
    per_class[name][a[0]] += 1

print(f"\n[1] SmartReact 官方库（{n:,} 条模板）")
for k in sorted(dist, key=lambda x: str(x)):
    print(f"    需要 {k} 个反应物：{dist[k]:>6,}  ({dist[k]/n:6.1%})")

one = [(c, v[1], sum(v.values())) for c, v in per_class.items() if v[1]]
one.sort(key=lambda x: -x[1])
print(f"\n    ★ 含【单反应物】模板的反应类型（共 {len(one)} 类，含 1 反应物模板 {dist[1]:,} 条）：")
for c, k, tot in one[:20]:
    print(f"      {c:<36} 1反应物 {k:>4} / 共 {tot:>4}")

# ---------------- 我们自抽的模板 ----------------
import json  # noqa: E402
for label, path in (("v1（当前引擎用的）", V1), ("v2（带源条件）", V2)):
    if not path.exists():
        print(f"\n[{label}] 不存在：{path}")
        continue
    d2 = Counter()
    ex_one = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        a = arity(rec.get("template", ""))
        if a is None:
            d2["解析失败"] += 1
            continue
        d2[a[0]] += 1
        if a[0] == 1 and len(ex_one) < 2:
            ex_one.append(rec.get("template", "")[:100])
    tot = sum(d2.values())
    print(f"\n[2] 自抽模板 {label}（{tot:,} 条）")
    for k in sorted(d2, key=lambda x: str(x)):
        print(f"    需要 {k} 个反应物：{d2[k]:>6,}  ({d2[k]/max(1,tot):6.1%})")
    for e in ex_one:
        print(f"      1反应物样例: {e}")

print("\n★ 读法：`compile_templates` 只收「恰好 2 个反应物」→ 上表里 1 反应物的那些**现在全被丢掉**。")

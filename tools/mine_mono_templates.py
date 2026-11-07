# -*- coding: utf-8 -*-
r"""单底物（mono-substrate）正向模板挖掘 —— 补上被 `len(plains) != 2` 整类跳过的那 22%。

## 为什么
`tools/forward_template_mining.py:473-476`：
```python
raws, plains = mc.contributing_components(lhs, pmaps)
if len(plains) != 2:      # 只挖"恰好 2 个贡献组分"
    skip[f"贡献组分={len(plains)}"] += 1
```
而 40,000 抽样里 **`贡献组分=1` 有 8,745 条（21.9%）** 被整类跳过 ——
那正是**水解 / 氧化 / 还原 / 脱羧 / 消除**这类"单底物 + 试剂"的化学
（第二十一轮普查：还原 7.5%、氧化 1.2%、水解 0.3%、脱羧 0.3%、异构化 2.4%）。

## 口径（与 v1 挖掘保持一致，便于对比）
  · 抽样：duckdb `USING SAMPLE N ROWS (reservoir, 20261012)` —— 与 v1 同 seed
  · 贡献组分判定：`mapped_chem.contributing_components`（产物映射原子占比 > 0.5）
  · **只取 `len(plains) == 1`** 的记录；用 rdchiral `extract_from_reaction` 抽模板
  · 去重按模板 SMARTS；support = 复现次数；按 support 降序落盘
  · 时间预算（墙钟）到点即停并**如实打印已处理量**（不许静默截断）

跑法：& "D:\TCMAI\venv\Scripts\python.exe" tools\mine_mono_templates.py [抽样数] [预算秒]
产出：reports/mined_mono_templates.jsonl + reports/mined_mono_templates_summary.json
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from rdkit import RDLogger  # noqa: E402
from rdchiral.template_extractor import extract_from_reaction  # noqa: E402

import mapped_chem as mc  # noqa: E402

RDLogger.DisableLog("rdApp.*")

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
OUT = STAGE / "reports" / "mined_mono_templates.jsonl"
OUT_SUM = STAGE / "reports" / "mined_mono_templates_summary.json"

N_SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
SEED = 20261012
BUDGET_S = float(sys.argv[2]) if len(sys.argv) > 2 else 1800.0
FULL = (N_SAMPLE <= 0)          # ★ N_SAMPLE<=0 -> 全量流式（1,771,032 条）
HEAVY_CAP = 70
BATCH = 20000
FLUSH_EVERY = 5

print("=" * 100, flush=True)
if FULL:
    print(f"单底物模板挖掘【全量流式】  预算 {BUDGET_S:.0f}s  批大小 {BATCH}", flush=True)
else:
    print(f"单底物模板挖掘：抽样 {N_SAMPLE:,}（seed {SEED}）  预算 {BUDGET_S:.0f}s", flush=True)
print("=" * 100, flush=True)

con = duckdb.connect()
if FULL:
    cursor = con.execute(f"SELECT reaction FROM read_parquet('{BIG.as_posix()}')")
else:
    cursor = con.execute(f"""
        SELECT reaction FROM read_parquet('{BIG.as_posix()}')
        USING SAMPLE {N_SAMPLE} ROWS (reservoir, {SEED})
    """)

skip = Counter()
tmpl_support = Counter()
examples = []
n_mono = 0
n_seen = 0
t0 = time.time()
timed_out = False


def flush(note: str = ""):
    """把当前模板按 support 降序落盘（增量保存，避免长跑崩了全丢）。"""
    with open(OUT, "w", encoding="utf-8") as f:
        for t, s in tmpl_support.most_common():
            f.write(json.dumps({"template": t, "generalized": None, "support": s},
                               ensure_ascii=False) + "\n")


def handle(blob) -> None:
    """处理一条 ORD 记录：是单底物就抽模板。"""
    global n_mono
    rxn = reaction_pb2.Reaction()
    try:
        rxn.ParseFromString(bytes(blob))
    except Exception:
        skip["protobuf失败"] += 1
        return
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES and i.value), None)
    if not cx:
        skip["无CXSMILES"] += 1
        return
    lhs, agents, rhs = mc.split_rxn(cx)
    if not lhs or not rhs:
        skip["拆段失败"] += 1
        return
    pm = mc.parse_plain(rhs)
    if pm is None:
        skip["产物SMILES非法"] += 1
        return
    pmaps = mc.map_nums(pm)
    if not pmaps:
        skip["产物无映射"] += 1
        return
    raws, plains = mc.contributing_components(lhs, pmaps)
    if len(plains) != 1:
        skip[f"贡献组分={len(plains)}（本轮只要 1）"] += 1
        return
    if len(raws) != 1:
        skip["raws/plains 长度不一致"] += 1
        return
    n_mono += 1
    if pm.GetNumHeavyAtoms() > HEAVY_CAP:
        skip["产物重原子过大"] += 1
        return
    try:
        # ★ 键名照抄既有脚本 forward_template_mining.py:560-562：
        #   reactants / reagents / products（复数！）/ _id —— 我第一次写成 "product" 导致 8730 次 KeyError
        out = extract_from_reaction({"reactants": raws[0], "reagents": agents or "",
                                     "products": rhs, "_id": "x"})
    except Exception as e:
        # ★ 不许静默：把异常类型+首条原文记下来（第一版只计数，等于把 8730 次失败藏了起来）
        key = f"rdchiral异常 {type(e).__name__}: {str(e)[:90]}"
        skip[key] += 1
        return
    if not out or not out.get("reaction_smarts"):
        skip["抽不出模板"] += 1
        if len(examples) < 6:
            examples.append({"template": f"[失败] out={str(out)[:80]}",
                             "plains": plains[0][:60], "rhs": rhs[:80]})
        return
    sm = out["reaction_smarts"]
    tmpl_support[sm] += 1
    if len(examples) < 3:
        examples.append({"template": sm[:150], "plains": plains[0][:60], "rhs": rhs[:80]})


n_batch = 0
while True:
    if time.time() - t0 > BUDGET_S:
        timed_out = True
        break
    rows = cursor.fetchmany(BATCH)
    if not rows:
        break
    for (blob,) in rows:
        if time.time() - t0 > BUDGET_S:
            timed_out = True
            break
        n_seen += 1
        handle(blob)
    n_batch += 1
    if n_batch % FLUSH_EVERY == 0:
        flush()
        print(f"  [批 {n_batch}] 已读 {n_seen:,}  单底物 {n_mono:,}  模板 {len(tmpl_support):,}  "
              f"{time.time()-t0:.0f}s", flush=True)
    if timed_out:
        break

flush()
el = time.time() - t0
print(f"\n  处理耗时 {el:.1f}s   {'⚠ 到预算上限提前停止' if timed_out else '跑完'}", flush=True)
print(f"  已读记录 {n_seen:,}   单底物记录（贡献组分=1）：{n_mono:,}", flush=True)
print(f"  抽出模板去重：{len(tmpl_support):,}", flush=True)
sup = sorted(tmpl_support.values(), reverse=True)
if sup:
    print(f"  support：max {sup[0]}  >=2 的 {sum(1 for x in sup if x >= 2):,}  "
          f">=5 的 {sum(1 for x in sup if x >= 5):,}", flush=True)
print(f"  跳过分类（前 12）：{dict(skip.most_common(12))}", flush=True)
for e in examples:
    print(f"  样例：{e['template']}", flush=True)

with open(OUT, "w", encoding="utf-8") as f:
    for t, s in tmpl_support.most_common():
        f.write(json.dumps({"template": t, "generalized": None, "support": s},
                           ensure_ascii=False) + "\n")
OUT_SUM.write_text(json.dumps({
    "scratch": "单底物（贡献组分=1）正向模板挖掘：补上 forward_template_mining.py 里被跳过的 21.9%",
    "mode": "full" if FULL else "sample",
    "n_sample": 0 if FULL else N_SAMPLE, "seed": SEED, "budget_s": BUDGET_S,
    "timed_out": timed_out, "seconds": round(el, 1),
    "n_records_seen": n_seen, "n_mono_records": n_mono,
    "n_templates_unique": len(tmpl_support),
    "support_ge2": sum(1 for x in sup if x >= 2),
    "support_ge5": sum(1 for x in sup if x >= 5),
    "skip": dict(skip),
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n-> {OUT.name} / {OUT_SUM.name}", flush=True)

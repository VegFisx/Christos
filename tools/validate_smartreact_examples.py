# -*- coding: utf-8 -*-
r"""SmartReact 9770 条模板的全量验收 —— 用每条模板【自带的 example】验证。

★ 数据是作者给的（templates.txt 的 example 列），不是我手写的 ★

对每条模板：
  1. 从 example 拆出 底物A / 底物B / 期望产物
  2. 喂进 ReactionEnumerator.enumerate_pair
  3. 看期望产物能不能被枚举出来

两个指标（含义不同，都报）：
  · 宽松命中 hit_any  ：期望产物出现在【任意】模板的产物里
  · 严格命中 hit_own  ：期望产物出现在【该模板自己】的产物里   ← 这才是"模板能重现自己的例子"

产物比对用 RDKit 规范化 SMILES，避免写法差异造成假阴性。

输出：控制台摘要 + JSON 明细（staging\reports\）。
"""
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem, RDLogger  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TEMPLATES = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
REPORTS = STAGE / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)
OUT_JSON = REPORTS / "smartreact_example_validation.json"


def canon(smi):
    """规范化 SMILES；失败返回 None。"""
    try:
        m = Chem.MolFromSmiles(smi)
        return Chem.MolToSmiles(m) if m is not None else None
    except Exception:
        return None


# ---------------- 读模板 ----------------
rows = []
for line in TEMPLATES.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
    f = line.split("\t")
    if len(f) == 5:
        rows.append(f)
print(f"载入模板 {len(rows)} 条", flush=True)

t0 = time.time()
enum = ReactionEnumerator()
print(f"构造枚举器完成 {time.time()-t0:.2f}s", flush=True)

# ---------------- 全量跑 ----------------
results = []
t0 = time.time()
for i, (rname, tid, example, smarts, cats) in enumerate(rows):
    if ">>" not in example:
        results.append({"i": i, "reaction_name": rname, "template_id": tid,
                        "status": "error", "err": "example 无 '>>'"})
        continue
    lhs, rhs = example.split(">>", 1)
    reactants = [s for s in lhs.split(".") if s]
    expected = canon(rhs)
    if expected is None:
        results.append({"i": i, "reaction_name": rname, "template_id": tid,
                        "status": "error", "err": "期望产物 SMILES 非法"})
        continue
    if len(reactants) != 2:
        results.append({"i": i, "reaction_name": rname, "template_id": tid,
                        "status": "error", "err": f"底物数={len(reactants)}"})
        continue

    try:
        res = enum.enumerate_pair(reactants[0], reactants[1])
    except Exception as ex:
        results.append({"i": i, "reaction_name": rname, "template_id": tid,
                        "status": "error", "err": f"{type(ex).__name__}: {str(ex)[:150]}"})
        continue

    any_hit = False
    own_hit = False
    n_prod = 0
    for r in res:
        for p in r.products:
            n_prod += 1
            cp = canon(p)
            if cp is None:
                continue
            if cp == expected:
                any_hit = True
                if r.reaction_name == rname:
                    own_hit = True

    status = "hit_own" if own_hit else ("hit_other" if any_hit else "miss")
    results.append({"i": i, "reaction_name": rname, "template_id": tid,
                    "status": status, "n_products": n_prod})

    if (i + 1) % 500 == 0:
        dt = time.time() - t0
        print(f"  {i+1}/{len(rows)}  已用 {dt/60:.1f} 分钟  预计还需 "
              f"{dt/(i+1)*(len(rows)-i-1)/60:.1f} 分钟", flush=True)

dt = time.time() - t0
print(f"\n全量跑完，耗时 {dt/60:.1f} 分钟", flush=True)

# ---------------- 汇总 ----------------
st = Counter(r["status"] for r in results)
n = len(results)

print()
print("=" * 78)
print("总成绩")
print("=" * 78)
for k, label in [("hit_own", "严格命中（该模板自己复现了作者的例子）"),
                 ("hit_other", "宽松命中（别的模板产出了，但自己没命中）"),
                 ("miss", "完全没命中"),
                 ("error", "报错")]:
    c = st.get(k, 0)
    print(f"  {label:<38} {c:>5}  ({c/n*100:5.1f}%)")
print(f"  {'-'*38} {'-'*5}")
print(f"  {'合计':<38} {n:>5}")
print(f"\n  ★ 严格命中率 {st.get('hit_own',0)/n*100:.1f}%"
      f"   （宽松命中率 {(st.get('hit_own',0)+st.get('hit_other',0))/n*100:.1f}%）")

# 按反应类型
print()
print("=" * 78)
print("按反应类型（37 种，按严格命中率排序）")
print("=" * 78)
by = defaultdict(lambda: [0, 0, 0, 0])   # total, own, other, miss
for r in results:
    b = by[r["reaction_name"]]
    b[0] += 1
    if r["status"] == "hit_own":
        b[1] += 1
    elif r["status"] == "hit_other":
        b[2] += 1
    elif r["status"] == "miss":
        b[3] += 1

print(f"  {'reaction_name':<32} {'总数':>5} {'严格':>5} {'宽松':>5} {'未中':>5} {'命中率':>7}")
for name, b in sorted(by.items(), key=lambda kv: -(kv[1][1] / kv[1][0] if kv[1][0] else 0)):
    rate = b[1] / b[0] * 100 if b[0] else 0
    print(f"  {name:<32} {b[0]:>5} {b[1]:>5} {b[2]:>5} {b[3]:>5} {rate:>6.1f}%")

# 保存明细
OUT_JSON.write_text(json.dumps({
    "n_templates": n,
    "elapsed_min": dt / 60,
    "status_counts": dict(st),
    "strict_hit_rate": st.get("hit_own", 0) / n,
    "by_reaction": {k: {"total": v[0], "hit_own": v[1], "hit_other": v[2],
                        "miss": v[3]} for k, v in by.items()},
    "results": results,
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n明细已存: {OUT_JSON}")

# 未命中的前 20 条，便于人工看
miss = [r for r in results if r["status"] == "miss"]
if miss:
    print()
    print("=" * 78)
    print(f"完全未命中的前 20 条（共 {len(miss)} 条）")
    print("=" * 78)
    for r in miss[:20]:
        row = rows[r["i"]]
        print(f"  [{r['reaction_name']}] id={r['template_id']}")
        print(f"      example: {row[2][:110]}")

enum.close()

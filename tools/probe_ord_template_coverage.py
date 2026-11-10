# -*- coding: utf-8 -*-
r"""C2 探针（2026-11-10）：语料里有，就能学会吗？

问题：第 135/136 轮把「稀有反应类召回只有 8–12%」归因于数据边界。但生产用的模板池只从
ORD 的 5 万条切片挖出来（41,619 条），而本地 `reports/ord_shards_full/` 里有 **286 片、
0.85 GB** 的 ORD 全量挖矿结果（1.77M 条）。所以先回答一个便宜的问题：

    这些稀有类型的模板，在「ORD 全量挖矿」里到底存不存在？

做法：
1. 复用 `bench_class_strata.build_sample()`（60,200 条 ORD 条件记录，带映射），
   按 `class_sig()` 分层，取「≤3 次」的稀有层，随机抽 120 条（与第 136 轮同一层）；
2. 对每条用 rdchiral `extract_from_reaction` 抽出它**自己**的模板（这是它在语料里
   「应该被挖出来」的样子）；
3. 流式扫 286 片 jsonl，看这些模板串是否出现在全量挖矿池里；
4. 输出每个模板的出现次数与「有/无」。

判读：
* 若多数模板在全量池里存在 → 稀有层缺的是**语料规模/挖矿覆盖**，不是架构；
* 若多数不存在 → 连全量 ORD 都没挖出来，说明模板式管线本身抓不住这些转化。

注意：这是「覆盖」统计，不是召回实验，因此不涉及把测试记录自己的模板套回自己。
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    sys.path.insert(0, str(_p))

import bench_class_strata as B  # noqa: E402

import rdchiral.template_extractor as te  # noqa: E402
from rdchiral.template_extractor import extract_from_reaction  # noqa: E402

te.VERBOSE = False

SHARDS = STAGE / "reports" / "ord_shards_full"
OUT = STAGE / "reports" / "ord_template_coverage_20261110.json"
N_SAMPLE = 120


def main() -> int:
    recs = B.build_sample()
    sigs = [B.class_sig(r["reactants"] + ">>" + r["product"]) for r in recs]
    cnt = Counter(s for s in sigs if s)
    rare = [(r, s) for r, s in zip(recs, sigs) if s and cnt[s] <= 3]
    print("records %d, sigs %d, rare %d" % (len(recs), len(cnt), len(rare)), flush=True)

    rng = random.Random(B.SEED)
    sample = rng.sample(rare, min(N_SAMPLE, len(rare)))

    rows = []
    for r, s in sample:
        tpl = None
        try:
            t = extract_from_reaction({"reactants": r["reactants"],
                                       "products": r["product"], "_id": "x"})
            tpl = (t or {}).get("reaction_smarts")
        except Exception:
            tpl = None
        rows.append({"reaction_id": r.get("reaction_id"), "sig": list(map(str, s)),
                     "template": tpl, "hits": 0})
    have = [r for r in rows if r["template"]]
    print("templates extracted %d/%d" % (len(have), len(rows)), flush=True)

    want = {r["template"] for r in have}
    count = Counter()
    files = sorted(SHARDS.glob("shard_*.jsonl"))
    for i, f in enumerate(files, 1):
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                j = line.find('"template": "')
                if j < 0:
                    continue
                start = j + 13
                end = line.find('", "rx"', start)
                if end < 0:
                    continue
                tpl = line[start:end]
                if tpl in want:
                    count[tpl] += 1
        if i % 40 == 0:
            print("  shard %d/%d, templates seen %d" % (i, len(files), len(count)),
                  flush=True)

    for r in rows:
        r["hits"] = count.get(r["template"], 0) if r["template"] else -1

    present = sum(1 for r in rows if r["hits"] > 0)
    absent = sum(1 for r in rows if r["template"] and r["hits"] == 0)
    no_tpl = sum(1 for r in rows if not r["template"])
    payload = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "n_records": len(recs),
        "n_rare": len(rare),
        "n_sample": len(rows),
        "templates_extracted": len(have),
        "present_in_full_pool": present,
        "absent_from_full_pool": absent,
        "no_template": no_tpl,
        "shards": len(files),
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("n_sample", "templates_extracted",
                                              "present_in_full_pool",
                                              "absent_from_full_pool",
                                              "no_template")}, ensure_ascii=False))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

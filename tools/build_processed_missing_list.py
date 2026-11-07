# -*- coding: utf-8 -*-
r"""从 A1 审计里抽出“炮制品库缺、但按铁律不能拆基原”的 token。

只读；不改 D:\TCMAI；输出补库候选清单。
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "sources"))
import formula as F  # noqa: E402
import processed as PR  # noqa: E402

AUDIT = STAGE / "data" / "formula_unmatched_audit.json"
OUTJ = STAGE / "data" / "processed_missing.json"
OUTM = STAGE / "reports" / "第七十五轮-炮制品库缺清单.md"


def main() -> int:
    d = json.loads(AUDIT.read_text(encoding="utf-8"))
    counts = Counter()
    examples = defaultdict(list)
    records = []
    for r in d.get("records") or []:
        hits = []
        for tok in r.get("bad") or []:
            clean = F.clean_token(tok)
            if clean and PR.is_processed(clean):
                counts[clean] += 1
                if len(examples[clean]) < 5:
                    examples[clean].append("%s#%d" % (r["name"], r["index"]))
                hits.append(tok)
        if hits:
            records.append({
                "name": r["name"], "index": r["index"],
                "chuchu": r.get("chuchu") or "",
                "peifang": r.get("peifang") or "",
                "processed_tokens": hits,
            })

    rows = [{"token": k, "count": v, "examples": examples[k]}
            for k, v in counts.most_common()]
    OUTJ.write_text(json.dumps({
        "n_processed_tokens": sum(counts.values()),
        "n_unique": len(counts),
        "n_records": len(records),
        "tokens": rows,
        "records": records,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    with OUTM.open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · 炮制品库缺清单（A1 衍生）\n\n")
        f.write("> 口径：A1 审计中 `processed.is_processed(clean_token)` 为真、"
                "但 HERB 库没有该炮制品的 token。\n")
        f.write("> **按用户铁律不拆基原**（制何首乌 ≠ 何首乌，姜半夏 ≠ 半夏）；"
                "本清单只是补库候选，不改 `D:\\TCMAI`。\n\n")
        f.write("## 总览\n\n")
        f.write("* 炮制品 token：**%d** 次 / **%d** 个唯一名；涉及 **%d** 条方剂记录。\n\n"
                % (sum(counts.values()), len(counts), len(records)))
        f.write("## 高频炮制品\n\n")
        f.write("| # | 炮制品 | 次数 | 示例记录 |\n|---:|---|---:|---|\n")
        for i, r in enumerate(rows[:50], 1):
            f.write("| %d | `%s` | %d | %s |\n"
                    % (i, r["token"], r["count"], "、".join(r["examples"])))
        f.write("\n## 补库建议\n\n")
        f.write("1. 这些名字应作为**独立炮制品**进入 HERB 库/药典炮制品名录，"
                "不能走 `_resolve_one` 的基原回退。\n")
        f.write("2. 需要补：herb_id / 基原 / 炮制方法 / 成分数据来源；"
                "没有成分数据时也只能标“库缺”，不能拿基原成分冒充。\n")
        f.write("3. 机器可读：`data/processed_missing.json`。\n")

    print("-> %s" % OUTJ)
    print("-> %s" % OUTM)
    print("  炮制品 %d 次 / %d 唯一 / %d 条记录"
          % (sum(counts.values()), len(counts), len(records)))
    print("  top:", rows[:10])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

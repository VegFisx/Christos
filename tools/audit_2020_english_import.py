# -*- coding: utf-8 -*-
r"""A3：2020 英文版药典导入批次专项（只读）。

`formula_db.json` 里 `chuchu == "Chinese Pharmacopoeia 2020 edition"` 的记录
是一批英文导入的药典条目；其中 55 条 category 被标成 `Ancient TCM prescriptions`，
与“药典”来源不一致。本脚本只统计、列清单、给显示建议，不改用户库。
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

STAGE = Path(__file__).resolve().parent.parent
SRC = Path(r"D:\TCMAI\data\formula_db.json")
OUTJ = STAGE / "data" / "formula_2020_english_audit.json"
OUTM = STAGE / "reports" / "第七十五轮-2020英文导入专项.md"


def main() -> int:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    rows = []
    for name, recs in d.items():
        for i, r in enumerate(recs):
            if "Chinese Pharmacopoeia 2020" in str(r.get("chuchu") or ""):
                rows.append({
                    "name": name, "index": i,
                    "category": r.get("category") or "",
                    "peifang": r.get("peifang") or "",
                    "gongxiao": r.get("gongxiao") or "",
                })
    cats = Counter(r["category"] for r in rows)
    ancient = [r for r in rows if r["category"] == "Ancient TCM prescriptions"]
    OUTJ.write_text(json.dumps({
        "n": len(rows), "categories": dict(cats), "rows": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    with OUTM.open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · 2020 英文版药典导入专项（A3）\n\n")
        f.write("> 对象：`D:\\TCMAI\\data\\formula_db.json` 里 "
                "`chuchu = Chinese Pharmacopoeia 2020 edition` 的记录。\n")
        f.write("> 只读统计；不改用户库。\n\n")
        f.write("## 总览\n\n")
        f.write("* 记录：**%d** 条\n" % len(rows))
        f.write("* category 分布：`%s`\n\n" % dict(cats))
        f.write("## 结论\n\n")
        f.write("1. 这 **%d** 条是**英文版药典数据集导入**，所以 source 字段是英文；"
                "不是 2025 中文官方 overlay。\n" % len(rows))
        f.write("2. 其中 **%d 条**被标成 `Ancient TCM prescriptions`，"
                "与药典来源不一致；这是源数据集的 category 标签问题。\n"
                % len(ancient))
        f.write("3. 它们仍可标为 `tier 0`（药典来源），但界面应显示 "
                "`药典 2020·英文导入（未核对）`，不能和 2025 中文法定版混为一谈。\n")
        f.write("4. 2025 中文 overlay（`chp_formulas.json`，1,526 条）才是"
                "带法定剂量的官方口径；2020 英文批没有剂量/官方 URL。\n\n")

        f.write("## 55 条 `Ancient TCM prescriptions` 清单\n\n")
        f.write("| # | 方名 | 组成（原文） |\n|---:|---|---|\n")
        for i, r in enumerate(ancient, 1):
            f.write("| %d | %s | `%s` |\n"
                    % (i, r["name"], r["peifang"].replace("|", "\\|")[:160]))

        f.write("\n## 处理建议\n\n")
        f.write("* 显示层：`source_display` 统一为 `中国药典 2020（英文导入）`；"
                "tier_label 为 `药典 2020·英文导入（未核对）`。\n")
        f.write("* 数据层：不改 `formula_db.json`；category 的 55 条误标作为"
                "源数据问题记录在案。\n")
        f.write("* 若论文/软著要引用这批，需另找 2020 中文药典原文核对；"
                "不能仅凭英文 source 字段声称“法定剂量”。\n")

    print("-> %s" % OUTJ)
    print("-> %s" % OUTM)
    print("  总数 %d ｜ category %s ｜ Ancient %d"
          % (len(rows), dict(cats), len(ancient)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

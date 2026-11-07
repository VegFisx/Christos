# -*- coding: utf-8 -*-
r"""A1：全库方剂组成未匹配 token 审计（只读）。

在 `split_ingredients` 括号感知 + 嵌套方名展开之后，扫描 12,071 条方剂记录，
把仍然对不上的 token 按“疑似炮制说明 / 方名引用 / 剂量单位 / 其他”归类，
给出高频 token 与涉及记录，供下一步决定是否继续修解析。

输出：
  data\formula_unmatched_audit.json
  reports\第七十五轮-方剂未匹配审计.md
"""
from __future__ import annotations

import json
import re
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

OUTJ = STAGE / "data" / "formula_unmatched_audit.json"
OUTM = STAGE / "reports" / "第七十五轮-方剂未匹配审计.md"

_PROC = ("炒", "炙", "煅", "蒸", "煮", "浸", "泡", "洗", "去皮", "去心", "研",
         "末", "粉", "块", "段", "丝", "晒", "烘", "焙", "酒", "醋", "盐",
         "蜜", "姜", "乳", "童便", "米泔", "土", "麸", "砂", "滑石", "朱砂",
         "雄黄", "硫黄", "煨", "淬", "炮", "熬", "捣", "杵", "切", "制",
         "清", "法", "焦",
         "各", "等分", "为末", "研末")
_DOSE = ("两", "钱", "分", "斤", "升", "合", "枚", "个", "条", "只",
         "克", "g", "ml", "毫升", "等分")
_EXCIPIENT = ("硬脂酸", "糊精", "甘油", "苯甲酸", "水杨酸", "山梨酯", "羟苯",
              "纤维素", "淀粉", "凡士林", "羊毛脂", "维生素", "氯化铵",
              "碳酸氢钠", "对乙酰氨基酚", "马来酸", "盐酸", "硫酸", "氢氧化",
              "氧化", "酯", "醇", "钠", "镁", "钙", "铝", "硅", "钛", "锌",
              "碱", "油")


def classify(tok: str, cleaned: str) -> str:
    if not cleaned:
        return "空"
    if cleaned in F._load() or cleaned in F._overlay():
        return "方名引用"
    if F._looks_like_formula_name(cleaned):
        return "方名引用"
    try:
        import processed as PR
        if PR.is_processed(cleaned):
            return "炮制品（库缺，不拆基原）"
    except Exception:
        pass
    if any(x in tok for x in _EXCIPIENT):
        return "疑似辅料/化学物质"
    if any(x in tok for x in _PROC):
        return "疑似炮制说明"
    if (any(x in tok for x in _DOSE)
            or re.fullmatch(r"[0-9一二三四五六七八九十百半两钱分斤升合枚个条只克gml毫升.\s]+",
                            tok.strip())):
        return "疑似剂量/单位"
    return "其他"


def main() -> int:
    d = F._load()
    token_counts = Counter()
    token_examples = defaultdict(list)
    rec_rows = []
    n_rec = 0
    n_bad_rec = 0
    for name, recs in d.items():
        for i, r in enumerate(recs):
            n_rec += 1
            herbs, bad = F.resolve_ingredients(str(r.get("peifang") or ""),
                                               _root_name=name)
            if not bad:
                continue
            n_bad_rec += 1
            for tok in bad:
                cleaned = F.clean_token(tok)
                key = cleaned or tok.strip()
                token_counts[key] += 1
                if len(token_examples[key]) < 3:
                    token_examples[key].append("%s#%d" % (name, i))
            rec_rows.append({
                "name": name, "index": i, "chuchu": r.get("chuchu") or "",
                "peifang": r.get("peifang") or "", "herbs": herbs,
                "bad": bad,
            })

    cats = Counter()
    for tok, count in token_counts.items():
        c = classify(tok, tok)
        cats[c] += count

    OUTJ.write_text(json.dumps({
        "n_records": n_rec,
        "n_records_with_bad": n_bad_rec,
        "n_bad_tokens": sum(token_counts.values()),
        "n_unique_bad_tokens": len(token_counts),
        "category_counts": dict(cats),
        "top_tokens": [{"token": k, "count": v,
                        "category": classify(k, k),
                        "examples": token_examples[k]}
                       for k, v in token_counts.most_common(100)],
        "records": rec_rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    with OUTM.open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · 方剂未匹配 token 审计（A1）\n\n")
        f.write("> 口径：括号感知切分 + 嵌套方名展开之后，`resolve_ingredients()` "
                "仍然对不上的 token。\n")
        f.write("> 只读审计；分类是启发式，`其他` 里可能仍有真药材/OCR 碎片。\n")
        f.write("> ★ **炮制品（库缺，不拆基原）**是按用户铁律：制何首乌/姜半夏等"
                "是独立炮制品，库里没有就报缺，不改写成基原。\n\n")
        f.write("## 总览\n\n")
        f.write("* 方剂记录：**%d** 条；仍有未匹配：**%d** 条（%.1f%%）\n"
                % (n_rec, n_bad_rec, 100.0 * n_bad_rec / max(1, n_rec)))
        f.write("* 未匹配 token：**%d** 次 / **%d** 个唯一 token\n\n"
                % (sum(token_counts.values()), len(token_counts)))
        f.write("### 启发式分类（按出现次数）\n\n")
        for k, v in cats.most_common():
            f.write("* %s：%d\n" % (k, v))
        f.write("\n## 高频 token（前 50）\n\n")
        f.write("| # | token | 次数 | 分类 | 示例记录 |\n")
        f.write("|---|---|---:|---|---|\n")
        for i, (tok, cnt) in enumerate(token_counts.most_common(50), 1):
            f.write("| %d | `%s` | %d | %s | %s |\n"
                    % (i, tok, cnt, classify(tok, tok),
                       "、".join(token_examples[tok])))
        f.write("\n## 涉及记录（前 30 条，按未匹配数降序）\n\n")
        rec_rows.sort(key=lambda x: -len(x["bad"]))
        for r in rec_rows[:30]:
            f.write("### %s #%d\n\n" % (r["name"], r["index"]))
            f.write("* 出处：%s\n" % (r["chuchu"] or "—"))
            f.write("* 原文：`%s`\n" % r["peifang"])
            f.write("* 已解析：%s\n" % ("、".join(r["herbs"]) or "—"))
            f.write("* 未匹配：%s\n\n"
                    % "、".join("`%s`(%s)" % (x, classify(x, F.clean_token(x)))
                               for x in r["bad"]))
        f.write("\n## 机器可读\n\n`data/formula_unmatched_audit.json`\n")

    print("-> %s" % OUTJ)
    print("-> %s" % OUTM)
    print("  记录 %d ｜ 有未匹配 %d ｜ token %d 次 / %d 唯一"
          % (n_rec, n_bad_rec, sum(token_counts.values()), len(token_counts)))
    print("  分类：", dict(cats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

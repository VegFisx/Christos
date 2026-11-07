# -*- coding: utf-8 -*-
r"""合并方案 a（模板签名）与方案 b（ORD 真实反应实测）→ 最终规则来源体检报告。

输入：
  data\rules_provenance_fp.json    方案 a
  data\rules_provenance_ord.json   方案 b（60k 等距抽样）
输出：
  reports\第七十五轮-规则来源体检-最终.md

只做**分组计数 + 逐条列示**，不打分、不排序；行序 = rules.json 原序。
"""
from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
FP = STAGE / "data" / "rules_provenance_fp.json"
ORD = STAGE / "data" / "rules_provenance_ord.json"
OUT = STAGE / "reports" / "第七十五轮-规则来源体检-最终.md"


def main() -> int:
    fp_rows = json.loads(FP.read_text(encoding="utf-8"))
    fp = {r["id"]: r for r in fp_rows}
    b = json.loads(ORD.read_text(encoding="utf-8"))
    rows = b["rows"]
    sample = b.get("sample", {})

    missing_fp = [r["id"] for r in rows if r["id"] not in fp]
    missing_ord = [i for i in fp if i not in {r["id"] for r in rows}]
    if missing_fp or missing_ord:
        print("   [warn] 两份结果规则集合不一致：a 缺 %s；b 缺 %s"
              % (missing_fp, missing_ord))

    # 交叉表：论文档位 × 结构证据 × ORD 是否至少一次 product_match
    cross = Counter()
    for r in rows:
        a = fp.get(r["id"], {})
        cross[(r.get("paper_tier", "?"), a.get("evidence", "?"),
               "有" if r.get("product_match", 0) > 0 else "无")] += 1

    by_tier = Counter(r.get("paper_tier", "?") for r in rows)
    n_fired = sum(1 for r in rows if r.get("fired", 0) > 0)
    n_match = sum(1 for r in rows if r.get("product_match", 0) > 0)
    n_none = len(rows) - n_match

    with OUT.open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · 规则来源体检（最终）\n\n")
        f.write("> 目的：回答「`rules/rules.json` 里 64 条规则的 SMARTS 是从哪来的、"
                "有没有 ORD 真实反应先例」。\n")
        f.write("> **本报告不打分、不排序**；行序 = `rules.json` 原顺序。"
                "「无 ORD 产物命中」只表示**这批抽样里没找到**，不等于规则错。\n\n")

        f.write("## 一、口径\n\n")
        f.write("* 规则库：`rules/rules.json` 共 **%d** 条。\n" % len(rows))
        f.write("* 论文 TableS1：逐条比对后分三档 —— "
                "论文原样 / 论文修正 / 自写新增。\n")
        f.write("* **方案 a（结构签名）**：把规则与 `reports/mined_forward_templates_full_lf.jsonl`"
                "（282,704 条 ORD 挖掘模板）抽成「映射原子元素/电荷/度 + 映射键」签名，"
                "分「同款 / 同反应中心 / 无」。\n")
        f.write("* **方案 b（ORD 实测）**：对 `data/ord_reaction_index.jsonl`"
                "（%s 行）按步长 %s 等距抽样 **%s** 条，把每条规则套到真实反应物上；"
                "生成产物去映射号/显式 H/立体并拆片段，和该记录真实产物比对，"
                "记 `fired` 与 `product_match`。\n"
                % (f"{sample.get('total_lines', 0):,}", sample.get("stride", "?"),
                   f"{sample.get('scanned_records', 0):,}"))
        f.write("* 反应物/产物解析失败：%s / %s 次（脚本逐条累计，不静默跳过）。\n\n"
                % (b.get("parse_fail", 0), b.get("product_parse_fail", 0)))

        f.write("## 二、总览（先看数字）\n\n")
        f.write("### 论文档位\n\n")
        for k in ("论文原样", "论文修正", "自写新增"):
            if k in by_tier:
                f.write("* **%s**：%d 条\n" % (k, by_tier[k]))
        f.write("\n### 方案 a：结构签名\n\n")
        ac = Counter(r.get("evidence", "?") for r in fp_rows)
        for k in ("同款", "同反应中心", "无"):
            f.write("* **%s**：%d 条\n" % (k, ac.get(k, 0)))
        f.write("\n### 方案 b：ORD 真实反应实测（%s 条抽样）\n\n"
                % f"{sample.get('scanned_records', 0):,}")
        f.write("* 至少 `fired` 一次：**%d / %d** 条\n" % (n_fired, len(rows)))
        f.write("* 至少 `product_match` 一次：**%d / %d** 条\n" % (n_match, len(rows)))
        f.write("* 抽样内没有 `product_match`：**%d** 条（列入下方“未命中清单”，"
                "只代表样本内没有同产物记录）\n\n" % n_none)

        f.write("### 交叉表（论文档位 × 结构证据 × ORD 是否命中）\n\n")
        f.write("| 论文档位 | 结构证据 | ORD 有命中 | ORD 无命中 |\n")
        f.write("|---|---|---:|---:|\n")
        for tier in ("论文原样", "论文修正", "自写新增"):
            for ev in ("同款", "同反应中心", "无"):
                y = cross.get((tier, ev, "有"), 0)
                n = cross.get((tier, ev, "无"), 0)
                if y or n:
                    f.write("| %s | %s | %d | %d |\n" % (tier, ev, y, n))
        f.write("\n")

        f.write("## 三、逐条结果（rules.json 原顺序）\n\n")
        f.write("| # | 规则 | 类别 | 状态 | 论文档位 | 结构证据 | 结构最高 support | "
                "ORD fired | ORD product_match | 首个命中 rid |\n")
        f.write("|---|---|---|---|---|---|---:|---:|---:|---|\n")
        for i, r in enumerate(rows, 1):
            a = fp.get(r["id"], {})
            ex = (r.get("examples_match") or [{}])[0]
            rid = ex.get("rid") or "—"
            sup = a.get("max_support")
            f.write("| %d | `%s` %s | %s | %s | %s | %s | %s | %d | %d | %s |\n"
                    % (i, r["id"], r.get("name", ""), r.get("category", ""),
                       r.get("status", ""), r.get("paper_tier", "?"),
                       a.get("evidence", "?"),
                       sup if sup is not None else "—",
                       r.get("fired", 0), r.get("product_match", 0), rid))

        f.write("\n## 四、ORD 有命中的规则：首个样例\n\n")
        f.write("> 只列每条规则的**第一个**命中样例；完整样例见 "
                "`reports/第七十五轮-规则来源体检（ORD实测）.md`。\n\n")
        any_match = False
        for r in rows:
            exs = r.get("examples_match") or []
            if not exs:
                continue
            any_match = True
            ex = exs[0]
            f.write("### `%s` %s\n\n" % (r["id"], r.get("name", "")))
            f.write("* 记录：`%s`\n" % ex.get("rid", ""))
            f.write("* 反应物：`%s`\n" % " + ".join(ex.get("reactants") or []))
            f.write("* 规则生成且与记录一致：`%s`\n"
                    % " ; ".join(ex.get("generated") or []))
            f.write("* 记录产物：`%s`\n\n"
                    % " ; ".join(ex.get("actual") or []))
        if not any_match:
            f.write("（本次抽样没有任何规则命中。）\n\n")

        f.write("## 五、抽样内没有 ORD 产物命中的规则（按类别分组，不排序）\n\n")
        f.write("> 这些规则**不是判错**。常见原因：该反应类型不在 ORD 抽样里、"
                "底物取代基不匹配、规则要求多步/共试剂、记录方向相反，"
                "或规则本身写错。需要外部文献/实验进一步区分。\n\n")
        f.write("> 零命中规则的逐条离线判读（修复后）见 "
                "`reports/第七十五轮-零命中规则-离线核验（修复后）.md`；"
                "修复前 14 条版本保留在 `reports/第七十五轮-14条零命中规则-离线核验.md`；"
                "样例记录的真实条件见 `reports/第七十五轮-规则条件样例.md`；"
                "规则级条件窗口见 `reports/第七十五轮-规则条件窗口.md`。\n\n")
        f.write("> B 外部文献核验（2026-10-17）已完成：6 条“抽样内无该反应”的规则"
                "**6/6 找到至少一条直接文献支持**；"
                "详见 `reports/第七十五轮-规则外部文献核验.md`。\n\n")
        groups: "OrderedDict[str, list]" = OrderedDict()
        for r in rows:
            if r.get("product_match", 0) == 0:
                groups.setdefault(r.get("category", "?"), []).append(r)
        for cat, rs in groups.items():
            f.write("### %s（%d 条）\n\n" % (cat, len(rs)))
            for r in rs:
                f.write("* `%s` %s（%s；fired=%d）\n"
                        % (r["id"], r.get("name", ""), r.get("paper_tier", "?"),
                           r.get("fired", 0)))
            f.write("\n")

        f.write("## 六、局限（必须和数字一起读）\n\n")
        f.write("1. **方案 a 的签名是粗粒度**：只比映射原子的元素/电荷/重原子度"
                "与映射键，忽略 H 数、立体、邻域取代基；「同款」可能是假阳性，"
                "「同反应中心」只说明反应物侧骨架相同。\n")
        f.write("2. **方案 b 是前向试跑，不是逆合成审计**：ORD 记录未必是同一反应类型；"
                "`fired` 只说明底物里存在可匹配子结构，`product_match` 才说明"
                "该记录里出现了规则生成的那个分子图。\n")
        f.write("3. **共试剂/水多为隐含**：水解等规则没有把 H2O 写成反应物，"
                "本审计只把规则套到记录的反应物列；这符合规则当前写法，"
                "但不能据此判断真实条件下的水解可行性。\n")
        f.write("4. **规范化忽略立体与显式 H**：`product_match` 是分子图相同，"
                "不是同一立体异构体、同一条件或同一机理。\n")
        f.write("5. **抽样不是全库**：%s 条等距样本不能证明“全库没有”；"
                "零命中应写成“本抽样未命中”。\n"
                % f"{sample.get('scanned_records', 0):,}")
        f.write("6. **本报告不解决条件可信度**：它只回答“有没有 ORD 记录里出现过"
                "这个产物”，不回答“需要什么试剂/温度/催化”。后者要继续用 ORD "
                "条件字段或文献核验。\n\n")

        f.write("## 七、结论与下一步\n\n")
        f.write("* 现在可以把 64 条规则明确分成：**论文原样 / 论文修正 / 自写新增**"
                "三档，不再把“自写”混成“论文来源”。\n")
        f.write("* 方案 a 给出结构上的“像不像”，方案 b 给出 ORD 真实记录里的"
                "“有没有跑出同产物”；两者都命中的规则证据最强，"
                "只有其一的规则需要按上面局限逐条解释。\n")
        f.write("* 对**自写新增且 ORD 零命中**的规则，论文/软著里只能写成"
                "“本工作新增规则，待外部文献或实验核验”，不能写成“来自论文/ORD”。\n")
        f.write("* 下一步（不需要再问 AI）：优先查这些规则对应的权威来源"
                "（论文 TableS1 之外的原始文献、ORD 记录的条件字段、SmartReact/ORD 模板）；"
                "查不到就保留“自写、待核验”标注。\n\n")

        f.write("## 八、复现\n\n")
        f.write("```powershell\n")
        f.write("cd D:\\ProgramData\\DSHNS\\chemreact-staging\n")
        f.write("python -u tools\\audit_rules_fp.py\n")
        f.write("python -u tools\\audit_rules_against_ord_reactions.py --limit 60000\n")
        f.write("python -u tools\\build_rules_provenance_report.py\n")
        f.write("```\n\n")
        f.write("机器可读证据：`data/rules_provenance_fp.json`、"
                "`data/rules_provenance_ord.json`。\n")

    print("-> %s" % OUT)
    print("  规则 %d ｜ 论文档位 %s ｜ 方案a %s ｜ ORD fired %d / match %d"
          % (len(rows), dict(by_tier), dict(ac), n_fired, n_match))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

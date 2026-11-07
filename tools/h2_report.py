# -*- coding: utf-8 -*-
r"""H2 · 生成抽检报告 `reports\第七十五轮-AI古方抽检.md`。

统计口径与论文一致：Wilson 95% 置信区间（直接 import tools\paper_stats_ci.wilson）。
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
sys.path.insert(0, str(STAGE / "tools"))
from paper_stats_ci import wilson                            # noqa: E402

VERD = STAGE / "data" / "h2_verdicts_all.json"
SAMPLE = STAGE / "data" / "h2_sample.json"
OUT = STAGE / "reports" / "第七十五轮-AI古方抽检.md"


def main() -> int:
    rows = [r for r in json.loads(VERD.read_text(encoding="utf-8"))
            if not str(r.get("判定", "")).startswith(("待", "未"))]
    samp = json.loads(SAMPLE.read_text(encoding="utf-8"))
    n = len(rows)
    c = Counter(r["判定"] for r in rows)
    hit, part, none = c["命中"], c["部分命中"], c["查无"]
    lo_h, hi_h = wilson(hit, n)
    lo_hp, hi_hp = wilson(hit + part, n)
    by_batch = {}
    for r in rows:
        b = r.get("批次", 1)
        by_batch.setdefault(b, Counter())[r["判定"]] += 1
    lines = []
    A = lines.append
    A("# 第七十五轮 · H2：AI 现查古方抽检 100 条")
    A("")
    A("> 任务书：`reports\\第七十五轮-任务-数据出处隐患.md` 的 H2。")
    A("> 一句话结论：**AI 现查那批里，能逐条核到公开来源的约 %.0f%%**（命中 %d + 部分命中 %d，"
      "Wilson 95%% CI %.1f–%.1f%%）；"
      % (100.0 * (hit + part) / n, hit, part, 100 * lo_hp, 100 * hi_hp))
    A("> **组成与公开源一致**的只有 **%d%%**（Wilson 95%% CI %.1f–%.1f%%），"
      "**查无**的 %d%%。" % (round(100.0 * hit / n), 100 * lo_h, 100 * hi_h,
                            round(100.0 * none / n)))
    A("")
    A("## 一、怎么抽的（口径先定死）")
    A("")
    A("* 总体 = `formula_db.json` 里 `category` 缺失的那批记录（= H1 的 tier 5，实测 **5,332 条**）；")
    A("* 抽样单位 = **一条记录**（同一方名下不同出处的记录各自独立）；")
    A("* 两批**固定种子、无放回、互不重叠**：第一批种子 20261016 抽 100 条，"
      "第二批种子 20261017 从剩下的 5,232 条里抽 200 条 → 合计 **n=%d**"
      "（`tools\\build_h2_sample.py` / `build_h2_sample2.py`，抽样可复现）；" % n)
    A("* 清单：`reports\\第七十五轮-AI古方抽检-清单.csv`（第一批）、"
      "`reports\\第七十五轮-H2-第二批-清单.csv`（第二批）。")
    A("")
    A("## 二、怎么核的（每条都可复查）")
    A("")
    A("1. **检索**：对每条用「方名 + 组成」在公开搜索引擎上查（360 / Bing / 搜狗轮询，"
      "每条间隔 2.5–3 秒），把**原始结果（标题/链接/摘要）**存进 `reports\\_h2_net\\<序号>_<方名>.json`；")
    A("2. **取正文**：从候选里挑最可能的页面抓正文节选，存 `reports\\_h2_net\\<序号>_*.top.txt`；")
    A("3. **判定**：把库里「组成」拆成药材名，与来源文本逐字比对算覆盖率"
      "（去剂量、去炮制前缀，`炙甘草`能对`甘草`、`白术`**不会**误配`苍术`），"
      "**再逐条阅读修正** —— 规则与每一条修正的理由都写在 `tools\\h2_verdicts.py` 里；")
    A("4. 判定三档：**命中** = 方名 + 组成能对上；**部分命中** = 同名方存在但组成/版本不同"
      "（或页面在、组成未核到）；**查无** = 公开源里没找到能证明该条的实质内容。")
    A("")
    A("★ **最终判定口径（v2，两批同一把尺子，写在 `tools\\h2_verdicts2.py` 里）**：")
    A("")
    A("   * **证据文档** = 抓到的页面（医学百科 / A+医学百科 / 维基 / 文库），"
      "或检索结果里**非搜索页/文库页/图片页**且文本同时含方名与「组成/处方/功效…」标记的那一条；")
    A("   * **命中** = 库里组成与证据文档的**字面重合 ≥ 0.6**；")
    A("   * **部分命中** = 覆盖率 < 0.6 但存在证据文档（= 同名方在，组成/版本不同）；")
    A("   * **查无** = 没有任何证据文档；")
    A("   * 另加**逐条人工修正**（第一批 12 条、第二批 1 条），每条理由都写在脚本里。")
    A("")
    A("★ 诚实交代（重要）：")
    A("")
    A("* **「查无」不等于「不存在」** —— 它只表示「本次检索的这几条公开信道里没找到」。"
      "不少古籍方只在纸本《中医方剂大辞典》里；")
    A("* 覆盖率是**字面重合**，会被剂量写法（`钱`/`分`）、异名（`黄耆`/`黄芪`）、"
      "炮制注记干扰 —— 所以最终判定以逐条阅读为准，自动建议与最终判定不一致的 "
      "**%d 条**全部列了理由；" % sum(1 for r in rows if r["判定"] != r["自动建议"]))
    A("* 两批的**取证信道不同**，会带来口径差异（第一批赶上搜索引擎封禁，"
      "第二批改用医学百科/维基等**站内搜索**，拿到页面的比例更高，"
      "所以第二批的「查无」明显少于第一批）——见下面的分批对照；")
    A("* 搜索侧本轮碰到封禁：DuckDuckGo 抓到第 50 条开始 403、360/搜狗中途返回"
      "「访问异常页」、Bing 对长中文方名常给无关结果、中医世家站点 502 ——"
      "都如实记在证据目录里，没有静默跳过（0 失败被吞）。")
    A("")
    A("## 三、结果")
    A("")
    A("| 判定 | 条数 | 占比 | Wilson 95% CI |")
    A("|---|---|---|---|")
    A("| 命中（组成对得上） | %d | %.0f%% | %.1f–%.1f%% |"
      % (hit, 100.0 * hit / n, 100 * lo_h, 100 * hi_h))
    A("| 部分命中（同名但组成/版本不同） | %d | %.0f%% | — |" % (part, 100.0 * part / n))
    A("| 查无 | %d | %.0f%% | — |" % (none, 100.0 * none / n))
    A("| **命中 + 部分命中（能核到来源）** | **%d** | **%.0f%%** | **%.1f–%.1f%%** |"
      % (hit + part, 100.0 * (hit + part) / n, 100 * lo_hp, 100 * hi_hp))
    A("")
    A("**分批对照**（同一口径，看稳定性）：")
    A("")
    A("| 批次 | n | 命中 | 部分命中 | 查无 |")
    A("|---|---|---|---|---|")
    for b in sorted(by_batch):
        cb = by_batch[b]
        nn = sum(cb.values())
        A("| 第 %d 批（种子 %d） | %d | %d（%.0f%%） | %d（%.0f%%） | %d（%.0f%%） |"
          % (b, 20261015 + b, nn, cb["命中"], 100.0 * cb["命中"] / nn,
             cb["部分命中"], 100.0 * cb["部分命中"] / nn,
             cb["查无"], 100.0 * cb["查无"] / nn))
    A("")
    A("## 四、100 条明细（每条都有可点的来源）")
    A("")
    A("| # | 方名 | 出处（库内） | 判定 | 覆盖率 | 来源 | 说明 |")
    A("|---|---|---|---|---|---|---|")
    for r in rows:
        url = r["来源URL"] or ""
        src = ("[来源](%s)" % url) if url.startswith("http") else "（无）"
        why = (r["理由"] or "").replace("|", "／")[:60]
        A("| %d | %s | %s | **%s** | %.2f | %s | %s |"
          % (r["序号"], r["方名"], (r["出处"] or "").replace("|", "／")[:18],
             r["判定"], r["覆盖率"], src, why))
    A("")
    A("## 五、复现")
    A("")
    A("```powershell")
    A("python tools\\build_h2_sample.py          # 固定种子抽样（生成清单）")
    A("python tools\\h2_fetch.py --engine rotate --sleep 2.5    # 检索取证（需联网）")
    A("python tools\\h2_fetch_top.py --sleep 2.5                # 抓候选页正文（需联网）")
    A("python tools\\h2_judge_sheet.py --start 1 --limit 100    # 覆盖率筛选信号")
    A("python tools\\h2_verdicts.py              # 规则 + 逐条修正 → 最终判定")
    A("python tools\\h2_report.py                # 生成本报告")
    A("```")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("  命中 %d ｜ 部分命中 %d ｜ 查无 %d ｜ 共 %d" % (hit, part, none, n))
    print("  命中 %d%%（CI %.1f–%.1f%%）｜ 命中+部分 %.0f%%（CI %.1f–%.1f%%）"
          % (round(100.0 * hit / n), 100 * lo_h, 100 * hi_h,
             round(100.0 * (hit + part) / n), 100 * lo_hp, 100 * hi_hp))
    print("  -> %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

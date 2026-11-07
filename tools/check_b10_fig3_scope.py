# -*- coding: utf-8 -*-
r"""核查 fig3 的 94.7% 与 B10 的 79.81% 是否为同一口径。

输入：
  reports\paper\results\coverage_summary.json                         （主线，fig3 原口径）
  repro-20261016\reports\paper\results\coverage_summary__lib_uspto50k_excl_s1.json （B10）
输出：
  reports\第七十五轮-B10-fig3口径核查.md
  reports\paper\figures_b10_check\fig3_coverage_topk_b10.(png|pdf)   （候选图，不覆盖原图）

不打分、不排序；只比较 n_targets / lib / lib_templates / any_hit / top-k。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
MAIN = STAGE / "reports" / "paper" / "results" / "coverage_summary.json"
B10 = (STAGE / "repro-20261016" / "reports" / "paper" / "results"
       / "coverage_summary__lib_uspto50k_excl_s1.json")
OUT_MD = STAGE / "reports" / "第七十五轮-B10-fig3口径核查.md"
FIG_DIR = STAGE / "reports" / "paper" / "figures_b10_check"


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def row(name: str, d: dict) -> str:
    top = d.get("topk") or {}
    def pct(k):
        return "%.2f%%" % (100.0 * float(top[k]["rate"])) if k in top else "—"
    return ("| %s | %s | %s | %s | %.2f%% | %s | %s | %s | %s | %s |"
            % (name, d.get("n_targets"), d.get("lib"), d.get("lib_templates"),
               100.0 * float(d.get("any_hit_rate", 0)),
               pct("top1"), pct("top3"), pct("top5"), pct("top10"), pct("top50")))


def make_figure(b10: dict) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as ex:  # noqa: BLE001
        return "跳过候选图：%s" % ex
    ks = ["top1", "top3", "top5", "top10", "top50"]
    vals = [100.0 * float(b10["any_hit_rate"])] + [
        100.0 * float(b10["topk"][k]["rate"]) for k in ks]
    labels = ["any"] + ks
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(4.6, 3.4))
    ax.bar(labels, vals, color=["#333"] + ["#4c78a8"] * len(ks))
    for i, v in enumerate(vals):
        ax.text(i, v + 0.5, "%.1f" % v, ha="center", fontsize=8)
    ax.set_ylim(0, 105)
    ax.set_ylabel("reactant-set match rate (%)")
    ax.set_title("USPTO-50k coverage (B10: 50,016 targets, 3,065 templates)",
                 fontsize=9)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(FIG_DIR / ("fig3_coverage_topk_b10." + ext), dpi=200,
                    bbox_inches="tight")
    plt.close(fig)
    return "已写候选图：%s" % (FIG_DIR / "fig3_coverage_topk_b10.png")


def main() -> int:
    a = load(MAIN)
    b = load(B10)
    note = make_figure(b)

    with OUT_MD.open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · B10 fig3 口径核查\n\n")
        f.write("> 目的：解释 `fig3_coverage_topk` 的 94.7% 与 B10 复现的 79.81% "
                "为何不同，确认论文图应该用哪一套。\n")
        f.write("> 只读比较，不改论文图；候选图另存到 "
                "`reports\\paper\\figures_b10_check\\`。\n\n")
        f.write("## 一、两套结果的关键字段\n\n")
        f.write("| 口径 | n_targets | 库 | 库模板数 | any-hit | top1 | top3 | top5 | top10 | top50 |\n")
        f.write("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|\n")
        f.write(row("主线 `coverage_summary.json`", a) + "\n")
        f.write(row("B10 `coverage_summary__lib_uspto50k_excl_s1.json`", b) + "\n")
        f.write("\n")
        f.write("## 二、结论\n\n")
        f.write("* 主线 any-hit **94.74%** 的分母是 **5,002 个目标**，"
                "库是 `lib_uspto50k_excl_v2.jsonl`（**79,184** 条模板）；\n")
        f.write("* B10 any-hit **79.81%** 的分母是 **50,016 个目标**，"
                "库是 `lib_uspto50k_excl.jsonl`（**3,065** 条模板）。\n")
        f.write("* 两者既不是同一目标集，也不是同一模板库；"
                "**94.7% 不能当作“USPTO-50k 全量 + 泄漏剔除库”的覆盖率**。"
                "论文 fig3 若标注 USPTO-50k，应使用 B10 这套 50,016 目标 / 3,065 模板的 79.81%。\n")
        f.write("* 这不是脚本算错，而是 `paper_make_figures.py::fig3()` "
                "默认读主线 `coverage_summary.json` 造成的口径错配。\n\n")
        f.write("## 三、建议\n\n")
        f.write("1. 论文定稿前把 fig3 的数据源改成 B10 的 "
                "`coverage_summary__lib_uspto50k_excl_s1.json`（或把 B10 结果复制成 "
                "`coverage_summary.json` 的 canonical 名称）；\n")
        f.write("2. 候选图已生成为 `figures_b10_check/fig3_coverage_topk_b10.png`，"
                "可与原图并排核对；**没有覆盖原 fig3**；\n")
        f.write("3. 若论文正文要保留 94.7%，必须把图注/正文改成"
                "“5,002 目标 + v2 库”，不能写 USPTO-50k 全量。\n\n")
        f.write("## 四、复现\n\n")
        f.write("```powershell\n")
        f.write("cd D:\\ProgramData\\DSHNS\\chemreact-staging\n")
        f.write("& D:\\TCMAI\\venv\\Scripts\\python.exe -u tools\\check_b10_fig3_scope.py\n")
        f.write("```\n\n")
        f.write("%s\n" % note)

    print("-> %s" % OUT_MD)
    print(note)
    print("MAIN n_targets=%s lib=%s templates=%s any_hit=%.2f%%"
          % (a.get("n_targets"), a.get("lib"), a.get("lib_templates"),
             100 * float(a.get("any_hit_rate", 0))))
    print("B10  n_targets=%s lib=%s templates=%s any_hit=%.2f%%"
          % (b.get("n_targets"), b.get("lib"), b.get("lib_templates"),
             100 * float(b.get("any_hit_rate", 0))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

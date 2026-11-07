# -*- coding: utf-8 -*-
"""Generate bilingual figures for the Christos system paper.

All quantitative values come from the frozen result tables listed in the
figure captions. The diagrams are conceptual layouts, not experimental data.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

STAGE = Path(__file__).resolve().parent.parent
OUT = STAGE / "reports" / "paper" / "figures-system-20261020"
FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_CN = font_manager.FontProperties(fname=str(FONT_PATH)) if FONT_PATH.exists() else None

COLORS = {
    "ink": "#183746",
    "muted": "#5c707a",
    "line": "#9bb8c4",
    "blue": "#dceff5",
    "blue2": "#c3e3ed",
    "green": "#e1f0e8",
    "amber": "#f7ecd0",
    "rose": "#f4e1e3",
    "white": "#ffffff",
}


def fp(lang: str):
    return FONT_CN if lang == "zh" else None


def txt(ax, x, y, s, lang, size=10, weight="normal", color=None, ha="center", va="center", wrap=None):
    if wrap:
        s = "\n".join(textwrap.wrap(str(s), wrap))
    ax.text(x, y, s, ha=ha, va=va, fontsize=size, fontweight=weight,
            color=color or COLORS["ink"], fontproperties=fp(lang), linespacing=1.35)


def box(ax, x, y, w, h, s, lang, fc="white", ec=None, size=10, weight="normal", wrap=None):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.35,rounding_size=1.1",
        linewidth=1.1, edgecolor=ec or COLORS["line"], facecolor=fc,
    ))
    txt(ax, x + w / 2, y + h / 2, s, lang, size=size, weight=weight, wrap=wrap)


def arrow(ax, x1, y1, x2, y2, color=None, lw=1.5):
    ax.add_patch(FancyArrowPatch(
        (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=12,
        linewidth=lw, color=color or COLORS["muted"], shrinkA=2, shrinkB=2,
    ))


def language_labels(lang: str):
    if lang == "zh":
        return {
            "arch_title": "Christos 系统架构",
            "input": "输入\n药材 / 物种 / 方剂 / SMILES",
            "resolver": "显式解析器\n名称 · 别名 · 版本",
            "herb": "药材库\n只读 SQLite",
            "coconut": "COCONUT\n物种级天然产物",
            "formula": "方剂库\n版本与出处",
            "ord": "ORD / USPTO\n公开反应模板",
            "engine": "反应引擎\n正向枚举 + 逆合成",
            "condition_layer": "条件层\n类 profile + 模板窗口",
            "ledger": "出处台账\n产物 · 规则 · 来源 · 证据",
            "report": "报告层\nCSV / TSV / HTML",
            "ui": "CLI / 本地浏览器界面",
            "resolution_title": "输入解析路径与未解析 token",
            "resolution_in": "用户输入",
            "resolution_herb": "中文药材名\n→ HERB 记录",
            "resolution_species": "拉丁双名\n→ COCONUT 物种",
            "resolution_formula": "方剂名\n→ 全部版本",
            "resolution_smiles": "用户 SMILES\n→ 结构记录",
            "resolution_unresolved": "未解析 token\n原样报告，不强行映射",
            "forward_title": "正向枚举的出处链",
            "input_card": "输入\nGlycyrrhiza uralensis",
            "source_card": "来源化合物\nCNP_CNP0003006.1\nCOCONUT",
            "rule_card": "规则 / 证据\nesterification\nactivation = 1.0",
            "product_card": "候选产物\nC64H84O23\n方向可疑",
            "provenance": "出处路径：输入 → 来源化合物 → 规则 → 产物；每个字段都进入台账和 HTML 报告。",
            "retro_title": "逆合成示例：来源、前体与可用性",
            "target": "目标\nO=C(NCCc1ccc(O)cc1)\nc1ccccc1O",
            "amide": "规则\namide_coupling",
            "prec1": "前体 1\nNCCc1ccc(O)cc1\nCOCONUT",
            "prec2": "前体 2\nO=C(O)c1ccccc1O\nCOCONUT",
            "retro_note": "正向验证通过 · 终止集合命中 · 路线仍须实验验证",
            "bench_title": "冻结基准上的系统结果",
            "forward_baseline": "正向\n基线",
            "forward_selected": "正向\n选定配置",
            "reverse": "逆向\nany-hit",
            "multi2": "多步\n深度 ≤2",
            "multi3": "多步\n深度 ≤3",
            "condition": "条件模板\n有匹配",
            "bench_note": "数值：58.73 / 91.69 / 94.74 / 47.67 / 72.33；均为冻结口径，见结果表。",
        }
    return {
        "arch_title": "Christos system architecture",
        "input": "Input\nherb / species / formula / SMILES",
        "resolver": "Explicit resolver\nname · alias · version",
        "herb": "HERB database\nread-only SQLite",
        "coconut": "COCONUT\nspecies-level natural products",
        "formula": "Formula records\nversions and provenance",
        "ord": "ORD / USPTO\npublic reaction templates",
        "engine": "Reaction engine\nforward enumeration + retro",
        "condition_layer": "Condition layer\nclass profiles + template windows",
        "ledger": "Provenance ledger\nproduct · rule · source · evidence",
        "report": "Report layer\nCSV / TSV / HTML",
        "ui": "CLI / local browser UI",
        "resolution_title": "Input resolution and unresolved tokens",
        "resolution_in": "User input",
        "resolution_herb": "Chinese herb\n→ HERB record",
        "resolution_species": "Latin binomial\n→ COCONUT species",
        "resolution_formula": "Formula name\n→ all versions",
        "resolution_smiles": "User SMILES\n→ structure record",
        "resolution_unresolved": "Unresolved token\nreported, never forced",
        "forward_title": "Provenance chain of one forward candidate",
        "input_card": "Input\nGlycyrrhiza uralensis",
        "source_card": "Source compound\nCNP_CNP0003006.1\nCOCONUT",
        "rule_card": "Rule / evidence\nesterification\nactivation = 1.0",
        "product_card": "Candidate product\nC64H84O23\nsuspect direction",
        "provenance": "Provenance path: input → source compound → rule → product; every field is written to the ledger and HTML report.",
        "retro_title": "Retrosynthesis example: source, precursors, availability",
        "target": "Target\nO=C(NCCc1ccc(O)cc1)\nc1ccccc1O",
        "amide": "Rule\namide_coupling",
        "prec1": "Precursor 1\nNCCc1ccc(O)cc1\nCOCONUT",
        "prec2": "Precursor 2\nO=C(O)c1ccccc1O\nCOCONUT",
        "retro_note": "Forward validation passed · termination-set hit · laboratory validation still required",
        "bench_title": "System results on the frozen benchmark",
        "forward_baseline": "Forward\nbaseline",
        "forward_selected": "Forward\nselected",
        "reverse": "Reverse\nany-hit",
        "multi2": "Multi-step\ndepth ≤2",
        "multi3": "Multi-step\ndepth ≤3",
        "condition": "Condition\ntemplates matched",
        "bench_note": "Values: 58.73 / 91.69 / 94.74 / 47.67 / 72.33; all frozen settings, see the result table.",
    }


def setup(figsize=(12, 7)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    return fig, ax


def architecture(lang: str, path: Path):
    L = language_labels(lang)
    fig, ax = setup((12, 7.4))
    txt(ax, 50, 95, L["arch_title"], lang, 17, "bold")
    box(ax, 3, 76, 20, 10, L["input"], lang, COLORS["blue"], size=9, wrap=24)
    box(ax, 29, 76, 19, 10, L["resolver"], lang, COLORS["blue2"], size=9, wrap=22)
    arrow(ax, 23, 81, 29, 81)
    source_boxes = [
        (3, 56, L["herb"], "green"),
        (28, 56, L["coconut"], "blue"),
        (53, 56, L["formula"], "amber"),
        (78, 56, L["ord"], "rose"),
    ]
    for x, y, s, c in source_boxes:
        box(ax, x, y, 19, 12, s, lang, COLORS[c], size=8.2, wrap=22)
        arrow(ax, 38.5, 76, x + 9.5, 68)
    box(ax, 23, 35, 30, 11, L["engine"], lang, COLORS["blue2"], size=10, wrap=30)
    box(ax, 59, 35, 29, 11, L["condition_layer"], lang, COLORS["amber"], size=9, wrap=32)
    arrow(ax, 12.5, 56, 30, 46)
    arrow(ax, 38, 56, 38, 46)
    arrow(ax, 62.5, 56, 48, 46)
    arrow(ax, 87.5, 56, 73, 46)
    box(ax, 19, 14, 31, 10, L["ledger"], lang, COLORS["green"], size=9, wrap=34)
    box(ax, 57, 14, 25, 10, L["report"], lang, COLORS["blue"], size=9, wrap=28)
    arrow(ax, 38, 35, 34, 24)
    arrow(ax, 53, 19, 57, 19)
    txt(ax, 50, 5, L["ui"], lang, 9, "normal", COLORS["muted"])
    arrow(ax, 69.5, 14, 69.5, 9.5)
    fig.savefig(path.with_suffix(".png"), dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def resolution(lang: str, path: Path):
    L = language_labels(lang)
    fig, ax = setup((12, 6.8))
    txt(ax, 50, 95, L["resolution_title"], lang, 17, "bold")
    box(ax, 4, 42, 19, 12, L["resolution_in"], lang, COLORS["blue2"], size=11, wrap=20)
    rows = [
        (75, L["resolution_herb"], "green"),
        (59, L["resolution_species"], "blue"),
        (43, L["resolution_formula"], "amber"),
        (27, L["resolution_smiles"], "rose"),
    ]
    for y, s, c in rows:
        box(ax, 39, y, 23, 9, s, lang, COLORS[c], size=9, wrap=24)
        arrow(ax, 23, 48, 39, y + 4.5)
    box(ax, 72, 47, 23, 16, L["resolution_unresolved"], lang, COLORS["white"], size=9, wrap=24)
    arrow(ax, 62, 48, 72, 55)
    txt(ax, 50, 12, L["provenance"], lang, 9, "normal", COLORS["muted"], wrap=85)
    fig.savefig(path.with_suffix(".png"), dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def forward(lang: str, path: Path):
    L = language_labels(lang)
    fig, ax = setup((12.5, 5.3))
    txt(ax, 50, 91, L["forward_title"], lang, 17, "bold")
    cards = [
        (3, L["input_card"], "blue"),
        (27, L["source_card"], "green"),
        (51, L["rule_card"], "amber"),
        (75, L["product_card"], "rose"),
    ]
    for x, s, c in cards:
        box(ax, x, 43, 20, 27, s, lang, COLORS[c], size=9, wrap=22)
    for x in (23, 47, 71):
        arrow(ax, x, 56.5, x + 4, 56.5)
    box(ax, 10, 18, 80, 12, L["provenance"], lang, COLORS["white"], size=9.2, wrap=100)
    arrow(ax, 50, 43, 50, 30)
    fig.savefig(path.with_suffix(".png"), dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def retro(lang: str, path: Path):
    L = language_labels(lang)
    fig, ax = setup((12, 6.6))
    txt(ax, 50, 94, L["retro_title"], lang, 17, "bold")
    box(ax, 33, 76, 34, 11, L["target"], lang, COLORS["blue2"], size=9)
    box(ax, 36, 54, 28, 9, L["amide"], lang, COLORS["amber"], size=9, wrap=25)
    arrow(ax, 50, 76, 50, 63)
    box(ax, 7, 30, 35, 12, L["prec1"], lang, COLORS["green"], size=8.5)
    box(ax, 58, 30, 35, 12, L["prec2"], lang, COLORS["green"], size=8.5)
    arrow(ax, 44, 54, 24, 42)
    arrow(ax, 56, 54, 76, 42)
    box(ax, 15, 12, 70, 9, L["retro_note"], lang, COLORS["white"], size=9, wrap=80)
    arrow(ax, 50, 30, 50, 21)
    fig.savefig(path.with_suffix(".png"), dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def benchmark(lang: str, path: Path):
    L = language_labels(lang)
    fig, ax = plt.subplots(figsize=(12, 6.2))
    fig.patch.set_facecolor("white")
    # 第 5 根柱（条件模板有匹配 493/500）已移除：它与 recall 不是同一量纲，
    # 放在同一根 percent 轴上会被误读为「又一个召回率」，数字本身仍写在正文里。
    labels = [L["forward_baseline"], L["forward_selected"], L["reverse"],
              L["multi2"], L["multi3"]]
    values = [58.73, 91.69, 94.74, 47.67, 72.33]
    colors = [COLORS["line"], COLORS["blue2"], COLORS["green"],
              COLORS["amber"], COLORS["amber"]]
    bars = ax.bar(range(len(values)), values, color=colors, edgecolor="#496773", linewidth=0.8)
    ax.set_ylim(0, 105)
    ax.set_ylabel("percent" if lang == "en" else "百分比", fontproperties=fp(lang), fontsize=10)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontproperties=fp(lang), fontsize=8.5)
    ax.grid(axis="y", color="#e2ecef", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    for index, (bar, value) in enumerate(zip(bars, values)):
        label = "%.2f%%" % value
        ax.text(bar.get_x() + bar.get_width() / 2, value + 2,
                label,
                ha="center", va="bottom", fontsize=9,
                fontproperties=fp(lang), color=COLORS["ink"])
    ax.set_title(L["bench_title"], fontproperties=fp(lang), fontsize=16, fontweight="bold", pad=14)
    fig.text(0.5, 0.02, L["bench_note"], ha="center", fontsize=8.5,
             fontproperties=fp(lang), color=COLORS["muted"])
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path.with_suffix(".png"), dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    for lang in ("en", "zh"):
        d = OUT / lang
        d.mkdir(parents=True, exist_ok=True)
        architecture(lang, d / "fig1_system_architecture")
        resolution(lang, d / "fig2_input_resolution")
        forward(lang, d / "fig3_forward_provenance")
        retro(lang, d / "fig4_retrosynthesis_example")
        benchmark(lang, d / "fig5_benchmark_summary")
        print("wrote", d)


if __name__ == "__main__":
    main()

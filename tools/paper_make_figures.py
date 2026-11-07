# -*- coding: utf-8 -*-
r"""论文配套：出图（用 venv 的 matplotlib；缺哪个输入就跳哪张图并打警告）。

产出（reports/paper/figures/）：
  fig1_toxicity_concentration.(png|pdf)  少数模板主导无效尝试（浓度曲线）
  fig2_usable_before_after.(png|pdf)     黑名单前后可用率（56 目标 / USPTO-50k 抽样）
  fig3_coverage_topk.(png|pdf)           USPTO-50k 覆盖率与 top-k（频次序）
  fig4_verdict_composition.(png|pdf)     切断构成对比（56 目标 vs USPTO-50k 抽样）
  fig5_instability.(png|pdf)             判据稳定性：三轮翻转
用法: & $venv tools\paper_make_figures.py
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

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import os as _os_root          # ★ 复现演练（B10）：仓库根可被环境变量覆盖，默认不变
STAGE = Path(_os_root.environ.get("CHEMCREACT_ROOT")
             or r"D:\ProgramData\DSHNS\chemreact-staging")
RES = STAGE / "reports" / "paper" / "results"
FIG = STAGE / "reports" / "paper" / "figures"


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("   写出", name)


def fig1():
    src = STAGE / "reports" / "retro_template_audit.jsonl"
    if not src.exists():
        print("[skip] fig1：缺", src.name)
        return
    rows = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
    rows = [r for r in rows if int(r.get("n_try", 0)) > 0]
    rows.sort(key=lambda r: -int(r.get("n_try", 0)))
    tot_bad = sum(int(r.get("n_try", 0)) - int(r.get("n_usable", 0)) for r in rows)
    cum, xs = 0.0, []
    for r in rows:
        cum += int(r.get("n_try", 0)) - int(r.get("n_usable", 0))
        xs.append(cum / max(1, tot_bad))
    fig, ax = plt.subplots(figsize=(4.6, 3.4))
    ax.plot(range(1, len(xs) + 1), [100 * x for x in xs], marker="o", ms=2.5, lw=1.4)
    ax.axvline(54, ls="--", c="crimson", lw=1)
    ax.annotate("54 templates\n-> 83.8% of wasted cuts",
                xy=(54, 83.8), xytext=(80, 55),
                arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.set_xlabel("# templates (sorted by wasted cut attempts)")
    ax.set_ylabel("cumulative share of wasted cuts (%)")
    ax.set_title("False-route generation is highly concentrated")
    save(fig, "fig1_toxicity_concentration")


def fig2():
    bars = []
    summ = STAGE / "reports" / "retro_template_audit_summary_r41.json"
    if summ.exists():
        s = json.loads(summ.read_text(encoding="utf-8"))
        before = 100 * s["totals"]["n_usable"] / max(1, s["totals"]["n_try"])
        after = 100 * s["before_after"]["after"]["n_usable"] / \
            max(1, s["before_after"]["after"]["n_try"])
        bars.append(("54-target audit\n(herb-derived)", before, after))
    us = RES / "usability_summary.json"
    if us.exists():
        s = json.loads(us.read_text(encoding="utf-8"))
        bars.append(("USPTO-50k sample\n(2,930 targets)", 100 * s["usable_rate"],
                     100 * s["usable_rate_after_blacklist"]))
    if not bars:
        print("[skip] fig2：缺输入")
        return
    import numpy as np
    x = np.arange(len(bars))
    fig, ax = plt.subplots(figsize=(4.6, 3.4))
    ax.bar(x - 0.18, [b[1] for b in bars], 0.36, label="before blacklist")
    ax.bar(x + 0.18, [b[2] for b in bars], 0.36, label="after blacklist")
    ax.set_xticks(x, [b[0] for b in bars])
    ax.set_ylabel("chemically usable cuts (%)")
    ax.set_title("Usable cut rate before/after blacklist")
    ax.legend()
    save(fig, "fig2_usable_before_after")


def fig3():
    # ★ A4 决定：USPTO-50k 全量图用 B10 的 50,016 目标 / 3,065 模板结果；
    #   旧的 5,002 目标 / 79,184 模板结果只作为 backup，不再作为全量图。
    cands = [
        RES / "coverage_summary__lib_uspto50k_excl_s1.json",
        STAGE / "repro-20261016" / "reports" / "paper" / "results"
        / "coverage_summary__lib_uspto50k_excl_s1.json",
        RES / "coverage_summary.json",
    ]
    src = next((p for p in cands if p.exists()), None)
    if src is None:
        print("[skip] fig3：缺 B10/主线 coverage_summary")
        return
    s = json.loads(src.read_text(encoding="utf-8"))
    ks = ["top1", "top3", "top5", "top10", "top50"]
    vals = [100 * s["topk"][k]["rate"] for k in ks]
    fig, ax = plt.subplots(figsize=(4.6, 3.4))
    ax.bar(["any"] + ks, [100 * s["any_hit_rate"]] + vals,
           color=["#333"] + ["#4c78a8"] * 5)
    for i, v in enumerate([100 * s["any_hit_rate"]] + vals):
        ax.text(i, v + 0.4, "%.1f" % v, ha="center", fontsize=8)
    ax.set_ylabel("reactant-set match rate (%)")
    ax.set_title("USPTO-50k coverage (50,016 targets, 3,065 templates)")
    save(fig, "fig3_coverage_topk")


def fig4():
    groups = []
    a = STAGE / "reports" / "retro_template_audit.jsonl"
    if a.exists():
        tot = Counter()
        for l in open(a, encoding="utf-8"):
            if not l.strip():
                continue
            r = json.loads(l)
            tot["usable"] += int(r.get("n_usable", 0))
            for k, v in r.items():
                if k.startswith("R") and k[1:2].isdigit():
                    tot[k.split("_")[0]] += int(v)
        n = sum(tot.values())
        groups.append(("54-target audit", {k: 100 * v / max(1, n) for k, v in tot.items()}))
    us = RES / "usability_summary.json"
    if us.exists():
        s = json.loads(us.read_text(encoding="utf-8"))
        tot = Counter()
        for k, v in s["verdicts"].items():
            tot["usable" if k == "ok" else k.split("_")[0]] += v
        n = sum(tot.values())
        groups.append(("USPTO-50k sample", {k: 100 * v / max(1, n) for k, v in tot.items()}))
    if not groups:
        print("[skip] fig4：缺输入")
        return
    keys = ["usable", "R1", "R2", "R3", "R4"]
    import numpy as np
    x = np.arange(len(groups))
    fig, ax = plt.subplots(figsize=(4.8, 3.4))
    bottom = np.zeros(len(groups))
    colors = {"usable": "#54a24b", "R1": "#e45756", "R2": "#f58518",
              "R3": "#b279a2", "R4": "#9d755d"}
    for k in keys:
        vals = np.array([g[1].get(k, 0.0) for g in groups])
        ax.bar(x, vals, 0.5, bottom=bottom, label=k, color=colors.get(k, "#999"))
        bottom += vals
    ax.set_xticks(x, [g[0] for g in groups])
    ax.set_ylabel("share of single-step cuts (%)")
    ax.set_title("Cut composition (R1 residue / R2 upsizing / ...)")
    ax.legend(ncol=5, fontsize=8)
    save(fig, "fig4_verdict_composition")


def fig5():
    # ★ 诚实版：翻转在受控负载实验里没有复现（详见 instability.json），
    #   真正可报的是"判定大量来自**超时（部分）搜索**"+ 两次独立审计的复现差异。
    labels, vals, notes = [], [], []
    ins = RES / "instability.json"
    if ins.exists():
        s = json.loads(ins.read_text(encoding="utf-8"))
        u = s["ustat"]["quiet1"]
        if u.get("mcs_calls"):
            labels.append("audit cut-set\n(66 MCS calls)")
            vals.append(100.0 * u.get("mcs_timeout", 0) / u["mcs_calls"])
            notes.append("controlled load test:\n0/3,414 verdict flips")
    us = RES / "usability_summary.json"
    if us.exists():
        u = json.loads(us.read_text(encoding="utf-8"))["ustat"]
        if u.get("mcs_calls"):
            labels.append("USPTO-50k sample\n(74,968 calls)")
            vals.append(100.0 * u.get("mcs_timeout", 0) / u["mcs_calls"])
            notes.append("replicate audits differ:\n3/414 (impl.), 28->26 (idx1613)")
    if not labels:
        print("[skip] fig5：缺输入")
        return
    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    ax.bar(labels, vals, color="#e45756", width=0.55)
    top = max(vals) if vals else 1.0
    ax.set_ylim(0, top * 1.28)
    for i, v in enumerate(vals):
        ax.text(i, v + top * 0.04, "%.1f%%" % v, ha="center", fontsize=9)
    ax.set_ylabel("MCS time-out share (%)")
    ax.set_title("Usability verdicts often come from timed-out\n"
                 "(partial) least-common-substructure searches", fontsize=10)
    for i, t in enumerate(notes):
        ax.text(i, 6, t, ha="center", fontsize=7, color="#555")
    save(fig, "fig5_instability")


def fig6():
    src = RES / "forward_50k.json"
    if not src.exists():
        print("[skip] fig6：缺", src.name)
        return
    s = json.loads(src.read_text(encoding="utf-8"))
    d = s["by_class_recall"]
    ks = sorted(d, key=lambda k: int(k))
    vals = [100 * d[k]["rate"] for k in ks]
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    ax.bar(["class %s" % k for k in ks], vals, color="#4c78a8")
    for i, v in enumerate(vals):
        ax.text(i, v + 1, "%.0f" % v, ha="center", fontsize=7.5)
    ax.axhline(100 * s["recall_1step"], ls="--", c="#e45756", lw=1)
    ax.text(len(ks) - 1, 100 * s["recall_1step"] + 1.5,
            "overall %.1f%%" % (100 * s["recall_1step"]), ha="right", fontsize=8,
            color="#e45756")
    ax.set_ylim(0, 100)
    ax.set_ylabel("recorded product found in candidates (%)")
    ax.set_title("Forward prediction on USPTO-50k (1 round, unranked candidates)")
    save(fig, "fig6_forward_by_class")


if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4(); fig5(); fig6()
    print("完成。")

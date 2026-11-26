# -*- coding: utf-8 -*-
"""P2 的三张图：候选分布、迁移失败、重叠与去污染。

数据全部从文件读取（不手写）：
  reports/candidate_table/candidates_cli.parquet    候选数分布
  reports/paper/results/forward_official_test__*.json/jsonl   官方口径
  reports/paper/split-20261114/mit_eval.json        MIT 口径

输出：reports/paper/split-20261114/figures/fig{1,2,3}_*.png（300 dpi）
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import candidate_table as CT  # noqa: E402

OUT = ROOT / "reports" / "paper" / "split-20261114" / "figures"
RES = ROOT / "reports" / "paper" / "results"

C_EMIT = "#9E9E9E"
C_V2 = "#4472C4"
C_V3 = "#ED7D31"
C_V3B = "#7F3F00"
C_LIGHT = "#A8C4E0"

plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.family": "DejaVu Sans",
})


def _label_bars(ax, bars, fmt="{:.1f}"):
    for b in bars:
        h = b.get_height()
        ax.annotate(fmt.format(h * 100), (b.get_x() + b.get_width() / 2, h),
                    textcoords="offset points", xytext=(0, 2),
                    ha="center", va="bottom", fontsize=7.5)


def _label_pct(ax, bars, fmt="{:.2f}"):
    for b in bars:
        h = b.get_height()
        ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, h),
                    textcoords="offset points", xytext=(0, 2),
                    ha="center", va="bottom", fontsize=7.5)


def fig_candidates():
    df, _ = CT.load(parquet=str(CT.DEFAULT_DIR / "candidates_cli.parquet"),
                    columns=["rid", "n_cand"])
    n = df.groupby("rid", sort=False).size().to_numpy()
    mean, med = float(n.mean()), float(np.median(n))
    fig, ax = plt.subplots(figsize=(4.4, 2.8))
    ax.hist(np.clip(n, 0, 90), bins=np.arange(0, 92, 3), color=C_V2,
            edgecolor="white", linewidth=0.6)
    ax.axvline(mean, color=C_V3, lw=1.4, ls="--")
    ax.annotate("mean %.1f" % mean, (mean, ax.get_ylim()[1] * 0.92),
                xytext=(6, 0), textcoords="offset points", color=C_V3, fontsize=8)
    clip = int((n > 90).sum())
    ax.text(0.98, 0.95, "%d reactions above 90\n(clipped at 90)" % clip,
            transform=ax.transAxes, ha="right", va="top", fontsize=7, color="#666666")
    ax.set_xlabel("Candidates per reaction")
    ax.set_ylabel("Reactions")
    ax.set_title("Candidate pool size (production configuration, 11,999 reactions)")
    ax.set_xlim(0, 92)
    fig.savefig(OUT / "fig1_candidates.png")
    plt.close(fig)
    print("fig1: n=%d mean=%.2f median=%.0f" % (len(n), mean, med))


def _j(tag):
    return json.loads((RES / ("forward_official_test__%s.json" % tag)).read_text(encoding="utf-8"))


def fig_transfer():
    us = {
        "Emission order": _j("official_norr")["top1"],
        "v2": _j("rerank_v2_official")["top1"],
        "v3, 12k": _j("rerank_v3d_official")["top1"],
        "v3, 50k": _j("rerank_v3_50k")["top1"],
    }
    mit = json.loads((ROOT / "reports" / "paper" / "split-20261114" / "mit_eval.json").read_text(encoding="utf-8"))
    by = {r["tag"]: r for r in mit["results"]}
    mi = {
        "Emission order": by["emission"]["top1"],
        "v2": by["rank_model_v2.pkl"]["top1"],
        "v3, 12k": by["rank_model_v3cli.pkl"]["top1"],
        "v3, 50k": by["rank_model_v3_50k.pkl"]["top1"],
    }
    labels = list(us)
    colors = [C_EMIT, C_V2, C_V3, C_V3B]
    n_us = int(_j("official_norr")["n_scored"])
    n_mit = int(by["emission"]["n"])
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.9), sharey=True)
    for ax, data, title in ((axes[0], us, "USPTO-50k official split (n = %s)" % format(n_us, ",")),
                            (axes[1], mi, "USPTO-MIT sample (n = %s)" % format(n_mit, ","))):
        bars = ax.bar(range(len(labels)), [data[k] for k in labels], color=colors,
                      width=0.68, edgecolor="white", linewidth=0.8)
        _label_bars(ax, bars)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(["Emission", "v2", "v3\n12k", "v3\n50k"], fontsize=8)
        ax.set_title(title)
        ax.set_ylim(0, 0.85)
        ax.axhline(0, color="black", lw=0.6)
    axes[0].set_ylabel("top-1 accuracy (%)")
    fig.suptitle("Structural features transfer, template statistics do not", y=1.02, fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "fig2_transfer.png")
    plt.close(fig)
    print("fig2: USPTO %s | MIT %s" % (us, mi))


def _clean_numbers():
    import paper_bench_official_test as PB
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    def canon(s):
        m = Chem.MolFromSmiles(s) if s else None
        return Chem.MolToSmiles(m) if m is not None else ""

    recs = PB.load_records()
    i2p = {r["i"]: canon(r.get("product") or "") for r in recs}
    df, _ = CT.load(parquet=str(CT.DEFAULT_DIR / "candidates_cli.parquet"),
                    columns=["rid", "want", "split"])
    train_want = set(df.loc[df["split"] == "train", "want"].unique().tolist())
    leak = {i for i, p in i2p.items() if p in train_want}
    out = {}
    for tag, name in (("rerank_v2_official", "v2"), ("rerank_v4_official", "v4")):
        rows = [json.loads(l) for l in io.open(RES / ("forward_official_test__%s.jsonl" % tag),
                                               encoding="utf-8") if l.strip()]
        ok = [r for r in rows if "error" not in r]
        full = sum(1 for r in ok if r["hit"] and r["rank"] == 1) / len(ok)
        clean = [r for r in ok if r["i"] not in leak]
        c = sum(1 for r in clean if r["hit"] and r["rank"] == 1) / len(clean)
        out[name] = (full, c)
    return out, len(leak), len(ok)


def fig_overlap():
    vals, n_leak, n_all = _clean_numbers()
    groups = ["v2", "v4"]
    full = [vals[g][0] * 100.0 for g in groups]
    clean = [vals[g][1] * 100.0 for g in groups]
    x = np.arange(len(groups))
    fig, ax = plt.subplots(figsize=(4.4, 2.8))
    b1 = ax.bar(x - 0.18, full, width=0.34, color=C_V2, label="All test reactions")
    b2 = ax.bar(x + 0.18, clean, width=0.34, color=C_LIGHT,
                label="Excluding training overlap")
    _label_pct(ax, b1, "{:.2f}")
    _label_pct(ax, b2, "{:.2f}")
    ax.set_xticks(x)
    ax.set_xticklabels(["v2", "v4"])
    ax.set_ylabel("top-1 accuracy (%)")
    ax.set_ylim(60, 76)
    ax.legend(frameon=False, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.14), ncol=2)
    ax.set_title("Overlap with the training half: %d / %d (%.1f%%)"
                 % (n_leak, n_all, 100.0 * n_leak / n_all))
    fig.savefig(OUT / "fig3_overlap.png")
    plt.close(fig)
    print("fig3: leak=%d/%d vals=%s" % (n_leak, n_all, vals))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fig_candidates()
    fig_transfer()
    fig_overlap()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

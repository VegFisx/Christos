# -*- coding: utf-8 -*-
r"""一次性：生成 fig7（截断饱和曲线 + 多步端到端曲线）。用 venv（有 matplotlib）。"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\figures\fig7_truncation_multistep.png")


def main() -> int:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    ax = axes[0]
    caps = [8, 32, 64]
    ax.plot(caps, [60.0, 64.6, 64.6], "o-", label="sweet-spot pool (3k/1.5k)")
    ax.plot(caps, [59.4, 75.8, 75.8], "s-", label="full pool (20k/6k)")
    for x, y in zip(caps, [60.0, 64.6, 64.6]):
        ax.annotate("%.1f%%" % y, (x, y), textcoords="offset points", xytext=(0, 6), fontsize=8)
    for x, y in zip(caps, [59.4, 75.8, 75.8]):
        ax.annotate("%.1f%%" % y, (x, y), textcoords="offset points", xytext=(0, -12), fontsize=8)
    ax.set_xlabel("max_products_per_pair (cap)")
    ax.set_ylabel("single-step any-hit (%)")
    ax.set_title("Truncation saturation (500-reaction ablation)")
    ax.set_xticks(caps)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    ax = axes[1]
    xs = [2, 3]
    ys = [47.67, 72.33]
    err = [(47.67 - 42.08, 53.31 - 47.67), (72.33 - 67.01, 77.09 - 72.33)]
    ax.errorbar(xs, ys, yerr=[[e[0] for e in err], [e[1] for e in err]],
                fmt="o-", capsize=5)
    ax.scatter([2], [46.0], marker="x", color="gray", label="n=100 pilot")
    for x, y in zip(xs, ys):
        ax.annotate("%.1f%%" % y, (x, y), textcoords="offset points", xytext=(6, 4), fontsize=9)
    ax.set_xticks(xs)
    ax.set_xlabel("search depth (beam=4)")
    ax.set_ylabel("end-to-end success (%)")
    ax.set_title("Multi-step route success (n=300, leak-free lib)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=200)
    print("saved", OUT, OUT.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())

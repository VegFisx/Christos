# -*- coding: utf-8 -*-
"""把「v2 分数 + 模板命中率」的混合参数打包成一个模型文件。

模型文件 = v2 的 59 维模型 + 模板统计（来自按生产配置重建的数据集）
           + blend_hitrate（后处理权重）。core/rerank.py 读到该字段才启用混合。

为什么用后处理而不是把命中率当特征：
  同样两个特征喂给 GBM，官方集 top-1 从 72.6% 崩到 27.5%（见第一百五十二轮）；
  但把命中率当反应内百分位与 v2 分数混合，内部 +1.3 pp、官方前 300 条 +3 pp。

用法：
  python tools\\build_blend_model.py --lambda 0.25
"""
from __future__ import annotations

import argparse
import io
import pickle
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "reports" / "rank_model_v2.pkl"))
    ap.add_argument("--stats-from", default=str(ROOT / "reports" / "rank_model_v3cli.pkl"))
    ap.add_argument("--lambda", dest="lam", type=float, default=0.25)
    ap.add_argument("--out", default=str(ROOT / "reports" / "rank_model_v4.pkl"))
    a = ap.parse_args()

    base = pickle.load(io.open(a.base, "rb"))
    stats_src = pickle.load(io.open(a.stats_from, "rb"))
    if not stats_src.get("tpl_stats"):
        print("[ERROR] %s 没有 tpl_stats" % a.stats_from)
        return 2

    blob = dict(base)
    blob.update({
        "tpl_stats": stats_src["tpl_stats"],
        "tpl_alpha": stats_src.get("tpl_alpha", 20.0),
        "tpl_prior": stats_src.get("tpl_prior", 0.0),
        "blend_hitrate": float(a.lam),
        "meta": dict(base.get("meta") or {}, version="v4",
                     note="v2 59 维 + 模板命中率后处理混合（lambda=%.2f）" % a.lam),
    })
    with io.open(a.out, "wb") as f:
        pickle.dump(blob, f)
    print("写出 %s（%.1f MB）：特征 %d 维，模板 %d 个，lambda=%.2f"
          % (a.out, Path(a.out).stat().st_size / 1e6, len(blob["features"]),
             len(blob["tpl_stats"]), a.lam))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

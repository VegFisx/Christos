# -*- coding: utf-8 -*-
# One-shot: where does the time go per pair?
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\github-release\christos")
for _p in ("core", "rules", "libs", "tools", "sources", "conditions"):
    d = STAGE / _p
    if d.is_dir() and str(d) not in sys.path:
        sys.path.insert(0, str(d))

import herb as H                    # noqa: E402
import smartreact_engine as SE      # noqa: E402


def main() -> int:
    lim = 24
    cs = H.compounds_of_herb("甘草", limit=lim)
    seeds = [(c.name, c.smiles, "tcm.db:甘草") for c in cs if c.smiles]
    n = len(seeds)
    print("底物 %d 个，对子 %d，每个底物出现在 %d 个对里"
          % (n, n * (n - 1) // 2, n - 1))

    t0 = time.time()
    eng = SE.SmartReactEngine(use_curated_templates=True,
                              strict_redox_gate=True,
                              mono_redox_gate=True)
    print("引擎加载 %.1f 秒" % (time.time() - t0))
    print("  curated 双底物 %d 条 / 单底物 %d 条"
          % (len(eng.curated_pair_templates), len(eng.curated_mono_templates)))
    print("  mined extra 模板 %d 条" % len(eng.extra_templates))
    print("  mined mono 模板 %d 条" % len(eng.mono_templates))
    print("  prefilter 默认 = %s" % eng.prefilter)
    print("  元素缓存条目 %d" % len(eng._elem_cache))
    return 0


if __name__ == "__main__":
    sys.exit(main())

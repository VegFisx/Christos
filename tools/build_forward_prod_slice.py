# -*- coding: utf-8 -*-
r"""从全量正向库切出"生产甜点"：arity2 前 3000 + arity1 前 1500（support 降序）。

依据（第六十五轮消融）：500 样本 any-hit——现役池 41.6% → k3000/1500 池 **60.0%**
（同速）；k6000/k20000 无额外收益。输出两个文件供引擎默认加载。
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

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
SRC = STAGE / "reports" / "mined_forward_templates_full_s5.jsonl"
OUT2 = STAGE / "reports" / "mined_forward_full_arity2_top3000.jsonl"
OUT1 = STAGE / "reports" / "mined_forward_full_arity1_top1500.jsonl"

sys.path.insert(0, str(STAGE / "tools"))
import rdkit_template_lib as lib          # noqa: E402


def main() -> int:
    tpls = lib.load_mined_templates(SRC, min_support=5, limit=100000)
    by, n_fail = lib.compile_templates_all(tpls)
    sup = {t.smarts: t.support for t in tpls}
    for arity, out, k in ((2, OUT2, 3000), (1, OUT1, 1500)):
        rows = by.get(arity, [])[:k]
        with open(out, "w", encoding="utf-8") as f:
            for sm, _rx in rows:
                f.write(json.dumps({"template": sm, "support": sup.get(sm, 0),
                                    "src": "ord_shards_full/arity%d" % arity},
                                   ensure_ascii=False) + "\n")
        print("arity%d: %d 条 -> %s" % (arity, len(rows), out.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
r"""从全量分片构建**泄漏剔除版**正向模板库（论文口径）。

口径（与逆向侧同款纪律）：分片里每一行 = 一条 ORD 反应；
**若该反应的产物（去映射、规范化后）命中 USPTO-50k 评测集，则整行剔除**，
不参与模板挖掘——避免"从考题学模板再考同一套题"。

输入：reports/ord_shards_full/shard_*.jsonl；reports/paper/data/uspto50k_canon.jsonl
输出：reports/mined_forward_templates_full_lf.jsonl（+ 剔除计数打印，不静默）
"""
from __future__ import annotations

import collections
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
SHARDS = STAGE / "reports" / "ord_shards_full"
CANON = STAGE / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
OUT = STAGE / "reports" / "mined_forward_templates_full_lf.jsonl"

from rdkit import Chem, RDLogger   # noqa: E402
RDLogger.DisableLog("rdApp.*")


def canon_nomap(smi: str):
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return Chem.MolToSmiles(m, isomericSmiles=False)


def main() -> int:
    t0 = time.time()
    prod_set = set()
    for line in open(CANON, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        p = d.get("product") or (d.get("products") or [None])[0]
        if p:
            cp = canon_nomap(p)
            if cp:
                prod_set.add(cp)
    print("50k 产物集合：%d 个（%.0fs）" % (len(prod_set), time.time() - t0), flush=True)
    cnt = collections.Counter()
    n_rows = n_skip = n_bad = 0
    files = sorted(SHARDS.glob("shard_*.jsonl"))
    for k, fp in enumerate(files, 1):
        for line in open(fp, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            n_rows += 1
            try:
                d = json.loads(line)
                rx = d.get("rx") or ""
                tpl = d.get("template") or ""
                if ">>" not in rx or ">>" not in tpl:
                    n_bad += 1
                    continue
            except Exception:
                n_bad += 1
                continue
            right = rx.split(">>")[-1]
            cp = canon_nomap(right)
            if cp is None:
                n_bad += 1
                continue
            if cp in prod_set:                     # ★ 泄漏行：整行剔除
                n_skip += 1
                continue
            a, b = tpl.split(">>", 1)
            cnt[b + ">>" + a] += 1
        if k % 50 == 0:
            print("  ... %d/%d 片 · %d 行（剔泄漏 %d · 坏 %d）· 模板 %d · %.0fs"
                  % (k, len(files), n_rows, n_skip, n_bad, len(cnt), time.time() - t0),
                  flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for t, n in cnt.most_common():
            f.write(json.dumps({"template": t, "support": n, "src": "ord_shards_full_leakfree"},
                               ensure_ascii=False) + "\n")
    n5 = sum(1 for _, n in cnt.items() if n >= 5)
    print("完成：读 %d 行 · **剔泄漏行 %d** · 坏 %d · 唯一正向模板 %d（s>=5: %d）"
          % (n_rows, n_skip, n_bad, len(cnt), n5))
    print("输出 -> %s（%.1f MB · %.0fs）"
          % (OUT, OUT.stat().st_size / 1048576, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

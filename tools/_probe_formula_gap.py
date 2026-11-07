# -*- coding: utf-8 -*-
"""一次性探针（只读）：方剂库"不全"缺在哪 —— 两个来源对比 + 找可用的参照物。

Q1 formula_db.json（主库）vs formula_db_api_only.json（API 源）差在哪
Q2 两边的 category / chuchu 分布（看谁偏传统、谁含现代制剂）
Q3 盘上有哪些药典/成方制剂类参照数据（能当"缺什么"的标尺）
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

D = Path(r"D:\TCMAI\data")
MAIN = D / "formula_db.json"
API = D / "formula_db_api_only.json"


def load(p: Path):
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as ex:                                # noqa: BLE001
        print("  读不动 %s：%s: %s" % (p.name, type(ex).__name__, ex))
        return None


def stats(d, label):
    names = set(d)
    recs = sum(len(v) for v in d.values())
    print("  %-22s 名字 %5d · 记录 %5d" % (label, len(names), recs))
    cat = Counter()
    src = Counter()
    for v in d.values():
        for r in v:
            if isinstance(r, dict):
                cat[str(r.get("category"))] += 1
                src[str(r.get("chuchu"))[:34]] += 1
    print("     category:", cat.most_common(5))
    print("     chuchu  :", src.most_common(6))
    return names, cat, src


def main() -> None:
    m = load(MAIN)
    a = load(API)
    print("[Q1/Q2] 两个方剂文件对比")
    if m is None or a is None:
        print("  缺文件，跳过")
    else:
        nm, _c1, _s1 = stats(m, "主库 formula_db.json")
        na, _c2, _s2 = stats(a, "API formula_db_api_only")
        print("    主库独有 %d · API 独有 %d · 交集 %d"
              % (len(nm - na), len(na - nm), len(nm & na)))
        print("    主库独有样例：", sorted(nm - na)[:8])
        print("    API 独有样例：", sorted(na - nm)[:8])

    print()
    print("[Q3] 盘上可能的参照物（药典 / 成方制剂 / 中成药清单）")
    roots = [Path(r"D:\TCMAI"), Path(r"D:\TCMAI\data"), Path(r"D:\TCMAI\docs"),
             Path(r"D:\ProgramData\DSHNS\chemreact-staging\data"),
             Path(r"D:\ProgramData\DSHNS\chemreact-staging\ord-data"),
             Path(r"D:\TCMAI\build"), Path(r"D:\TCMAI\archive")]
    pats = ("*chp*", "*yaodian*", "*药典*", "*成方*", "*中成药*", "*indkb*",
            "*formula*", "*fangji*", "*prescription*")
    seen = set()
    for r in roots:
        if not r.is_dir():
            continue
        for p in pats:
            for f in r.glob(p):
                if f in seen or f.is_dir():
                    continue
                seen.add(f)
                try:
                    sz = f.stat().st_size / 1024.0
                except OSError:
                    continue
                print("    %-72s %8.1f KB" % (str(f), sz))


if __name__ == "__main__":
    main()

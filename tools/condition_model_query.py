# -*- coding: utf-8 -*-
r"""D2 入口：给一套**化学条件**问模型「这套条件会不会有产物」——只打标记，不做门控。

为什么要有这个入口（第三十七轮 Q4-a）：模型的特征是 HTE 的
溶剂/催化剂/碱/来源**名字**，而现有 10 个工艺模板给的是 water / ethanol —— 分布外。
所以要先有一个能填「化学条件」的入口，模型才有意义。

用法:
  python tools/condition_model_query.py --list-vocab
  python tools/condition_model_query.py --aryl "c1ccc(Br)cc1" --amine "Nc1ccccc1" \
      --solvent DMSO --catalyst "cphos-pd-g4" --base "P2Et" --source "JNJ HTE 2024"
  python tools/condition_model_query.py --aryl "c1ccc(Br)cc1" --amine "Nc1ccccc1" --solvent water
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_STAGE = Path(__file__).resolve().parent.parent
for _p in (_STAGE / "core", _STAGE / "rules", _STAGE / "libs", _STAGE / "tools"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import condition_model as cm  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="条件可行性模型（只打标记）")
    ap.add_argument("--reaction", default="B-H", help="反应类（默认 B-H；其它类按类降级）")
    ap.add_argument("--aryl", default="", help="底物 A 的 SMILES")
    ap.add_argument("--amine", default="", help="底物 B 的 SMILES")
    ap.add_argument("--solvent", default="")
    ap.add_argument("--catalyst", default="")
    ap.add_argument("--base", default="")
    ap.add_argument("--source", default="")
    ap.add_argument("--list-vocab", action="store_true", help="打印训练词表（可选的取值）")
    a = ap.parse_args()

    print("=" * 78)
    print(cm.describe())
    print("=" * 78)

    if a.list_vocab:
        v = cm.vocab()
        for k in ("solvent", "catalyst", "base", "source"):
            vals = v.get(k, [])
            print("")
            print("[" + k + "] " + str(len(vals)) + " 个取值：")
            print("   " + " | ".join(vals[:40]) + (" ..." if len(vals) > 40 else ""))
        return 0

    if not (a.aryl and a.amine):
        print("")
        print("需要 --aryl 与 --amine（模型的两个底物指纹位）。")
        return 2

    r = cm.score(solvent=a.solvent, catalyst=a.catalyst, base=a.base, source=a.source,
                 aryl=a.aryl, amine=a.amine, reaction=a.reaction)
    print("")
    if not r["applicable"]:
        print("不适用：" + str(r["note"]))
        return 0
    print("p(这套条件会有产物) = %.4f   档位：%s" % (r["p"], r["band"]))
    print("分布外字段：" + ("、".join(r["ood"]) if r["ood"] else "无"))
    print("说明：" + str(r["note"]))
    print("")
    print("★ 这是**标记**，不是门控：不删产物、不排序、不筛路线（第三十七轮 Q1-c）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

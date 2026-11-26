# -*- coding: utf-8 -*-
"""救回模板的泄漏检查：低支持度模板是不是从「同一条反应」挖出来的？

输入：
  _diag/screen_rescues_100.json（screen_gap_templates.py 的救回明细）
  reports/ord_shards_full/shard_*.jsonl（每行 {template(反向), rx(带映射反应)}）

对每个救回模板，找出 ORD 里产生它的反应，比较：
  exact     产物相同 + 反应物集合相同  → 记忆，算泄漏
  same_prod 产物相同、反应物不同       → 可疑（同产物不同路线）
  other     产物不同                   → 真泛化
  no_src    分片里找不到来源
"""
from __future__ import annotations

import json
import re
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

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

SHARDS = ROOT / "reports" / "ord_shards_full"
_MAP = re.compile(r"\[([^:\]]*):\d+\]")


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def strip_map(s):
    return _MAP.sub(r"[\1]", s or "")


def flip(t):
    if ">>" not in t:
        return t
    a, b = t.split(">>", 1)
    return b + ">>" + a


def main() -> int:
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_diag" / "screen_rescues_100.json"
    rescues = json.loads(p.read_text(encoding="utf-8"))
    print("救回记录 %d 条，模板 %d 个" % (len(rescues), len({r["template"] for r in rescues})))

    # 正向模板 + 反向模板 -> 救回记录
    tpl_to_rescues = {}
    for r in rescues:
        for form in {r["template"], flip(r["template"])}:
            tpl_to_rescues.setdefault(form, []).append(r)

    files = sorted(SHARDS.glob("shard_*.jsonl"))
    print("扫描分片 %d 个 ..." % len(files), flush=True)
    sources = {}
    n = 0
    for k, fp in enumerate(files, 1):
        with open(fp, encoding="utf-8") as f:
            for line in f:
                n += 1
                d = json.loads(line)
                t = d.get("template") or ""
                if t in tpl_to_rescues:
                    sources.setdefault(t, []).append(d.get("rx") or "")
        if k % 100 == 0:
            print("  ...%d/%d 片 · %d 行" % (k, len(files), n), flush=True)
    print("命中来源模板 %d 个 / 扫描 %d 行" % (len(sources), n), flush=True)

    stat = {"exact": 0, "same_prod": 0, "other": 0, "no_src": 0}
    examples = []
    for r in rescues:
        want = r["want"]
        rx_set = set()
        for form in {r["template"], flip(r["template"])}:
            rx_set.update(sources.get(form, []))
        if not rx_set:
            stat["no_src"] += 1
            continue
        u_set = sorted({canon(r["r1"]), canon(r["r2"])} - {""})
        verdict = None
        for rx in rx_set:
            if ">>" not in rx:
                continue
            left, right = rx.split(">>", 1)
            prods = {canon(x) for x in strip_map(right).split(".") if x}
            if want not in prods:
                continue
            src_react = sorted({canon(x) for x in strip_map(left).split(".") if x} - {""})
            if src_react == u_set:
                verdict = "exact"
                break
            verdict = "same_prod"
        if verdict is None:
            stat["other"] += 1
        else:
            stat[verdict] += 1
            if len(examples) < 10:
                examples.append((r["rid"], verdict, r["template"][:60]))

    n = len(rescues)
    print("\n泄漏分类（%d 条救回）：" % n)
    for k in ("exact", "same_prod", "other", "no_src"):
        print("  %-10s %3d  %.1f%%" % (k, stat[k], 100.0 * stat[k] / max(1, n)))
    print("  真泛化 = other / (有来源) = %.1f%%"
          % (100.0 * stat["other"] / max(1, n - stat["no_src"])))
    print("\n个例：")
    for rid, v, t in examples:
        print("  rid=%-6s %-9s %s" % (rid, v, t))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

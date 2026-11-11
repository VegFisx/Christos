"""学习型路线要扩覆盖，先得知道「凭空多出来的产物片段」长什么样。

背景（第 146 轮）：
    键编辑只能表达已有原子之间的键变化。ORD 里只有 3% 的反应产物原子全部来自底物；
    其余 95% 的产物里还有未映射片段（离去基团、试剂残基、盐）。这些片段用改键造不出来，
    所以那条路线被限制在 3%。

本探针只回答一个问题（不做任何建模）：
    未映射产物片段到底是什么？用多大的「片段词表」能覆盖多少？

口径：
    - 产物侧：把每个分子拆成连通片段；**全部原子都没有映射号**的片段记为「新增片段」。
    - 同时记录：反应里映射原子数、新增片段数、新增片段的重原子数。
    - 输出：新增片段按「去立体规范 SMILES」的出现频次排行，以及覆盖率曲线
      （top-1 / top-5 / top-20 / top-100 词表能解释多少条反应）。

用法：
    python tools/probe_unmapped_fragments.py 5000
"""

import collections
import json
import os
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_HERE = Path(__file__).resolve().parent
STAGE = _HERE.parent
for _p in (STAGE, STAGE / "libs"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SHARDS = STAGE / "reports" / "ord_shards_full"


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5000

    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    shards = sorted(SHARDS.glob("shard_*.jsonl"))
    freq = collections.Counter()
    n = 0
    stat = collections.Counter()
    sizes = collections.Counter()
    per_react_counts = collections.Counter()

    for sh in shards:
        with open(sh, encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                rx = row.get("rx") or ""
                if ">>" not in rx:
                    continue
                lhs, rhs = rx.split(">>", 1)
                P = Chem.MolFromSmiles(rhs)
                if P is None:
                    stat["unparsable_product"] += 1
                    continue
                n += 1
                # 每个片段：全部原子无映射 = 新增片段
                frags = Chem.GetMolFrags(P, asMols=True, sanitizeFrags=False)
                new_frags = []
                for f in frags:
                    if all(a.GetAtomMapNum() == 0 for a in f.GetAtoms()):
                        new_frags.append(f)
                per_react_counts[len(new_frags)] += 1
                if not new_frags:
                    stat["no_new_fragment"] += 1
                for f in new_frags:
                    smi = Chem.MolToSmiles(f, isomericSmiles=False)
                    freq[smi] += 1
                    sizes[f.GetNumHeavyAtoms()] += 1
                if n >= limit:
                    break
        if n >= limit:
            break

    print(f"检查 {n} 条反应的产物")
    print(f"  产物里没有新增片段（=全映射）: {stat['no_new_fragment']} = "
          f"{100.0 * stat['no_new_fragment'] / max(1, n):.1f}%")
    print("  每条反应的新增片段数分布:",
          dict(sorted(per_react_counts.items())[:8]))
    print("  新增片段重原子数分布(前 8):",
          dict(sorted(sizes.items())[:8]))
    print(f"\n新增片段种类 {len(freq)} 个 · 总出现 {sum(freq.values())} 次")
    print("  最常见的 25 个:")
    for smi, c in freq.most_common(25):
        print(f"    {smi:<24} {c}")

    # 覆盖率：top-k 词表能解释的「片段出现次数」占比
    total = sum(freq.values())
    acc = 0
    print("\n  词表覆盖率（按出现次数）:")
    for k, (smi, c) in enumerate(freq.most_common(100), start=1):
        acc += c
        if k in (1, 5, 10, 20, 50, 100):
            print(f"    top-{k:<3} 覆盖 {100.0 * acc / total:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

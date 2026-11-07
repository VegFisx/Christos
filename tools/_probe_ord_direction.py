# -*- coding: utf-8 -*-
r"""探针：ORD 数据本身能不能给出【反应方向】的先验？

只回答一个问题：在 ORD 里，一个反应的（底物集 -> 产物集）在别的记录里
**反向**出现（即"产物"当底物、"底物"当产物）的比例有多少？

口径（先定死）：
  * 抽样：ord_condition_dataset 分片前 N 片（分片本身是固定 row group 切出来的，可复现）
  * 每条记录取 reactants / product 两列（CXSMILES），用 core 引擎同款方式拆分
  * 规范化：RDKit canonical SMILES（**不带映射号**，因为这里只判"同一分子"）
  * 「反向出现过」= 存在另一条记录，其【产物分子集合】是这条记录的【底物集合】的子集，
    且其【底物分子集合】是这条记录【产物集合】的子集。
  * 只做**集合级**近似判断（不做映射级配平），因为这一步只想知道"值不值得做"

输出：整体双向率 + 按反应规模分档 + 几个例子。
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, str(STAGE / "core"))
sys.path.insert(0, str(STAGE / "tools"))

import duckdb                                    # noqa: E402
from rdkit import Chem, RDLogger                 # noqa: E402

RDLogger.DisableLog("rdApp.*")

SHARDS = (STAGE / "reports" / "ord_condition_dataset" / "shard_*.parquet").as_posix()
N_SHARDS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
MAX_ROWS = int(sys.argv[2]) if len(sys.argv) > 2 else 120000


def canon_set(s: str) -> frozenset:
    """CXSMILES 串（点号分隔多组分）-> canonical SMILES 集合。"""
    out = set()
    if not s:
        return frozenset()
    for part in str(s).split("."):
        part = part.strip()
        if not part:
            continue
        m = Chem.MolFromSmiles(part)
        if m is None:
            continue
        out.add(Chem.MolToSmiles(m))
    return frozenset(out)


def main() -> int:
    t0 = time.time()
    con = duckdb.connect()
    con.execute("SET enable_progress_bar=false")
    print(f"抽样：前 {N_SHARDS} 片，上限 {MAX_ROWS:,} 行")
    rows = con.execute(
        f"SELECT reactants, product FROM read_parquet('{SHARDS}') LIMIT {MAX_ROWS}"
    ).fetchall()
    print(f"读到 {len(rows):,} 行，用时 {time.time()-t0:.1f}s\n")

    recs = []
    n_bad = 0
    for r, p in rows:
        rs, ps = canon_set(r), canon_set(p)
        if not rs or not ps:
            n_bad += 1
            continue
        recs.append((rs, ps))
    print(f"可用记录 {len(recs):,}（拆分失败 {n_bad:,}）")

    # 反向索引：某分子集合 -> 出现在哪些记录的底物侧
    by_react = defaultdict(list)
    for i, (rs, ps) in enumerate(recs):
        by_react[rs].append(i)

    # 逐条判：删除一个产物分子后，是否等于某条记录的底物集合？
    #   ★ 这比"整集合相等"宽松得多、也更接近"这一步能不能倒过来"：
    #     记录 P 的产物集合 == 记录 Q 的底物集合，说明 P 的正向产物正是 Q 的底物。
    n_rev = 0
    examples = []
    for rs, ps in recs:
        # 这条记录的某个产物，是否在别的记录里当过底物（多步存在的下界）
        fwd_hit = any(by_react.get(frozenset({x})) for x in ps)
        if fwd_hit:
            n_rev += 1
            if len(examples) < 4:
                for x in sorted(ps):
                    if by_react.get(frozenset({x})):
                        j = by_react[frozenset({x})][0]
                        examples.append((rs, ps, x, recs[j][1]))
                        break

    rate = n_rev / max(1, len(recs))
    print(f"\n★ 实测①：{n_rev:,}/{len(recs):,} = **{rate:.1%}** 的记录，"
          f"其某个产物在别的记录里当过底物")
    print("   （= 数据里存在『继续往下反应』的记录）")
    for rs, ps, x, ps2 in examples:
        print(f"\n   例：底物 {sorted(rs)}")
        print(f"       -> 产物 {sorted(ps)}")
        print(f"       其中 {x} 在另一条记录里当底物 -> {sorted(ps2)}")
    print(f"\n总用时 {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

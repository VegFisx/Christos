# -*- coding: utf-8 -*-
r"""★ 决定性测量：SmartReact 对【天然产物尺寸】反应的覆盖率是多少？★

直接回答用户的问题："煎煮所需的反应是否完全不包含在已有规则库里？"

方法：把 ORD 反应按【底物尺寸】分层（用 ORD/COCONUT 自己的分布做界，不发明阈值），
      在每层里测 SmartReact 的覆盖率。

  全部          —— 基准
  底物重原子>=15 —— COCONUT 的 p10（"天然产物尺寸"的宽松界）
  底物重原子>=30 —— COCONUT 的中位（严格界）

若覆盖率在这两层里断崖式下跌 -> 说明规则库系统性地不覆盖大分子（天然产物）化学。

同时列出这些层里【零覆盖】的反应中心 = 缺的具体化学。

用法: python measure_coverage_by_size.py [抽样数]
"""
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402
import mapped_chem as mc  # noqa: E402

RDLogger.DisableLog("rdApp.*")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"


def is_carbonyl_c(a):
    if a.GetSymbol() != "C":
        return False
    for b in a.GetBonds():
        o = b.GetOtherAtom(a)
        if o.GetSymbol() in ("O", "N", "S") and b.GetBondTypeAsDouble() == 2.0:
            return True
    return False


def adesc(a):
    sym = a.GetSymbol()
    if sym == "N":
        if a.GetIsAromatic():
            return "唑N"
        if any(is_carbonyl_c(nb) for nb in a.GetNeighbors()):
            return "酰胺N"
        hn = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() == "H")
        return f"胺N({'NH2' if hn >= 2 else 'NH' if hn == 1 else 'N'})"
    if sym == "O":
        if a.GetIsAromatic():
            return "酚O/芳醚O"
        return "醚/酯O" if sum(1 for nb in a.GetNeighbors()
                            if nb.GetSymbol() == "C") >= 2 else "羟基O"
    s = sym
    if a.GetIsAromatic():
        s += "ar"
    elif a.IsInRing():
        s += "环"
    if is_carbonyl_c(a):
        s += "=O"
    het = sum(1 for nb in a.GetNeighbors() if nb.GetSymbol() not in ("C", "H"))
    if het:
        s += f"{min(het,3)}杂"
    return s


con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")
rows = con.execute(
    f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') USING SAMPLE {N} ROWS"
).fetchall()
con.close()
print(f"抽样 {len(rows)} 条\n")

enum = ReactionEnumerator()

# 层 -> [可测, 命中]
layers = defaultdict(lambda: [0, 0])
zero_center = Counter()        # 大分子层里，零覆盖的反应中心
zero_examples = defaultdict(list)
all_center = Counter()
seen = set()
t0 = time.time()
n_test = 0

for (blob,) in rows:
    rxn = reaction_pb2.Reaction()
    try:
        rxn.ParseFromString(blob)
    except Exception:
        continue
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES), None)
    if cx is None:
        continue
    lhs, agents, rhs = mc.split_rxn(cx)
    if not lhs or not rhs:
        continue
    try:
        pm = mc.parse_mapped(rhs)
    except mc.MapStrippedError:
        continue
    if pm is None:
        continue
    pmaps = mc.map_nums(pm)
    product = mc.canon_plain(rhs)
    if product is None:
        continue
    raws, plains = mc.contributing_components(lhs, pmaps)
    if len(plains) != 2:
        continue
    r1, r2 = sorted(plains)
    if (r1, r2, product) in seen:
        continue
    seen.add((r1, r2, product))
    n_test += 1

    # 底物尺寸
    hm = 0
    for s in plains:
        m = mc.parse_plain(s)
        if m is not None:
            hm = max(hm, m.GetNumHeavyAtoms())

    # 反应中心
    left_bonds = 0
    try:
        left = mc.bonds_over_maps_all(raws)
        formed, _ = mc.formed_broken(pm, left)
        labs = []
        for pair in formed:
            a1 = next((a for a in pm.GetAtoms() if a.GetAtomMapNum() == pair[0]), None)
            a2 = next((a for a in pm.GetAtoms() if a.GetAtomMapNum() == pair[1]), None)
            if a1 and a2:
                labs.append(" - ".join(sorted([adesc(a1), adesc(a2)])))
        label = "(无成键)" if not labs else (labs[0] if len(labs) == 1 else f"(多键){labs[0]}")
    except mc.MapStrippedError:
        label = "(映射异常)"

    # 命中判定
    try:
        res = enum.enumerate_pair(r1, r2)
        hit = any(mc.canon_plain(p) == product for r in res for p in r.products)
    except Exception:
        hit = False

    for name, cond in (("全部", True),
                       ("底物>=15重原子", hm >= 15),
                       ("底物>=30重原子", hm >= 30)):
        if cond:
            layers[name][0] += 1
            if hit:
                layers[name][1] += 1

    if hm >= 15:
        all_center[label] += 1
        if not hit:
            zero_center[label] += 1
            if len(zero_examples[label]) < 2 and not label.startswith("(多键)"):
                zero_examples[label].append((r1, r2, product))

print(f"可测 {n_test} 条，耗时 {time.time()-t0:.0f}s\n")

print("=" * 94)
print("★ 分层覆盖率（同一批 ORD 反应，按底物尺寸分层）")
print("=" * 94)
print(f"   {'层':<18} {'可测':>7} {'命中':>7} {'覆盖率':>9}")
for name in ("全部", "底物>=15重原子", "底物>=30重原子"):
    t, h = layers[name]
    if t:
        print(f"   {name:<18} {t:>7} {h:>7} {h/t*100:>8.1f}%")

print()
print("=" * 94)
print("★ 底物>=15 重原子的反应里，【零覆盖】的反应中心（= 缺的化学）")
print("=" * 94)
tot = sum(all_center.values())
tot_zero = sum(zero_center.values())
print(f"   该层共 {tot} 条，其中零覆盖 {tot_zero} 条 "
      f"({tot_zero/tot*100 if tot else 0:.1f}%)\n")
print(f"   {'零覆盖':>7} {'该中心总数':>10} {'零覆盖占比':>10}  反应中心")
for lab, c in zero_center.most_common(22):
    t = all_center[lab]
    print(f"   {c:>7} {t:>10} {c/t*100 if t else 0:>9.1f}%  {lab}")

print()
print("   零覆盖中心的实例：")
for lab, exs in list(zero_examples.items())[:6]:
    if not exs:
        continue
    r1, r2, prod = exs[0]
    print(f"   【{lab}】")
    print(f"      底物: {r1[:60]}  +  {r2[:60]}")
    print(f"      产物: {prod[:70]}")

enum.close()

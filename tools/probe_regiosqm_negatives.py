# -*- coding: utf-8 -*-
r"""第十四轮 / 任务②附：RegioSQM20 能造多少【合成选择性负例】？

口径（照 jensengroup/SI_RegioSQM20 + negative_learning 仓库的做法）：
  每条底物有一个"正确位点"（positive）与若干"错误位点"（negative）；
  错误位点 = 底物上**所有芳香 C–H**（可被卤化的位置）减去正确位点。
  → 所以合成负例数 ≈ Σ(芳香 C–H 数 - 1)。

数据：data/external/negatives/regiosqm20_compounds.smiles（GitHub raw 下载，535 行）
格式：name <TAB> SMILES <TAB> n_halogens

用法: python probe_regiosqm_negatives.py
"""
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")
P = STAGE / "data" / "external" / "negatives" / "regiosqm20_compounds.smiles"

rows = [l.split() for l in P.read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"读入 {len(rows)} 行（name / SMILES / 正确位点索引表）")
print(f"  原始首行: {rows[0] if rows else '<空>'}")
print(f"  原始第二行: {rows[1] if len(rows) > 1 else '<空>'}")
ok = bad = total_neg = 0
center_counts = {}
examples = []
for f in rows:
    if len(f) < 3:
        continue
    name, smi, centers_raw = f[0], f[1], f[2].strip()
    m = Chem.MolFromSmiles(smi)
    if m is None:
        bad += 1
        continue
    ok += 1
    # 第三列是【正确位点索引表】（如 "1,3,5" / "2"），不是卤素数
    try:
        centers = [int(x) for x in centers_raw.split(",") if x.strip() != ""]
    except ValueError:
        centers = []
    key = len(centers)
    center_counts[key] = center_counts.get(key, 0) + 1
    ach = sum(1 for a in m.GetAtoms()
              if a.GetIsAromatic() and a.GetSymbol() == "C" and a.GetTotalNumHs() > 0)
    neg = max(0, ach - len(centers))       # 芳香 C–H 里扣掉正确位点
    total_neg += neg
    if len(examples) < 5:
        examples.append((name, smi, ach, len(centers), neg))
print(f"  可解析 {ok}，不可解析 {bad}")
print(f"  正确位点数分布: {dict(sorted(center_counts.items()))}")
print(f"  ★ 可生成的【合成选择性负例】总数 ≈ {total_neg} 条"
      f"（平均 {total_neg/max(1,ok):.1f} 条/底物）")
print("  样例（底物 / 芳香C–H / 正确位点数 / 可造负例数）:")
for e in examples:
    print(f"    {e[0]:<10} {e[1][:42]:<44} CH={e[2]:<3} 正确={e[3]:<3} neg={e[4]}")
print()
print("口径提醒：合成负例 = 「同一个底物，换到错误位点」——它检验的是【选择性】不是【活性】；")
print("          与 HTE 的『实验做不出来』是两种不同的假阳性，不能混为一谈。")

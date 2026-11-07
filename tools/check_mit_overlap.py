"""检查 USPTO-MIT 480K 与模板库 `example` 反应的严格重叠（能不能拿 480K 做外部基线）。

判据（与第 110 轮泄漏检查同一套）：
  * 反应键 = (反应物 canonical 集合, 产物 canonical) 的字符串
  * 严格同反应 = 两侧反应物集合与产物都相同
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

HERE = ROOT
MIT = HERE / "reports" / "paper" / "data" / "uspto_mit" / "USPTO_MIT.csv"
TPL = HERE / "libs" / "smartreact" / "data" / "templates.txt"


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(m) if m else ""


def key(reactants, product):
    rs = sorted(canon(x) for x in reactants if x.strip())
    return ".".join(rs) + ">>" + canon(product)


def main() -> int:
    tpl_keys = set()
    n_tpl = 0
    with open(TPL, encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            ex = (row.get("example") or "").strip()
            if not ex:
                continue
            n_tpl += 1
            parts = ex.split(">")
            if len(parts) == 3:
                tpl_keys.add(key(parts[0].split("."), parts[2]))

    n = 0
    hit = 0
    ex_hit = []
    with open(MIT, encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            rxn = row.get("reactions") or ""
            parts = rxn.split(">")
            if len(parts) != 3:
                continue
            n += 1
            k = key(parts[0].split("."), parts[2])
            if k in tpl_keys:
                hit += 1
                if len(ex_hit) < 3:
                    ex_hit.append(rxn[:120])
    print(f"模板条目 {n_tpl}（可解析反应键 {len(tpl_keys)}）")
    print(f"480K 反应 {n}，严格同反应命中模板示例 {hit} = {100.0*hit/max(1,n):.3f}%")
    for e in ex_hit:
        print("  例:", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

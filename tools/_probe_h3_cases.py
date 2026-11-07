# -*- coding: utf-8 -*-
r"""
一次性探针（H3）：验收用例的底物到底能不能从 tcm.db 取？
先看清库结构，再逐条用例查：按【名字】能不能查到、查到的 SMILES 与手写的**规范式**是否一致。
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
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem, RDLogger                    # noqa: E402
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from tcm_ro import open_db                          # noqa: E402


def canon(smi):
    m = Chem.MolFromSmiles(smi) if smi else None
    return Chem.MolToSmiles(m) if m else None


def main() -> None:
    with open_db() as conn:
        cur = conn.cursor()
        print("=" * 100)
        print("【A】tcm.db 里和成分有关的表/列")
        tables = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        print("    表：", ", ".join(tables))
        for t in tables:
            cols = [r[1] for r in cur.execute("PRAGMA table_info(%s)" % t).fetchall()]
            if any(c.lower() in ("smiles", "isomeric_smiles", "canonical_smiles") for c in cols):
                n = cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
                print("    ★ %s（%d 行）：%s" % (t, n, ", ".join(cols)))
        print()
        print("=" * 100)
        print("【B】验收用例逐条：能否从库里按名字取到")
        cases = []
        for name in ("reaction_cases.json", "reaction_cases2.json"):
            p = STAGE / "tools" / name
            if p.exists():
                cases.extend(json.loads(p.read_text(encoding="utf-8")))
        print("    用例总数 = %d" % len(cases))

        # 库里的 name / name_en / smiles 映射
        cols = [r[1] for r in cur.execute("PRAGMA table_info(compounds)").fetchall()]
        ncol = "name_en" if "name_en" in cols else ("name" if "name" in cols else None)
        scol = ("isomeric_smiles" if "isomeric_smiles" in cols else
                "canonical_smiles" if "canonical_smiles" in cols else "smiles")
        print("    用列：name=%s ｜ smiles=%s" % (ncol, scol))
        rows = cur.execute("SELECT %s, %s FROM compounds WHERE %s IS NOT NULL"
                           % (ncol, scol, scol)).fetchall()
    db_by_name = {}
    for nm, smi in rows:
        db_by_name.setdefault(str(nm).strip().lower(), []).append(smi)
    db_canon = {}
    for nm, smi in rows:
        c = canon(smi)
        if c:
            db_canon.setdefault(c, []).append(str(nm))

    hit_name = hit_smi = miss = 0
    diff = []
    for c in cases:
        nm = str(c.get("name") or "").strip()
        smi = str(c.get("smiles") or "")
        cs = canon(smi)
        got = db_by_name.get(nm.lower()) or []
        got_c = [canon(x) for x in got]
        by_name = ("same" if cs in got_c else "diff") if got_c else "none"
        by_smi = db_canon.get(cs) if cs else None
        if by_name == "same":
            hit_name += 1
        elif by_smi:
            hit_smi += 1
        else:
            miss += 1
        if by_name != "same":
            diff.append((c.get("id"), nm, smi, by_name,
                         (by_smi or [])[:3]))
    print("    按名字精确命中（且规范 SMILES 相同）= %d ｜ 名字没对上但 SMILES 在库里 = %d ｜ 库里都没有 = %d"
          % (hit_name, hit_smi, miss))
    print()
    print("    非「名字精确命中」的用例明细（前 40 条）：")
    for cid, nm, smi, how, names in diff[:40]:
        print("      %-26s %-22s %-34s %s  %s"
              % (cid, nm, smi[:34], how, ("库里叫：" + "、".join(names)) if names else ""))


if __name__ == "__main__":
    main()

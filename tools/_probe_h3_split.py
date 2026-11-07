# -*- coding: utf-8 -*-
r"""一次性探针（H3 第二步）：用例里的分子字面量按字段拆分，看在库里的比例。
回答一个问题：把底物改成「数据库取样」最多能减掉多少处手写？
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
        rows = cur.execute("SELECT name_en, isomeric_smiles, inchi_key FROM compounds "
                           "WHERE isomeric_smiles IS NOT NULL").fetchall()
    db_smi = {}
    for nm, smi, ik in rows:
        c = canon(smi)
        if c:
            db_smi.setdefault(c, (str(nm), str(ik)))

    cases = []
    for name in ("reaction_cases.json", "reaction_cases2.json"):
        p = STAGE / "tools" / name
        if p.exists():
            cases.extend(json.loads(p.read_text(encoding="utf-8")))

    print("=" * 100)
    print("用例文件里的分子字面量，按字段拆（共 %d 条用例）" % len(cases))
    print("=" * 100)
    fields = Counter()
    in_db = Counter()
    not_in_db = []
    for c in cases:
        vals = []
        if c.get("smiles"):
            vals.append(("底物 smiles", c["smiles"]))
        for k in ("expect_any", "forbid"):
            for v in (c.get(k) or []):
                vals.append((k, v))
        for f, v in vals:
            c_v = canon(v)
            fields[f] += 1
            if c_v and c_v in db_smi:
                in_db[f] += 1
            else:
                not_in_db.append((f, c.get("id"), v))
    for f, n in fields.most_common():
        print("    %-14s 共 %3d 处 ｜ 在 tcm.db 里 %3d 处 ｜ 不在库里 %3d 处"
              % (f, n, in_db[f], n - in_db[f]))
    print()
    print("「不在库里」的明细（前 30 条）：")
    for f, cid, v in not_in_db[:30]:
        print("    %-14s %-26s %s" % (f, cid, v))

    # 每条用例的底物在不在库里
    print()
    print("=" * 100)
    print("逐条用例：底物是否来自库里")
    print("=" * 100)
    n_yes = n_no = 0
    for c in cases:
        smi = c.get("smiles")
        if not smi:
            print("    %-28s （无底物：%s 用例）" % (c.get("id"), c.get("kind")))
            continue
        c_v = canon(smi)
        got = db_smi.get(c_v)
        if got:
            n_yes += 1
            print("    %-28s ✔ 库里：%-28s %s" % (c.get("id"), got[0][:28], got[1]))
        else:
            n_no += 1
            print("    %-28s ✘ 库里没有（手写）" % c.get("id"))
    print()
    print("    底物在库 = %d ｜ 底物不在库 = %d" % (n_yes, n_no))


if __name__ == "__main__":
    main()

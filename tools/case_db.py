# -*- coding: utf-8 -*-
r"""验收用例的分子**从 tcm.db 取**（第七十五轮 H3）。

用户原则：「不要手写任何数据，数据要用数据库的」——手写 SMILES 已经错过三次
（甘草次酸骨架、大黄素分子式、甘草酸/乌头碱）。所以验收用例里的分子不再手写，
改成**引用数据库里那一行**：

    用例里写 {"db": "<InChIKey>", "name": "<库里名字>"}
    运行时由本模块用**只读**连接把 SMILES 取出来

三条保障：
  1. **找不到就报错**（`KeyError` 带清楚信息），绝不静默退回字面量；
  2. 引用是 **InChIKey**（分子的标准标识符，库里 `compounds.inchi_key` 列有它），
     不是"我抄的 SMILES"；
  3. `same_as(smi)` 供转换脚本用：确认"库里那一行"和"原来手写的那个分子"是同一张结构
     （规范 SMILES 相等），否则不许替换。

自检：``python tools\case_db.py``
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, str(STAGE / "libs"))


def canon(smi: str):
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.error")
    RDLogger.DisableLog("rdApp.warning")
    m = Chem.MolFromSmiles(smi) if smi else None
    return Chem.MolToSmiles(m) if m else None


_BY_KEY: Optional[Dict[str, list]] = None
_BY_CANON: Optional[Dict[str, Tuple[str, str, str]]] = None
_RESOLVED: Dict[str, Tuple[str, str]] = {}


def _build() -> None:
    global _BY_KEY, _BY_CANON
    if _BY_KEY is not None:
        return
    from tcm_ro import open_db
    by_key: Dict[str, list] = {}
    by_canon: Dict[str, Tuple[str, str, str]] = {}
    with open_db() as conn:
        rows = conn.execute(
            "SELECT name_en, isomeric_smiles, inchi_key FROM compounds "
            "WHERE isomeric_smiles IS NOT NULL").fetchall()
    for nm, smi, ik in rows:
        nm, smi, ik = str(nm or ""), str(smi or ""), str(ik or "")
        if not smi:
            continue
        if ik:
            by_key.setdefault(ik, []).append((nm, smi))
        c = canon(smi)
        if c and c not in by_canon:
            by_canon[c] = (nm, ik, smi)
    _BY_KEY, _BY_CANON = by_key, by_canon


def is_charged(smi: str) -> bool:
    from rdkit import Chem
    m = Chem.MolFromSmiles(smi) if smi else None
    if m is None:
        return False
    return any(a.GetFormalCharge() for a in m.GetAtoms())


def by_key(key: str) -> Tuple[str, str]:
    """InChIKey → (库里名字, 库里 SMILES)。找不到**报错**（不静默）。

    ★ 实测（第七十五轮）：同一个 InChIKey 在库里可能有**多行不同写法** ——
      例如苯酚 `ISWSIDIOOBJBQZ-UHFFFAOYSA-N` 有 3 行，第一行是
      `[H+].C1=CC=C(C=C1)[O-]`（名字叫「Iph」，苯酚的**离子写法**）。
      直接取第一行会把底物悄悄换成"苯酚阴离子"，回归里当场挂了两条用例。
      所以这里**优先取电中性的那一行**；若所有写法都带电，才原样使用并**打印警告**。
    """
    _build()
    k = str(key or "").strip()
    if k in _RESOLVED:
        return _RESOLVED[k]
    rows = (_BY_KEY or {}).get(k)
    if not rows:
        raise KeyError("tcm.db 里没有这个 InChIKey：%r（用例引用必须能在库里查到；"
                       "不许悄悄退回手写值）" % k)
    neutral = [r for r in rows if not is_charged(r[1])]
    if neutral:
        pick = neutral[0]
    else:
        pick = rows[0]
        print("   [warn] case_db：InChIKey %s 在库里 %d 行**全是带电写法**，"
              "本次用「%s」（若不该带电请改用手写 lit 并说明）"
              % (k, len(rows), pick[0]))
    _RESOLVED[k] = pick
    return pick


def variants(key: str) -> list:
    """该 InChIKey 在库里的**全部写法**（供审计/报告用，不隐藏任何一行）。"""
    _build()
    return list((_BY_KEY or {}).get(str(key or "").strip(), []))


def ref_of_smiles(smi: str) -> Optional[dict]:
    """给转换脚本用：手写 SMILES → 数据库引用；库里没有则返回 None。"""
    _build()
    c = canon(smi)
    if not c:
        return None
    got = _BY_CANON.get(c)                                 # type: ignore[union-attr]
    if not got:
        return None
    nm, ik, db_smi = got
    return {"db": ik, "name": nm, "same_canonical": True, "db_smiles": db_smi}


def resolve(ref) -> str:
    """用例里的分子字段 → SMILES。

    * ``{"db": "<InChIKey>", ...}`` → 从库里取
    * ``{"lit": "<SMILES>", ...}`` → 库外的小分子（用例里显式标明）
    * 纯字符串 → 当作 ``{"lit": …}``（老格式，仅供过渡）
    """
    if isinstance(ref, str):
        return ref
    if not isinstance(ref, dict):
        raise TypeError("分子字段既不是字符串也不是 dict：%r" % (ref,))
    if ref.get("db"):
        return by_key(ref["db"])[1]
    if ref.get("lit"):
        return str(ref["lit"])
    raise KeyError("分子字段既没有 db 也没有 lit：%r" % (ref,))


def describe(ref) -> str:
    """给打印用：这个分子是库里取的还是字面量。"""
    if isinstance(ref, dict) and ref.get("db"):
        nm, smi = by_key(ref["db"])
        return "库(%s)" % (nm or ref["db"])
    return "字面量"


def _selftest() -> int:
    import json
    _build()
    print("tcm.db 索引：按 InChIKey %d 条 ｜ 按规范 SMILES %d 条"
          % (len(_BY_KEY or {}), len(_BY_CANON or {})))
    for smi in ("O=Cc1ccccc1", "CC(C)=O", "c1ccccc1O"):
        ref = ref_of_smiles(smi)
        print("  %-14s → %s" % (smi, ref))
    p = STAGE / "tools" / "reaction_cases.json"
    if p.exists():
        cases = json.loads(p.read_text(encoding="utf-8"))
        n_db = n_lit = 0
        for c in cases:
            for f in ("smiles",):
                v = c.get(f)
                if isinstance(v, dict):
                    n_db += 1
            for f in ("expect_any", "forbid"):
                for v in (c.get(f) or []):
                    if isinstance(v, dict):
                        n_db += 1
                    else:
                        n_lit += 1
        print("  用例文件 reaction_cases.json：数据库引用 %d 处 ｜ 仍是字符串 %d 处"
              % (n_db, n_lit))
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())

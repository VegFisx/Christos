# -*- coding: utf-8 -*-
"""统一数据库查询工具（HERB + COCONUT 双路线）"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Sequence

ROOT = Path(r"D:\TCMAI")
TCM_DB = ROOT / "tcm.db"
COCONUT_DB = ROOT / "coconut.db"
ALIASES_FILE = ROOT / "data" / "herb_aliases.json"
ALIAS_MAP_FILE = ROOT / "data" / "herb_aliases_map.json"


@contextmanager
def open_db(db_path=TCM_DB):
    conn = sqlite3.connect(str(db_path))
    try:
        yield conn
    finally:
        conn.close()


# ============================================================
# HERB 路线
# ============================================================
def find_herbs(
    herb_kw: str,
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
    db_path=TCM_DB,
) -> List[Tuple[str, str]]:
    with open_db(db_path) as conn:
        cur = conn.cursor()

        # 白名单：精确 IN
        if include:
            ph = ",".join("?" * len(include))
            sql = f"SELECT herb_id, name_cn FROM herbs WHERE name_cn IN ({ph})"
            params = list(include)
            if exclude:
                for e in exclude:
                    sql += " AND name_cn NOT LIKE ?"
                    params.append(f"%{e}%")
            cur.execute(sql, params)
            return cur.fetchall()

        # 1. 精确匹配优先（炮姜、熟地黄、炙甘草 都走这里）
        cur.execute(
            "SELECT herb_id, name_cn FROM herbs WHERE name_cn = ?",
            (herb_kw,)
        )
        rows = cur.fetchall()
        if rows:
            return rows

        # 2. 精确失败 → 前缀匹配（"姜" → "姜xx"）
        cur.execute(
            "SELECT herb_id, name_cn FROM herbs WHERE name_cn LIKE ? "
            "ORDER BY LENGTH(name_cn) LIMIT 10",
            (f"{herb_kw}%",)
        )
        rows = cur.fetchall()
        if rows:
            return rows

        # 3. 还失败 → 模糊兜底
        sql = "SELECT herb_id, name_cn FROM herbs WHERE name_cn LIKE ?"
        params: list = [f"%{herb_kw}%"]
        for e in (exclude or []):
            sql += " AND name_cn NOT LIKE ?"
            params.append(f"%{e}%")
        sql += " ORDER BY LENGTH(name_cn)"
        cur.execute(sql, params)
        return cur.fetchall()


def find_compounds(
    herb_kw: str,
    name_kws: Optional[List[str]] = None,
    priority_names: Optional[List[str]] = None,
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
    limit: int = 300,
    db_path=TCM_DB,
) -> List[Dict]:
    """HERB 路线：按药材名查成分"""
    herb_rows = find_herbs(herb_kw, include=include, exclude=exclude, db_path=db_path)
    if not herb_rows:
        return []

    herb_ids = [h[0] for h in herb_rows]
    ph_herb = ",".join("?" * len(herb_ids))

    if priority_names:
        ph_pri = ",".join("?" * len(priority_names))
        pri_case = f"CASE WHEN c.name_en IN ({ph_pri}) THEN 0 ELSE 1 END"
    else:
        pri_case = "0"

    if name_kws:
        kw_case = "CASE WHEN (" + " OR ".join(
            ["c.name_en LIKE ? OR c.alias LIKE ?" for _ in name_kws]
        ) + ") THEN 0 ELSE 1 END"
    else:
        kw_case = "0"

    sql = f"""
        SELECT
            c.ingredient_id, h.name_cn, c.name_en, c.smiles, c.mol_weight,
            hc.match_level, c.cas_id,
            {pri_case} AS pri_rank, {kw_case} AS kw_rank
        FROM herb_compound hc
        JOIN compounds c ON hc.ingredient_id = c.ingredient_id
        JOIN herbs h ON hc.herb_id = h.herb_id
        WHERE hc.herb_id IN ({ph_herb})
          AND c.smiles IS NOT NULL AND c.smiles != ''
          AND LENGTH(c.smiles) > 3
          AND c.smiles NOT IN ('Not','not','None','none','N/A','NA','nan','NaN')
        ORDER BY
            pri_rank ASC, kw_rank ASC,
            CASE hc.match_level WHEN 'marker' THEN 0 ELSE 1 END ASC,
            c.mol_weight DESC
    """

    params: list = []
    if priority_names:
        params += list(priority_names)
    if name_kws:
        for k in name_kws:
            params += [f"%{k}%", f"%{k}%"]
    params += list(herb_ids)

    with open_db(db_path) as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()

    seen: Dict[str, Dict] = {}
    order: List[str] = []
    for r in rows:
        ing_id = r[0]
        if ing_id not in seen:
            seen[ing_id] = {
                "ingredient_id": ing_id,
                "herb_name": r[1],
                "herb_names": [r[1]],
                "name": r[2],
                "smiles": r[3],
                "mol_weight": r[4],
                "match_level": r[5],
                "cas_id": r[6],
            }
            order.append(ing_id)
        else:
            if r[1] not in seen[ing_id]["herb_names"]:
                seen[ing_id]["herb_names"].append(r[1])

    results = []
    for ing_id in order[:limit]:
        item = seen[ing_id]
        item["herb_names"] = "; ".join(item["herb_names"])
        results.append(item)
    return results


# ============================================================
# COCONUT 路线（按物种拉丁名）
# ============================================================
def find_compounds_coconut(
    species_kws: Sequence[str],
    limit: int = 1000,
    db_path=COCONUT_DB,
) -> List[Dict]:
    if not species_kws:
        return []

    from rdkit import Chem
    from rdkit.Chem import Descriptors

    with open_db(db_path) as conn:
        cur = conn.cursor()
        conditions = " OR ".join(["LOWER(sc.species) LIKE ?" for _ in species_kws])
        params = [f"%{kw.lower()}%" for kw in species_kws]

        sql = f"""
            SELECT DISTINCT c.cnp_id, c.name, c.smiles, c.formula,
                            CAST(c.np_likeness AS REAL) AS npl
            FROM species_compound sc
            JOIN compounds c ON sc.cnp_id = c.cnp_id
            WHERE ({conditions})
              AND c.smiles IS NOT NULL AND c.smiles != ''
              AND c.smiles != 'None'
              AND LENGTH(c.smiles) > 5
            ORDER BY npl DESC NULLS LAST
            LIMIT ?
        """
        params.append(limit)
        cur.execute(sql, params)
        rows = cur.fetchall()

    results = []
    seen_smi = set()
    for cnp_id, name, smiles, formula, _npl in rows:
        if smiles in seen_smi:
            continue
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue
        seen_smi.add(smiles)
        mw = Descriptors.MolWt(mol)
        results.append({
            "ingredient_id": cnp_id,
            "herb_name": "COCONUT",
            "herb_names": "COCONUT",
            "name": name if name and name != "None" else f"CNP_{cnp_id}",
            "smiles": smiles,
            "formula": formula,
            "mol_weight": round(mw, 2),
            "match_level": "coconut",
            "cas_id": None,
        })
    return results


# ============================================================
# 别名表 + 别名映射 + 统一取数入口
# ============================================================
_ALIASES_CACHE: Optional[Dict] = None
_ALIAS_MAP_CACHE: Optional[Dict] = None


def load_herb_aliases(force: bool = False) -> Dict[str, dict]:
    """读取 data/herb_aliases.json（含 include/coconut）"""
    global _ALIASES_CACHE
    if _ALIASES_CACHE is None or force:
        if ALIASES_FILE.exists():
            try:
                with open(ALIASES_FILE, "r", encoding="utf-8") as f:
                    _ALIASES_CACHE = json.load(f)
            except Exception as e:
                print(f"[warn] herb_aliases.json 读取失败: {e}")
                _ALIASES_CACHE = {}
        else:
            print(f"[warn] {ALIASES_FILE} 不存在，走裸药名查询")
            _ALIASES_CACHE = {}
    return _ALIASES_CACHE


def load_herb_alias_map(force: bool = False) -> Dict[str, str]:
    """读取 data/herb_aliases_map.json（别名→标准名）"""
    global _ALIAS_MAP_CACHE
    if _ALIAS_MAP_CACHE is None or force:
        if ALIAS_MAP_FILE.exists():
            try:
                with open(ALIAS_MAP_FILE, "r", encoding="utf-8") as f:
                    _ALIAS_MAP_CACHE = json.load(f)
            except Exception as e:
                print(f"[warn] herb_aliases_map.json 读取失败: {e}")
                _ALIAS_MAP_CACHE = {}
        else:
            _ALIAS_MAP_CACHE = {}
    return _ALIAS_MAP_CACHE


def collect_compounds(herb_specs, herb_limit: int = 200,
                      coconut_limit: int = 1000,
                      return_missed: bool = False):
    """
    统一取数入口：药材 → 成分（HERB + COCONUT 双源，按 smiles 去重）

    herb_specs: list，每项可为：
      - str:  "附子"            → 从 herb_aliases.json 查 include/coconut
      - dict: {"cn": "...", "include": [...], "coconut": [...]}

    return_missed=False（默认）: 返回 list[dict]
    return_missed=True:           返回 (list[dict], missed_list)

    别名处理：
      主名查不到时，尝试 herb_aliases_map.json 映射（如 元参 → 玄参）。
      映射命中时，用原话名字作为 source 标注。
    """
    aliases = load_herb_aliases()
    alias_map = load_herb_alias_map()
    all_c: List[Dict] = []
    missed: List[str] = []

    def _fetch(name, inc, coco):
        """查一个药，返回 (herb_rows, coco_rows)"""
        rows = find_compounds(name, include=inc or None, limit=herb_limit)
        coco_rows = []
        if coco:
            coco_rows = find_compounds_coconut(coco, limit=coconut_limit)
        return rows, coco_rows

    for spec in herb_specs:
        if isinstance(spec, str):
            name = spec
            cfg = aliases.get(name, {})
            inc = cfg.get("include") or []
            coco = cfg.get("coconut") or []
        elif isinstance(spec, dict):
            name = spec.get("cn") or spec.get("name")
            if not name:
                continue
            if "include" in spec or "coconut" in spec:
                inc = spec.get("include") or []
                coco = spec.get("coconut") or []
            else:
                cfg = aliases.get(name, {})
                inc = cfg.get("include") or []
                coco = cfg.get("coconut") or []
        else:
            continue

        rows, coco_rows = _fetch(name, inc, coco)

        # 主名查不到 → 尝试别名映射
        used_name = name
        if not rows and not coco_rows:
            mapped = alias_map.get(name)
            if mapped and mapped != name:
                mcfg = aliases.get(mapped, {})
                rows, coco_rows = _fetch(mapped,
                                         mcfg.get("include") or [],
                                         mcfg.get("coconut") or [])
                if rows or coco_rows:
                    print(f"[alias] {name} → {mapped}  "
                          f"(命中 {len(rows) + len(coco_rows)} 条)")

        for r in rows:
            r["source"] = used_name
            all_c.append(r)
        for r in coco_rows:
            r["source"] = f"{used_name}(COCONUT)"
            all_c.append(r)

        if not rows and not coco_rows:
            missed.append(name)

    seen, uniq = set(), []
    for c in all_c:
        smi = c.get("smiles")
        if not smi or smi in seen:
            continue
        seen.add(smi)
        uniq.append(c)

    if return_missed:
        return uniq, missed
    return uniq
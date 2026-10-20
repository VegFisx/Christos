# -*- coding: utf-8 -*-
"""
chemreact 数据源：从 tcm.db 只读取成分
======================================

复用 `D:\\TCMAI\\src\\db_utils.py` 的数据，但**不改它、不 import 它**——
那边的模块一 import 就会连带拉起 rdkit 之外的依赖，且路径是硬编码的。
这里只做只读 SQL，保持核心引擎独立。

**全程只读**：`file:...?mode=ro`，不会写数据库。
"""

from __future__ import annotations

import difflib
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent
for _p in (_STAGE / "core",):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from engine import Compound  # noqa: E402

DEFAULT_DB = r"D:\TCMAI\tcm.db"
# ★ 最近一次解析命中信息（给桥接打印用）：{"query":…, "matched":…, "how":…}
LAST_RESOLVE: Dict[str, str] = {}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _resolve_herb_ids(cur, name: str):
    """中文名（精确/模糊）→ 药典拉丁·英文名·别名 → 近似(difflib) 多路解析。

    返回 [(herb_id, name_cn, how)]。
    ★ 第七十四轮：**拼音这一路已删除**（用户 2026-10-15 决定）——中文用户直接打汉字，
    外文用户打拉丁学名，中间夹一层拼音没有真实用户，反而制造错命中（实测 ``gancao``
    曾命中「秤杆草」chenggancao）。物种学名走 ``sources/coconut.py``，不在这里。
    """
    hits = []
    cur.execute("SELECT herb_id, name_cn FROM herbs WHERE name_cn = ?", (name,))
    hits = [(r[0], r[1], "中文精确") for r in cur.fetchall()]
    if hits:
        return hits
    # ★ 炮制品闸（用户 2026-10-16）：药典收载的炮制品是**独立药材**，
    #   库里有就用它、库里没有就如实报"库缺"——**绝不**拆成基原或走别名/模糊。
    try:
        import processed as PR
        if PR.is_processed(name):
            return []
    except Exception as ex:                     # noqa: BLE001 —— 打印，不静默
        print("   [warn] 炮制品闸查询失败：%s: %s" % (type(ex).__name__, ex))
    # ★ 别名（NTU《中文药名同义词表》+ herbs.alias，**多候选**）—— 排在"中文模糊"
    #   **之前**：别名有辞典依据，而"字面包含"常常是误配。
    #   实测：`龙胆草` 若走字面包含会给出「滇龙胆草/德国龙胆草」，
    #   而别名表说得清楚 —— 它是「龙胆」等 6 个候选。多个候选**全部返回**，不替用户猜。
    try:
        import alias_index as AI
        hit = [(c["herb_id"], c["canonical"], "别名") for c in AI.in_db(name)]
        if hit:
            return hit
    except Exception as ex:                     # noqa: BLE001 —— 打印，不静默
        print("   [warn] 别名索引查询失败：%s: %s" % (type(ex).__name__, ex))
    # ★ **人工审定**的异名（第七十五轮）：必须排在"中文模糊/字面包含"**之前** ——
    #   实测 `黄耆` 若走模糊会命中「巨圆叶黄耆」（另一种药），而审定表说它就是 黄芪。
    try:
        import alias_curated as AC
        canon = AC.resolve(name)
        if canon:
            hit = [(r[0], r[1], "别名(审定)") for r in
                   cur.execute("SELECT herb_id, name_cn FROM herbs WHERE name_cn = ?",
                               (canon,)).fetchall()]
            if hit:
                return hit
    except Exception as ex:                     # noqa: BLE001 —— 打印，不静默
        print("   [warn] 审定异名表查询失败：%s: %s" % (type(ex).__name__, ex))
    cur.execute("SELECT herb_id, name_cn FROM herbs WHERE name_cn LIKE ? "
                "ORDER BY LENGTH(name_cn) LIMIT 40", ("%" + name + "%",))
    hits = [(r[0], r[1], "中文模糊") for r in cur.fetchall()]
    if hits:
        return hits
    q = _norm(name)
    if not q:
        return []
    # ★ 第七十四轮：拼音这一路已删除（见函数 docstring 的说明）。
    cur.execute("SELECT herb_id, name_cn, COALESCE(latin,''), COALESCE(name_en,''), "
                "COALESCE(alias,'') FROM herbs")
    rows2 = cur.fetchall()
    hits = [(i, cn, "外文名") for i, cn, la, en, al in rows2
            if q in _norm(la) or q in _norm(en) or q in _norm(al)]
    if hits:
        return hits
    best = (0.0, None, None)
    for i, cn, la, en, al in rows2:
        for s in (la, en, al, cn):
            ns = _norm(s)
            if not ns:
                continue
            r = difflib.SequenceMatcher(None, q, ns).ratio()
            if r > best[0]:
                best = (r, i, cn)
    if best[0] >= 0.85:
        return [(best[1], best[2], "近似(%.2f)" % best[0])]
    return []


def _connect(db_path: str) -> sqlite3.Connection:
    r"""只读连接：先 mode=ro；打不开（WAL 无 -shm / 有活跃写者）就回退 immutable=1。

    ★ 第七十五轮修的 bug：用户库处于 WAL 活跃状态时，`mode=ro` 会
    `unable to open database file`，整条药材解析崩掉。回退仍是**纯只读**。
    """
    uri = f"file:{db_path}"
    try:
        conn = sqlite3.connect(uri + "?mode=ro", uri=True)
        conn.execute("SELECT 1")
        return conn
    except sqlite3.OperationalError as ex:
        print("   [warn] herb: mode=ro 打不开（%s）→ 回退 immutable=1（只读快照）" % ex)
        return sqlite3.connect(uri + "?immutable=1", uri=True)


def list_herbs(keyword: str, db_path: str = DEFAULT_DB,
               limit: int = 20) -> List[Dict[str, str]]:
    """按中文名模糊找药材。精确匹配排最前。"""
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT herb_id, name_cn FROM herbs WHERE name_cn LIKE ? "
            "ORDER BY CASE WHEN name_cn = ? THEN 0 ELSE 1 END, LENGTH(name_cn) "
            "LIMIT ?",
            (f"%{keyword}%", keyword, limit),
        )
        return [{"herb_id": r[0], "name_cn": r[1]} for r in cur.fetchall()]
    finally:
        conn.close()


def compounds_of_herb(herb_name: str, db_path: str = DEFAULT_DB,
                      limit: int = 200,
                      include: Optional[Sequence[str]] = None,
                      chp_first: bool = False,
                      order_tcmsp: bool = False,
                      ) -> List[Compound]:
    """取一味药的全部成分（HERB 库）。按 marker 优先、分子量降序。

    ★ chp_first（默认 False）：打开时按"药典判据优先"重排——Tier-0（药典含量测定成分）
      在前、同 Tier 按限量值降序，其余保持原序；排序依据可回溯（chp_priority 模块）。
    """
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        if include:
            ph = ",".join("?" * len(include))
            cur.execute(
                f"SELECT herb_id FROM herbs WHERE name_cn IN ({ph})", list(include))
            ids = [r[0] for r in cur.fetchall()]
        else:
            # ★ 第七十四轮：多路解析（中文精确/模糊 → 药典拉丁·英文名·别名 → 近似兜底）
            resolved = _resolve_herb_ids(cur, herb_name)
            ids = [h[0] for h in resolved]
            LAST_RESOLVE.clear()
            if resolved:
                LAST_RESOLVE.update({"query": herb_name, "matched": resolved[0][1],
                                     "how": resolved[0][2], "n_hits": str(len(resolved))})
            else:
                LAST_RESOLVE.update({"query": herb_name, "matched": "", "how": "",
                                     "n_hits": "0"})
        if not ids:
            return []

        ph = ",".join("?" * len(ids))
        cur.execute(
            f"""
            SELECT c.ingredient_id, c.name_en, c.smiles, c.isomeric_smiles, c.mol_weight,
                   h.name_cn, hc.match_level, c.ob_score, c.drug_likeness
            FROM herb_compound hc
            JOIN compounds c ON hc.ingredient_id = c.ingredient_id
            JOIN herbs h ON hc.herb_id = h.herb_id
            WHERE hc.herb_id IN ({ph})
              AND c.smiles IS NOT NULL AND c.smiles != ''
              AND LENGTH(c.smiles) > 3
              AND c.smiles NOT IN ('Not','not','None','none','N/A','NA','nan','NaN')
            ORDER BY
              CASE hc.match_level WHEN 'marker' THEN 0 ELSE 1 END,
              c.mol_weight DESC
            """,
            ids,
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    out: List[Compound] = []
    seen = set()
    for ing_id, name_en, smiles, iso_smiles, mw, herb_cn, _lvl, _ob, _dl in rows:
        # ★ 优先用 isomeric_smiles ★
        # 实测：compounds 表 31646 行里有 19043 行（60%）的 isomeric_smiles
        # 含手性标记 @，21376 行的两列不同。只读 smiles 等于把手性信息扔掉。
        # 而中药成分（糖苷、萜类、生物碱）恰恰是手性重灾区。
        # 拿不到异构 SMILES 时才退回普通 SMILES。
        use = (iso_smiles or "").strip()
        if not use or use in ("Not", "not", "None", "none", "N/A", "NA"):
            use = (smiles or "").strip()
        if not use:
            continue
        smiles = use

        if smiles in seen:
            continue
        seen.add(smiles)
        c = Compound(smiles=smiles,
                     name=(name_en or "").strip() or smiles[:24],
                     herb=herb_cn or herb_name,
                     source="herb")
        c.chp = None
        # ★ C（用户 2026-10-16）：带出 TCMSP 的 OB / DL。**默认只当信息列，不参与取舍**；
        #   只有显式 order_tcmsp=True 时才用它排序。口径：OB≥30% 且 DL≥0.18（TCMSP 经典）。
        for _attr, _raw in (("ob", _ob), ("dl", _dl)):
            try:
                setattr(c, _attr, float(_raw) if _raw not in (None, "") else None)
            except (TypeError, ValueError):
                setattr(c, _attr, None)
        c.tcmsp = bool(c.ob is not None and c.ob >= 30
                       and c.dl is not None and c.dl >= 0.18)
        out.append(c)

    if chp_first:
        chp = {}
        try:
            from chp_priority import load_map          # sources/ 在同一 sys.path 下
            chp = load_map().get(herb_name) or {}
        except Exception as ex:                        # 打印，不静默
            print("   [warn] 药典优先排序加载失败，退回原序：%s: %s" % (type(ex).__name__, ex))
        if chp:
            # out 与 rows 的"去重后"顺序一一对应：重建 ingredient_id 列表
            id_list, seen2 = [], set()
            for ing_id, _n, smi, iso, _mw, _h, _l, _ob, _dl in rows:
                use = (iso or "").strip()
                if not use or use in ("Not", "not", "None", "none", "N/A", "NA"):
                    use = (smi or "").strip()
                if use and use not in seen2:
                    seen2.add(use)
                    id_list.append(ing_id)
            for c, iid in zip(out, id_list):
                c.chp = chp.get(iid)
            indexed = list(enumerate(out))

            def _key(pair):
                i, c = pair
                info = getattr(c, "chp", None)
                if info:
                    return (0, info[0], -float(info[1] or 0), i)
                return (1, 0, 0.0, i)

            indexed.sort(key=_key)
            out = [c for _, c in indexed]
    if order_tcmsp:
        # ★ 只**排序**，不筛选：有 OB 的按 OB 降序，没有 OB 的一律排在后面（保持原相对序）。
        out.sort(key=lambda c: (0 if getattr(c, "ob", None) is not None else 1,
                                -(getattr(c, "ob", None) or 0.0)))
    return out[:limit]


def list_named_herbs(keyword: str, db_path: str = DEFAULT_DB,
                     limit: int = 40) -> List[Dict[str, Any]]:
    """按中文名子串列出**同字段的全部条目** —— 给桥接层的**查找窗口**用。

    用户 2026-10-15 要求：中文名也该有个查找窗口，把同字段的条目摆出来让人挑，例如

        甘草  -> 甘草 / 炙甘草 / 甘草节 / 甘草稍 / 甘草头 / 光果甘草…
        柴胡  -> 柴胡 / 南柴胡 / 北柴胡 / 银柴胡…

    返回 ``[{"herb_id","name_cn","n_compounds","latin","name_en"}]``。
    排序：**精确名在前**，其次名字短的，最后按 herb_id。
    成分数用 LEFT JOIN 数（没有成分的条目也列出、标 0 —— 让人看见"库里就是没有"，
    而不是"我把它藏起来了"）。``latin``/``name_en`` 带出来是为了让调用方再去
    COCONUT 里确认这批药材对应的**基元植物**（物种）。
    """
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT h.herb_id, h.name_cn,
                   COUNT(DISTINCT CASE
                       WHEN c.isomeric_smiles IS NULL OR c.isomeric_smiles IN
                            ('', 'Not', 'not', 'None', 'none', 'N/A', 'NA')
                       THEN c.smiles ELSE c.isomeric_smiles END),
                   COALESCE(h.latin, ''), COALESCE(h.name_en, '')
            FROM herbs h
            LEFT JOIN herb_compound hc ON hc.herb_id = h.herb_id
            LEFT JOIN compounds c
                   ON c.ingredient_id = hc.ingredient_id
                  AND c.smiles IS NOT NULL AND LENGTH(c.smiles) > 3
            WHERE h.name_cn LIKE ?
            GROUP BY h.herb_id, h.name_cn
            ORDER BY CASE WHEN h.name_cn = ? THEN 0 ELSE 1 END,
                     LENGTH(h.name_cn), h.herb_id
            LIMIT ?
            """,
            ("%" + keyword + "%", keyword, limit),
        )
        return [{"herb_id": r[0], "name_cn": r[1], "n_compounds": int(r[2]),
                 "latin": r[3] or "", "name_en": r[4] or ""}
                for r in cur.fetchall()]
    finally:
        conn.close()


def list_latin_herbs(text: str, db_path: str = DEFAULT_DB,
                     limit: int = 20) -> List[Dict[str, Any]]:
    """按**药材拉丁名 / 英文名 / 别名**列出命中的药材条目（给「查找相似」用）。

    用户 2026-10-16 要求：查找窗口要能回答"这个拉丁名到底对应哪几条药材"，
    并区分"独苗"与"根本没收录"。返回结构与 ``list_named_herbs`` 一致。
    """
    q = _norm(text)
    if len(q) < 4:
        return []
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        counts: Dict[str, int] = {}
        cur.execute(
            """
            SELECT hc.herb_id,
                   COUNT(DISTINCT CASE
                       WHEN c.isomeric_smiles IS NULL OR c.isomeric_smiles IN
                            ('', 'Not', 'not', 'None', 'none', 'N/A', 'NA')
                       THEN c.smiles ELSE c.isomeric_smiles END)
            FROM herb_compound hc
            JOIN compounds c ON c.ingredient_id = hc.ingredient_id
            WHERE c.smiles IS NOT NULL AND LENGTH(c.smiles) > 3
            GROUP BY hc.herb_id
            """)
        for hid, n in cur.fetchall():
            counts[hid] = int(n)
        cur.execute("SELECT herb_id, name_cn, COALESCE(latin, ''), "
                    "COALESCE(name_en, ''), COALESCE(alias, '') FROM herbs")
        rows = cur.fetchall()
    finally:
        conn.close()
    hits = []
    for hid, cn, la, en, al in rows:
        if q in _norm(la) or q in _norm(en) or q in _norm(al):
            hits.append((0 if q == _norm(la) else 1, len(cn or ""), hid, cn))
    hits.sort(key=lambda t: (t[0], t[1], t[2]))
    return [{"herb_id": hid, "name_cn": cn, "n_compounds": counts.get(hid, 0),
             "latin": "", "name_en": ""} for _r, _l, hid, cn in hits[:limit]]


def find_named_compound(keyword: str, db_path: str = DEFAULT_DB,
                        limit: int = 10) -> List[Compound]:
    """按英文名找成分（用于挑演示用的标志性分子，如 aconitine）。"""
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            # 同样优先 isomeric_smiles——手性信息不能丢
            "SELECT name_en, smiles, isomeric_smiles FROM compounds "
            "WHERE name_en LIKE ? AND smiles IS NOT NULL AND smiles != '' LIMIT ?",
            (f"%{keyword}%", limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    out = []
    for n, s, iso in rows:
        use = (iso or "").strip() or (s or "").strip()
        if use:
            out.append(Compound(smiles=use, name=n, herb="(直接指定)",
                                source="user"))
    return out


def compounds_from_smiles(smiles_list: Sequence[str]) -> List[Compound]:
    """通用 SMILES 入口（简报 §5 的"通用 SMILES 入口"）。"""
    return [Compound(smiles=s, name=f"SMILES_{i+1}", herb="(用户输入)", source="user")
            for i, s in enumerate(smiles_list)]

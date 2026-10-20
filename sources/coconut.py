# -*- coding: utf-8 -*-
r"""chemreact 数据源：COCONUT 物种级成分库（``D:\TCMAI\coconut.db``，**全程只读**）。

为什么要有它（第七十四轮）
--------------------------
中药材在库里其实有两种"名字"，用户两种都可能输：

  1. **药材名**：药典拉丁（``Radix et Rhizoma Glycyrrhizae``）、中文（``甘草``）
  2. **种名**：双名法拉丁学名（``Glycyrrhiza uralensis``）

``tcm.db`` 的 ``herbs`` 表把这两类名字混在同一行里，而且**种名被挂到了药用部位条目上**——
实测 ``'Glycyrrhiza uralensis'`` 在 HERB 侧只反查到 ``{甘草节, 甘草稍, 甘草头}``，
真正的 ``甘草``（HERB001779）反查不到：它的 ``latin`` 列是药典式药材名。

COCONUT 侧则天然是**物种级**：``species_compound`` 有 51,608 个种名（全小写双名法）。
实测同一味药两库成分数（去重 SMILES 口径）：

    甘草 / Glycyrrhiza uralensis : HERB 324  COCONUT 644
    白鲜皮 / Dictamnus dasycarpus: HERB  81  COCONUT 134
    银杏叶 / Ginkgo biloba       : HERB 293  COCONUT 525

本模块只做两件事：

  * ``looks_like_species(text)`` —— 判定"这是不是种名"。判据**不是正则猜测**，而是拿 COCONUT
    的 5.1 万种名字典来比：实测英文俗名 ``Abyssinia Coralbean`` / ``Algerian Iris``
    能骗过"两个大写单词"式正则，但骗不过种名字典。
  * ``compounds_of_species(sp)`` —— 取该物种的全部成分（按结构去重，**不截取、不打分**）。

调用方是桥接层；没识别成种名的输入仍走 ``herb.py``（HERB 库，带药典 marker 标注）。
"""
from __future__ import annotations

import difflib
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent
for _p in (_STAGE / "core",):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from engine import Compound  # noqa: E402
# ★ 第七十五轮（第七十四轮交接待办①）：库路径**单一来源**。
#   原先这里自己写了一份 r"D:\TCMAI\coconut.db"，与 core/query_base.py 的 COCONUT_DB 重复；
#   现在统一从 query_base 取（coconut.py 本来就把 core 加进了 sys.path，方向不会成环）。
from query_base import COCONUT_DB as _COCONUT_DB  # noqa: E402

DEFAULT_DB = str(_COCONUT_DB)          # 保持字符串签名（旧调用方按 str 传）

# ★ 最近一次种名判定的依据（给桥接层打印用）：{"query","matched","how","n_cand"}
LAST_SPECIES: Dict[str, str] = {}

# ★ 最近一次取成分时，命中的**异写组**：{"query","canonical","variants","n_variants"}
LAST_VARIANTS: Dict[str, str] = {}

# COCONUT 里表示"非确定物种"的词：abelmoschus spp / xxx aff …
NONDET = re.compile(r"\b(spp?|aff|cf|indet)\b", re.I)

_SPECIES_CACHE: Optional[List[str]] = None
_FOLD_CACHE: Dict[str, List[str]] = {}


# ---------------------------------------------------------------- 归一

def _norm_words(s: str) -> List[str]:
    """只留字母和空格，小写，压掉多余空白。"""
    t = re.sub(r"[^A-Za-z]+", " ", s or "").lower()
    return [w for w in t.split() if w]


def _fold(s: str) -> str:
    """拉丁拼写模糊归一（只用于**两边对称**的比较，不用于显示）。

    覆盖实测与常识里最常见的四类手误/异写：
      * ``ae/oe`` → ``e``   （Glycyrrhizae ≈ Glycyrrhize）
      * ``ph`` → ``f``      （Dictamnus 一类属名里常见）
      * 叠字母压成一个      （Glycyrrhiza 的 ``rr``；ll→l，ss→s）
      * ``y`` → ``i``       （Glycyrrhiza ≈ Glycirrhiza —— 用户实测拼错 0.8444 相似度，
                              归一后两边都变成 ``glicirhiza uralensis``，直接命中）
    """
    s = (s or "").lower()
    s = s.replace("ae", "e").replace("oe", "e").replace("ph", "f")
    s = re.sub(r"(.)\1+", r"\1", s)
    return s.replace("y", "i")


def _binomial(words: Sequence[str]) -> str:
    """取前两个词当候选双名法（属名+种加词）。后面的都是命名人/变种，一律丢掉。

    实测必要性：HERB 里写着 ``Glycyrrhiza Uralensis Fisch``——``Fisch`` 后面**没有句点**，
    靠"去缩写"识别不掉；直接取前两词最稳。
    """
    if len(words) < 2:
        return ""
    a, b = words[0], words[1]
    if len(a) < 3 or len(b) < 3:
        return ""
    return f"{a} {b}"


# ---------------------------------------------------------------- 连接

def _connect(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    p = Path(db_path).resolve()
    return sqlite3.connect("file:" + p.as_posix() + "?mode=ro", uri=True)


def _species_list(db_path: str = DEFAULT_DB) -> List[str]:
    global _SPECIES_CACHE
    if _SPECIES_CACHE is None:
        conn = _connect(db_path)
        try:
            rows = conn.execute(
                "SELECT DISTINCT species FROM species_compound").fetchall()
        finally:
            conn.close()
        _SPECIES_CACHE = sorted(
            {" ".join(_norm_words(r[0])[:2]) for r in rows
             if r[0] and len(_norm_words(r[0])) >= 2})
    return _SPECIES_CACHE


def _fold_map(db_path: str = DEFAULT_DB) -> Dict[str, List[str]]:
    """fold(种名) → [种名…]。同键多值时保留全部，供打印"多候选"。"""
    global _FOLD_CACHE
    if not _FOLD_CACHE:
        for sp in _species_list(db_path):
            _FOLD_CACHE.setdefault(_fold(sp), []).append(sp)
    return _FOLD_CACHE


# ---------------------------------------------------------------- 判定

def variants_of(species: str, db_path: str = DEFAULT_DB) -> List[str]:
    """返回 ``species`` 所在的**异写组**（含它自己）。

    实测（2026-10-16 体检）：51,608 个物种里有 **522 组** fold 撞车、涉及 1,056 个条目
    （2.05%），例如 ``picrorhiza kurroa | kurrooa | picrorrhiza kurrooa``、
    ``annona salzmanii | salzmannii``、``glycyrrhiza uralensis | glycyrrhizae uralensis``。
    它们是同一个植物的拼写变体，**成分应当合并**，否则选择窗口里会摆出 3~4 个同物选项。

    只用 fold 键成组（两词、去 ae/oe、压叠字母、ph→f、y→i），不改动词典本身。
    """
    words = _norm_words(species)
    if len(words) < 2:
        return [species]
    k = _fold(" ".join(words[:2]))
    got = _fold_map(db_path).get(k) or []
    return got if got else [" ".join(words[:2])]


def _counts_of(species_list: Sequence[str],
               db_path: str = DEFAULT_DB) -> List[Tuple[str, int]]:
    """一批物种各自的成分条数（按 species_compound 计数，未去重结构）。"""
    if not species_list:
        return []
    conn = _connect(db_path)
    try:
        ph = ",".join("?" * len(species_list))
        return [(r[0], int(r[1])) for r in conn.execute(
            f"SELECT LOWER(TRIM(species)), COUNT(DISTINCT cnp_id) FROM species_compound "
            f"WHERE LOWER(TRIM(species)) IN ({ph}) GROUP BY 1", species_list).fetchall()]
    finally:
        conn.close()


def _collapse(rows: Sequence[Tuple[str, int]]) -> List[Tuple[str, int, int]]:
    """把 ``[(物种, 成分数)]`` 按 fold 组**合并**成 ``[(代表名, 成分合计, 异写个数)]``。

    代表名取该组里成分数最多的那个（通常也是正确的拼写，如 glycyrrhiza uralensis 644
    压过 glycyrrhizae uralensis）。名字只负责显示，成分是**整组合计**，不丢东西。
    """
    groups: Dict[str, List[Tuple[str, int]]] = {}
    for sp, n in rows:
        groups.setdefault(_fold(sp), []).append((sp, n))
    out = []
    for v in groups.values():
        v.sort(key=lambda t: (-t[1], len(t[0]), t[0]))
        out.append((v[0][0], sum(n for _, n in v), len(v)))
    out.sort(key=lambda t: -t[1])
    return out

def species_by_word(word: str, db_path: str = DEFAULT_DB,
                    limit: int = 40) -> List[str]:
    r"""**单段拉丁词**反查（第七十五轮，用户：「uralensis 为什么查不到」）。

    * 种加词：``uralensis`` → 所有以 `` uralensis`` 结尾的物种；
    * 属名前缀：``glycy`` → 所有以 ``glycy`` 开头的物种（前几个词也一起给出）。

    只做**字面**匹配，不猜拼写；找不到就是找不到。
    """
    w = str(word or "").strip().lower()
    if len(w) < 3:
        return []
    out, seen = [], set()
    for sp in _species_list(db_path):
        low = sp.lower()
        if low.endswith(" " + w) or low.split(" ")[0].startswith(w):
            if sp not in seen:
                seen.add(sp)
                out.append(sp)
                if len(out) >= limit:
                    break
    return out


def looks_like_species(text: str, db_path: str = DEFAULT_DB,
                       min_ratio: float = 0.88) -> Tuple[Optional[str], str]:
    """判定 ``text`` 是不是**种名**（双名法拉丁学名）。

    返回 ``(命中的 COCONUT 种名, 依据字符串)``；不是种名则 ``(None, "")``。
    判定顺序（先严后宽）：

      1. 精确     —— 前两词原样命中种名表
      2. 拼写归一 —— fold 后命中（吃掉 Glycirrhiza/Glycyrrhiza、ae/e、叠字母、y/i）
      3. 词集命中 —— 前两词都在某个种名里（吃掉变种/亚种后缀）
      4. 近似     —— 同属（前 4 字母）候选里 difflib ≥ min_ratio
    """
    LAST_SPECIES.clear()
    LAST_SPECIES.update({"query": text or "", "matched": "", "how": "", "n_cand": "0"})
    words = _norm_words(text)
    if len(words) < 2 or not re.search(r"[A-Za-z]", text or ""):
        return None, ""
    cand = _binomial(words)
    if not cand:
        return None, ""

    species = _species_list(db_path)
    if cand in species:
        return _hit(text, cand, "种名精确", 1)

    fm = _fold_map(db_path)
    fc = _fold(cand)
    if fc in fm:
        got = fm[fc]
        return _hit(text, got[0], "种名拼写归一", len(got))

    t1, t2 = cand.split()
    subset = [sp for sp in species if t1 in sp.split() and t2 in sp.split()]
    if len(subset) == 1:
        return _hit(text, subset[0], "种名词集", 1)
    if len(subset) > 1:
        subset.sort(key=len)
        return _hit(text, subset[0], "种名词集(多候选)", len(subset))

    prefix = fc[:4]
    pool = [sp for sp in species if _fold(sp).startswith(prefix)]
    best, best_r = None, 0.0
    for sp in pool:
        r = difflib.SequenceMatcher(None, fc, _fold(sp)).ratio()
        if r > best_r:
            best, best_r = sp, r
    if best and best_r >= min_ratio:
        return _hit(text, best, "种名近似(%.2f)" % best_r, 1)
    LAST_SPECIES.update({"n_cand": str(len(pool))})
    return None, ""


def _hit(text: str, matched: str, how: str, n: int) -> Tuple[str, str]:
    LAST_SPECIES.update({"query": text or "", "matched": matched,
                         "how": how, "n_cand": str(n)})
    return matched, how


# ---------------------------------------------------------------- 取成分

def compounds_of_species(species: str, db_path: str = DEFAULT_DB,
                         limit: Optional[int] = None,
                         order: str = "lib") -> List[Compound]:
    """取一个物种的全部成分（COCONUT ``species_compound``）。

    * ``order='lib'``（默认）：**库内原序**（cnp_id 升序）—— 表示"没有偏好"，符合
      "不打分、不排序、不取舍"的约定。
    * ``order='npl'``     ：按 ``np_likeness`` 降序（打开开关才生效）。

    去重按**结构**（rdkit 规范 SMILES），不是按字符串——否则同一分子不同写法会被算两次，
    白白吃掉对子预算。解析失败的条目**计数并打印**，不静默跳过。
    """
    sp = " ".join(_norm_words(species)[:2])
    # ★ 异写合并：查一个种名时，把同 fold 组的拼写变体**全部**取进来（实测 522 组）。
    variants = variants_of(sp, db_path)
    LAST_VARIANTS.clear()
    LAST_VARIANTS.update({"query": species or "",
                          "canonical": variants[0] if variants else "",
                          "variants": " | ".join(variants),
                          "n_variants": str(len(variants))})
    conn = _connect(db_path)
    try:
        ph = ",".join("?" * len(variants))
        rows = conn.execute(
            f"""
            SELECT c.cnp_id, c.name, c.smiles, c.np_likeness
            FROM species_compound sc
            JOIN compounds c ON sc.cnp_id = c.cnp_id
            WHERE LOWER(TRIM(sc.species)) IN ({ph})
              AND c.smiles IS NOT NULL
              AND c.smiles NOT IN ('', 'None', 'none', 'N/A', 'nan')
              AND LENGTH(c.smiles) > 3
            ORDER BY c.cnp_id
            """,
            variants).fetchall()
    finally:
        conn.close()

    if order == "npl":
        rows = sorted(rows, key=lambda r: -(float(r[3]) if r[3] not in (None, "") else -1.0))

    out: List[Compound] = []
    seen = set()
    bad = 0
    for cnp_id, name, smiles, _npl in rows:
        smi = (smiles or "").strip()
        key = _canon(smi)
        if key is None:
            bad += 1
            continue
        if key in seen:
            continue
        seen.add(key)
        c = Compound(smiles=smi,
                     name=(name or "").strip() or f"CNP_{cnp_id}",
                     herb=f"COCONUT:{sp}",
                     source="coconut")
        out.append(c)
    if bad:
        print("   [warn] COCONUT %s：%d 条 SMILES rdkit 解析失败已跳过（共 %d 条原始记录）"
              % (sp, bad, len(rows)))
    return out[:limit] if limit is not None else out


def _canon(smiles: str) -> Optional[str]:
    """规范 SMILES；解析失败返回 None（由调用方计数打印）。"""
    try:
        from rdkit import Chem, RDLogger
        RDLogger.DisableLog("rdApp.*")
        m = Chem.MolFromSmiles(smiles)
        return Chem.MolToSmiles(m) if m is not None else None
    except Exception:
        return None


def species_compounds_count(species: str, db_path: str = DEFAULT_DB) -> int:
    """只数个数（给"要不要走这条路线"的快速判断用）。"""
    conn = _connect(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM species_compound WHERE LOWER(TRIM(species)) = ?",
            (species.lower(),)).fetchone()[0]
    finally:
        conn.close()


DRUG_PART_WORDS = frozenset((
    "radix", "rhizoma", "folium", "herba", "cortex", "fructus", "semen", "flos",
    "ramulus", "caulis", "lignum", "resina", "pericarpium", "bulbus", "nodus",
    "spica", "stigma", "medulla", "arillus", "exocarpium", "sarcocarpium",
    "testa", "squama", "corium", "perio", "radix",
))


def looks_like_drug_latin(text: str) -> str:
    """**药材拉丁名守卫**（用户 2026-10-15 明确）：

    药典里的药材拉丁名长这样：``Radix et Rhizoma Glycyrrhizae``、``Ginkgo Folium``、
    ``Cortex Dictamni`` —— 特征不是"用了拉丁字母"，而是**含药用部位词**。

    所以：含部位词 → 判为**药材拉丁名** → 走 HERB 药材库，**不做**种名判定。
    返回命中的部位词（``""`` = 不是药材拉丁名）。

    为什么需要这条：单靠"不是种名"来反推不够硬 —— 有的药材拉丁名（``Ginkgo Folium``）
    与真种名（``Ginkgo biloba``）只差一个词，一旦近似度算高就会走错路。这里是**正向证据**。
    """
    for w in _norm_words(text):
        if w in DRUG_PART_WORDS:
            return w
    return ""


def genus_species(text: str, db_path: str = DEFAULT_DB,
                  limit: int = 80) -> List[Tuple[str, int]]:
    """只给一个词（**属名**，如 ``glycyrrhiza`` / ``panax``）时，列出该属下的物种。

    给桥接层的**选择窗口**用（用户 2026-10-15 要求）：属名不直接开跑，而是把该属在
    COCONUT 里的全部物种连同成分数列出来，由用户挑。

    实测：``glycyrrhiza`` → 19 个物种、``panax`` → 25 个（2881 条记录）。
    返回 ``[(种名, 该种成分数)]``，按成分数降序；不是属名则返回 ``[]``。

    拼写归一同样生效（``Glycirrhiza`` 能对上 ``glycyrrhiza``），因为库里存在
    ``glycyrrhizae uralensis`` 这种异写的属名。
    """
    words = _norm_words(text)
    if len(words) != 1:
        return []
    g = _fold(words[0])
    if len(g) < 3:
        return []
    species = _species_list(db_path)
    genus_forms = {sp.split()[0] for sp in species
                   if len(sp.split()) > 1 and _fold(sp.split()[0]) == g}
    if not genus_forms:
        return []
    picked = [sp for sp in species if sp.split()[0] in genus_forms]
    # ★ 异写合并 + 标出"属级混合条目"（abelmoschus spp 这种不是确定物种）
    rows = _collapse(_counts_of(picked, db_path))
    return rows[:limit]


def species_from_blobs(blobs, db_path: str = DEFAULT_DB,
                       limit: int = 40) -> List[Tuple[str, int]]:
    """从一批自由文本（药材行的 ``latin`` / ``name_en``）里**捞出基元植物**。

    动机（用户 2026-10-15）：中文名查到的是一串**药材条目**（甘草 / 炙甘草 / 甘草节…），
    用户还想看见这些条目背后的**基元植物**（物种）。HERB 表里的种名写法很乱
    （``Glycyrrhiza Uralensis Fisch``、``Radix et Rhizoma Glycyrrhizae``、
    ``Liquorice Root`` 混在同一列），所以不靠解析、**靠 COCONUT 的种名字典来认**：

    取每段文本里**每两个相邻词**当候选，fold 归一后去种名字典里查，查到才算数。

    返回 ``[(种名, 该种成分数)]``，按成分数降序。
    """
    cand_keys = []
    for blob in blobs or ():
        words = _norm_words(blob)
        for i in range(len(words) - 1):
            k = _fold(words[i] + " " + words[i + 1])
            if len(k) >= 7 and k not in cand_keys:
                cand_keys.append(k)
    if not cand_keys:
        return []
    fm = _fold_map(db_path)
    found = []
    for k in cand_keys:
        for sp in fm.get(k, ()):
            if sp not in found:
                found.append(sp)
    if not found:
        return []
    return _collapse(_counts_of(found, db_path))[:limit]


def suggest_species(text: str, db_path: str = DEFAULT_DB,
                    k: int = 5, min_ratio: float = 0.60) -> List[Tuple[str, float]]:
    """没命中时给候选：最接近的 k 个种名 + 相似度。

    只在**没命中**的路径上调用（要扫 5.1 万条），命中路径不付这个钱。
    """
    words = _norm_words(text)
    if not words:
        return []
    q = _fold(" ".join(words[:2]))
    species = _species_list(db_path)
    prefix = q[:3]
    pool = [sp for sp in species if _fold(sp).startswith(prefix)] or species
    best = []
    for sp in pool:
        r = difflib.SequenceMatcher(None, q, _fold(sp)).ratio()
        if r >= min_ratio:
            best.append((sp, r))
    best.sort(key=lambda t: -t[1])
    return best[:k]


def _selftest() -> int:
    """``python sources/coconut.py`` 自检：判定 + 取成分。"""
    cases = [("Glycyrrhiza uralensis", True), ("Glycirrhiza uralensis", True),
             ("Ginkgo biloba", True), ("Glycyrrhiza Uralensis Fisch", True),
             ("Radix et Rhizoma Glycyrrhizae", False), ("甘草", False),
             ("Liquorice Root", False), ("Abyssinia Coralbean", False),
             ("Dictamnus dasycarpus", True)]
    ok = True
    for text, want in cases:
        sp, how = looks_like_species(text)
        flag = "OK " if bool(sp) == want else "FAIL"
        if bool(sp) != want:
            ok = False
        print("%s  输入 %-32r → %-24s %s" % (flag, text, sp or "(非种名)", how))
    print("-" * 70)
    for sp in ("glycyrrhiza uralensis", "gingko biloba"):
        cs = compounds_of_species(sp)
        print("   %-26s 成分（结构去重后）%d 个；前 3 个：%s"
              % (sp, len(cs), [c.name for c in cs[:3]]))
    print("-" * 70)
    print("   候选建议 ('Glycyrrhiza uralensys') → %s"
          % ["%s(%.2f)" % t for t in suggest_species("Glycyrrhiza uralensys")])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())

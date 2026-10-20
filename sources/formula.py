# -*- coding: utf-8 -*-
r"""chemreact 数据源：**方剂**（``D:\TCMAI\data\formula_db.json``，**只读**）。

用户 2026-10-16：方剂库爬完（6,743 个名字 / 12,071 条记录），要求接进来。

结构（实测）::

    {"散痰宁糖浆": [{"name":…, "peifang":"桑白皮，桔梗，氯化铵，盐酸麻黄碱，薄荷脑，远志。",
                     "chuchu":"ETCM", "gongxiao":"咳嗽", "yongfa":…,
                     "from_herb":true, "category":"Chinese patent medicines"}, …], …}

* ``peifang`` = 组成，**逗号分隔的中文串**（不是列表）；中位 8 味、最多 94 味、平均 9.9 味。
* 原始 token 直接精确命中 tcm.db 只有 **46.7%** —— 因为里面混着三类噪音：
  剂量（``侧柏叶15g``）、未闭合的炮制括号（``甘草（炙``）、加工动词（``炒``/``焙``/``锉``/``晒干``）。
  再加异名（``生地``/``黄耆``/``丹皮``/``桂心``）与中成药辅料（``硬脂酸镁``/``糊精``）。

本模块只做解析：清洗 token（**不手写异名**，异名一律去 ``herbs.alias`` 反查），
把组成变成「能对上药材库的名字」+「对不上的原样列出」。
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ★ 出处分档（第七十五轮 H1）：纯函数模块，**不读任何额外文件**（判据就是两个已有字段）
import formula_source as FS
# ★ H2 抽检结论（第七十五轮）：固定种子抽中的 100 条逐条核对结果，供网页/台账多显示一栏
import h2_probe as HP

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FJ_DEFAULT = r"D:\TCMAI\data\formula_db.json"
TCM_DEFAULT = r"D:\TCMAI\tcm.db"
# ★ 药典 2025 成方制剂 overlay（我们自己从 indkb.zip 扒出来的，**不改用户的库**）
CHP_OVERLAY = Path(__file__).resolve().parent.parent / "data" / "chp_formulas.json"

# 剂量：数字 + 常用单位
_DOSE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:g|G|克|千克|kg|mg|毫克|钱|两|斤|ml|mL|毫升|升|L|"
    r"片|粒|枚|条|个|只|对|支|瓶|袋|丸|滴|份|包|分|寸|尺|把|握)?")
# 加工/炮制动词与注记（出现在**结尾**时丢掉）
_TAIL = re.compile(
    r"(?:去皮脐|去皮尖|去皮|去心|去芦|去核|去油|去毛|去节|去壳|去籽|去瓤|"
    r"炒炭|炒焦|炒黄|炒|微炒|清炒|麸炒|土炒|米炒|煅|煨|焙干|焙|晒干|阴干|晒|"
    r"切碎|切段|切片|捣碎|研末|为末|研|锉|碎|磨|蒸|煮|炖|酒洗|酒炙|蜜炙|"
    r"盐炙|醋炙|姜汁|分|末)+$")
_JUNK = "。．.、；;：:，,（）()【】[]《》<>\"'“”‘’　 \t\r\n"


def _load(path: str = FJ_DEFAULT) -> dict:
    """读方剂库（**进程内缓存**：5.3 MB，读一次 ≈0.15 s，之后 0）。"""
    global _DB_CACHE, _DB_CACHE_PATH
    if _DB_CACHE is None or _DB_CACHE_PATH != path:
        _DB_CACHE = json.loads(Path(path).read_text(encoding="utf-8"))
        _DB_CACHE_PATH = path
    return _DB_CACHE


_DB_CACHE: Optional[dict] = None
_DB_CACHE_PATH: str = ""


def clean_token(tok: str) -> str:
    """把一个组成 token 洗成**尽量像药材名**的形式（只做机械清洗，不猜）。"""
    t = str(tok or "").strip()
    t = t.split("（")[0].split("(")[0]          # 未闭合的炮制注记：甘草（炙 → 甘草
    t = t.strip(_JUNK)
    t = _DOSE.sub("", t)
    t = t.strip(_JUNK)
    for _ in range(3):                          # 加工动词可能叠着出现
        t2 = _TAIL.sub("", t).strip(_JUNK)
        if t2 == t:
            break
        t = t2
    return t.strip(_JUNK)


def split_ingredients(peifang: str) -> List[str]:
    """按**顶层** ，,、;； 切分；括号内的炮制说明不切。

    例：`肉豆蔻1两（用盐酒浸，破故纸同炒干燥，不用故纸）` 是一个 token，
    不会被中间的 `，` 切成“破故纸同炒干燥 / 不用故纸”两条。
    """
    s = str(peifang or "")
    out: List[str] = []
    buf: List[str] = []
    depth = 0
    for ch in s:
        if ch in "（(":
            depth += 1
        elif ch in "）)":
            depth = max(0, depth - 1)
        if ch in "，,、;；" and depth == 0:
            tok = "".join(buf).strip()
            if tok:
                out.append(tok)
            buf = []
        else:
            buf.append(ch)
    tok = "".join(buf).strip()
    if tok:
        out.append(tok)
    return out


_FORMULA_SUFFIX = ("汤", "丸", "散", "饮", "丹", "煎", "方")


def _looks_like_formula_name(t: str) -> bool:
    """保守判断“这像方名而不是药材名”（只用于识别整条方名引用）。"""
    return bool(t) and any(str(t).endswith(x) for x in _FORMULA_SUFFIX)


def _source_display(src: str) -> str:
    """出处显示名：英文版药典导入批次显示中文名，原始字段仍保留在 source。"""
    s = str(src or "")
    if "Chinese Pharmacopoeia 2020" in s:
        return "中国药典 2020（英文导入）"
    return s


def _best_formula_peifang(name: str) -> str:
    """嵌套方名 → 最权威版本的组成原文（优先 2025 药典 overlay）。"""
    ov = _overlay().get(name)
    if ov:
        herbs = [str(c.get("herb") or "").strip() for c in (ov.get("组成") or [])]
        herbs = [h for h in herbs if h]
        if herbs:
            return "、".join(herbs)
    recs = _load().get(name) or []
    if not recs:
        return ""

    def _rank(r: dict):
        ai = 1 if not str(r.get("category") or "").strip() else 0
        return (ai, _src_rank(str(r.get("chuchu") or "")))

    return str(min(recs, key=_rank).get("peifang") or "")


@contextmanager
def _ro_conn(db_path: str = TCM_DEFAULT):
    r"""**只读**打开 tcm.db：先 mode=ro；打不开（WAL 无 -shm / 有活跃写者）就回退 immutable=1。

    ★ 第七十五轮修的 bug：原先直接 `mode=ro`，在用户库处于 WAL 活跃状态时会
    `unable to open database file`，整条方剂解析直接崩。回退仍是**纯只读**（不加锁、不写文件），
    只是把库当"不会变化的快照"读 —— 与 `tools\tcm_ro.py` 的口径一致。
    """
    uri = "file:" + str(Path(db_path).resolve()).replace("\\", "/")
    try:
        conn = sqlite3.connect(uri + "?mode=ro", uri=True)
        conn.execute("SELECT 1")
    except sqlite3.OperationalError as ex:
        print("   [warn] formula: mode=ro 打不开（%s）→ 回退 immutable=1（只读快照）" % ex)
        conn = sqlite3.connect(uri + "?immutable=1", uri=True)
    try:
        yield conn
    finally:
        conn.close()


def alias_map(db_path: str = TCM_DEFAULT) -> Dict[str, str]:
    """别名 → 正名。**从 herbs.alias 列读**，不手写。"""
    with _ro_conn(db_path) as conn:
        out: Dict[str, str] = {}
        for name_cn, alias in conn.execute(
                "SELECT name_cn, COALESCE(alias,'') FROM herbs"):
            for a in re.split(r"[;；、,，/]", alias):
                a = a.strip()
                if a and a != name_cn and a not in out:
                    out[a] = name_cn
        return out


_PREP = ("炙", "生", "熟", "炒", "焦", "醋", "酒", "盐", "蜜", "姜", "制", "煅", "煨")


def _resolve_one(tok: str, names: set, alias: Dict[str, str]) -> Optional[str]:
    """一个名字 → 药材库正名。对不上返回 None。

    顺序（先严后宽，全部有依据、不猜）：

      1. 精确正名
      2. 别名表
      3. 去炮制前缀（炙甘草→甘草；熟地黄 **不该** 被砍成地黄 —— 所以精确在前）
      4. **前缀规则**：正名是它的前缀（水牛角浓缩粉 → 水牛角）
      5. **后缀规则**：正名是它的后缀（人工麝香 → 麝香；粉丹皮 → 牡丹皮）
      6. 别名后缀规则（酒萸肉 → 萸肉 → 别名"山萸肉" → 山茱萸）
    """
    t = str(tok or "").strip()
    if not t:
        return None
    if t in names:
        return t
    # ★ 炮制品闸（用户 2026-10-16）：药典收载的炮制品（制何首乌/姜半夏/大蓟炭…）
    #   是独立药材，**不许**拆成基原、也不走别名/前缀后缀。库里有就精确命中上面那一行。
    try:
        import processed as PR
        if PR.is_processed(t):
            return None
    except Exception as ex:                                # noqa: BLE001 —— 打印，不静默
        print("   [warn] 炮制品闸查询失败：%s: %s" % (type(ex).__name__, ex))
    if t in alias:
        return alias[t]
    for p in _PREP:
        if t.startswith(p) and len(t) > len(p) + 1:
            rest = t[len(p):]
            if rest in names:
                return rest
            if rest in alias:
                return alias[rest]
    # ★ 别名索引（NTU 同义词表，多候选取首选）：槐米→槐花、黑顺片→附子…
    try:
        import alias_index as AI
        got = AI.best_in_db(t)
        if got:
            return got
    except Exception:                                    # noqa: BLE001 —— 可选增强
        pass
    # ★ 前缀 / 后缀规则：**枚举它自己的前缀/后缀去查表**（O(长度)），
    #   不要扫全部 6421 个药材名（那会是 1.5 万次 × 6421 次比较，慢到不能用）。
    for L in range(len(t), 1, -1):
        head = t[:L]
        if L < len(t) and head in names:          # 正名是它的前缀：水牛角浓缩粉 → 水牛角
            return head
    for L in range(len(t), 1, -1):
        tail = t[-L:]
        if L < len(t) and tail in names:          # 正名是它的后缀：人工麝香 → 麝香
            return tail
        if L < len(t) and tail in alias:          # 别名后缀：酒萸肉 → 萸肉 → 山萸肉 → 山茱萸
            return alias[tail]
        # 别名**以它结尾**（库里的别名是"山萸肉"，我们要查的词是"萸肉"）
        if L < len(t):
            for a, full in _alias_tail2(alias).get(tail[-2:], ()):
                if a.endswith(tail):
                    return full
    # ★ 最后一道：**人工审定**的异名表（第七十五轮；只收同物异写，绝不碰炮制品）
    try:
        import alias_curated as AC
        canon = AC.resolve(t)
        if canon and canon in names:
            return canon
    except Exception as ex:                                # noqa: BLE001 —— 打印，不静默
        print("   [warn] 审定异名表查询失败：%s: %s" % (type(ex).__name__, ex))
    return None


_AT2_CACHE: Optional[dict] = None
_AT2_SIZE: int = -1


def _alias_tail2(alias: Dict[str, str]) -> Dict[str, list]:
    """别名按**末两字**分桶（一次建好、按表大小缓存）—— 用于"别名以某词结尾"的 O(1) 查询。"""
    global _AT2_CACHE, _AT2_SIZE
    if _AT2_CACHE is None or _AT2_SIZE != len(alias):
        idx: Dict[str, list] = {}
        for a, full in alias.items():
            if len(a) >= 2:
                idx.setdefault(a[-2:], []).append((a, full))
        for v in idx.values():
            v.sort(key=lambda x: -len(x[0]))
        _AT2_CACHE, _AT2_SIZE = idx, len(alias)
    return _AT2_CACHE


def _names_alias(db_path: str = TCM_DEFAULT):
    """(正气名集合, 别名表) —— 进程内缓存，避免每条记录都重扫 herbs 表。"""
    global _NA_CACHE, _NA_PATH
    if _NA_CACHE is None or _NA_PATH != db_path:
        with _ro_conn(db_path) as conn:
            _NA_CACHE = ({r[0] for r in conn.execute("SELECT name_cn FROM herbs")},
                         alias_map(db_path))
        _NA_PATH = db_path
    return _NA_CACHE


_NA_CACHE = None
_NA_PATH: str = ""


def resolve_ingredients(peifang: str, names: Optional[set] = None,
                        alias: Optional[Dict[str, str]] = None,
                        db_path: str = TCM_DEFAULT,
                        _depth: int = 0, _seen: Optional[set] = None,
                        _root_name: Optional[str] = None
                        ) -> Tuple[List[str], List[str]]:
    """返回 ``(能对上药材库的名字列表, 对不上的原 token 列表)``。

    三级：精确名 → 别名 → 去掉炮制前缀（炙甘草→甘草）。
    若 token 是**嵌套方名**（如「成方便读」里的“二妙丸”），展开成其最权威版本的组成；
    递归深度上限 3，带 seen 防环。都对不上就如实列出。
    """
    if names is None or alias is None:
        names, alias = _names_alias(db_path)
    if _seen is None:
        _seen = set()
    if _root_name:
        _seen = _seen | {_root_name}
    tokens = split_ingredients(peifang)
    cleaned = [(tok, clean_token(tok)) for tok in tokens]
    formula_names = {t for _tok, t in cleaned
                     if t and (t in _load() or t in _overlay())}
    formula_like = {t for _tok, t in cleaned
                    if t and (t in formula_names or _looks_like_formula_name(t))}
    non_formula = [t for _tok, t in cleaned
                   if t and t not in formula_like]
    # 整条只是“方名引用”（如“六味地黄汤，生脉饮。”）→ 不当成组成，避免把两方合并
    if formula_like and not non_formula:
        return [], [tok for tok, _t in cleaned if _t]
    ok: List[str] = []
    bad: List[str] = []
    for tok, t in cleaned:
        if not t:
            continue
        got = _resolve_one(t, names, alias)
        if got:
            if got not in ok:
                ok.append(got)
            continue
        # 嵌套方名：二妙丸 → 苍术、黄柏（优先 2025 药典 overlay）
        if (_depth < 3 and t not in _seen
                and (t in _load() or t in _overlay())):
            sub = _best_formula_peifang(t)
            if sub:
                sub_ok, sub_bad = resolve_ingredients(
                    sub, names, alias, db_path, _depth + 1, _seen | {t}, _root_name)
                for h in sub_ok:
                    if h not in ok:
                        ok.append(h)
                bad.extend(sub_bad)
                continue
        if t:
            bad.append(tok.strip())
    return ok, bad


def find_formulas(keyword: str, path: str = FJ_DEFAULT,
                  limit: int = 20) -> List[str]:
    """按名字找方剂：精确优先，其次子串。"""
    return _find(keyword, path, limit)


def similar_formulas(keyword: str, path: str = FJ_DEFAULT,
                     limit: int = 8) -> List[str]:
    """相似方名候选 —— **只供用户点选，绝不用于自动选版**。

    先取精确/连续子串（find_formulas），再用首尾片段补齐，
    这样「三黄汤」也能看到「三黄泻心汤」「三黄片」等候选。
    """
    kw = str(keyword or "").strip()
    if not kw:
        return []
    hits = find_formulas(kw, path, limit=limit)
    seen = set(hits)
    d = _load(path)
    ov = _overlay()
    keys = list(d.keys())
    for k in ov:
        if k not in d:
            keys.append(k)
    need = max(0, limit - len(hits))
    frags: List[str] = []
    if need:
        cand = set()
        for w in (kw[:2], kw[:3], kw[-2:], kw[-3:]):
            if len(w) < 2:
                continue
            for k in keys:
                if k not in seen and w in k:
                    cand.add(k)

        def _pfx(a: str, b: str) -> int:
            n = 0
            for x, y in zip(a, b):
                if x != y:
                    break
                n += 1
            return n

        def _sfx(a: str, b: str) -> int:
            n = 0
            for x, y in zip(reversed(a), reversed(b)):
                if x != y:
                    break
                n += 1
            return n

        frags = sorted(
            cand,
            key=lambda k: (-_pfx(kw, k), -_sfx(kw, k),
                           abs(len(k) - len(kw)), len(k), k),
        )[:need]
    return (hits + frags)[:limit]


def is_formula_name(name: str, path: str = FJ_DEFAULT) -> bool:
    """**精确**方剂名判定 —— 展开组成时只能用这个。

    为什么不能用子串：实测「甘草」会命中「炙甘草汤」、「桂枝」会命中「桂枝汤」，
    那会把药材名劫持成方剂。子串匹配只留给「查找相似」窗口。

    ★ 第七十五轮修正：**药典成方 overlay 独有**的方名（1,526 里 26 个不在方剂库）
      以前会被误判"不是方剂"→ 界面报未收录。现在两边都查。
    """
    key = str(name or "").strip()
    return bool(key) and (key in _load(path) or key in _overlay())


def _find(keyword: str, path: str = FJ_DEFAULT,
          limit: int = 20) -> List[str]:
    d = _load(path)
    ov = _overlay()
    kw = str(keyword or "").strip()
    if not kw:
        return []
    keys = list(d.keys())
    for k in ov:
        if k not in d:
            keys.append(k)
    if kw in d or kw in ov:
        exact = [kw]
    else:
        exact = []
    sub = [k for k in keys if kw in k and k not in exact]
    sub.sort(key=len)
    return (exact + sub)[:limit]


# ★★ 同名方剂在**不同典籍里组成不同**，绝对不能合并！
#   实测：合并后「四君子汤」= 24 味（人参/白术/茯苓 + 川芎/陈皮/半夏/天麻…），
#   「六味地黄丸」= 50 味 —— 那是嵌合体，不是任何一本书里的方子。
#   所以按**版本**（出处）分开，让用户选。
SRC_RANK = (
    ("中国药典", 0),               # ★ overlay 里写的是中文来源名，权威度最高
    ("Pharmacopoeia", 0),          # 中国药典最权威
    ("ETCM", 1),
    ("ITCM", 2),
    ("CPMCP", 3),
    ("Catalogue of Ancient Classic Prescriptions", 4),
)


def _src_rank(src: str) -> int:
    for key, r in SRC_RANK:
        if key.lower() in (src or "").lower():
            return r
    return 9


def _overlay(path: Optional[Path] = None) -> dict:
    """药典 overlay（进程内缓存）。缺文件就返回空字典，不报错。"""
    global _OV_CACHE, _OV_PATH
    p = Path(path) if path else CHP_OVERLAY
    if _OV_CACHE is None or _OV_PATH != str(p):
        try:
            _OV_CACHE = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            _OV_CACHE = {}
        _OV_PATH = str(p)
    return _OV_CACHE


_OV_CACHE: Optional[dict] = None
_OV_PATH: str = ""


def _clean_chp_herb(name: str) -> str:
    """药典组成里的药材名清洗：去括号注记、去"或"分支、去尾标点。"""
    t = re.split(r"[（(]", str(name or ""))[0]
    t = t.split("或")[0]
    t = re.sub(r"[。．.、，,\s]+$", "", t)
    return t.strip()


def dose_multiples(overlay_entry: dict) -> Dict[str, int]:
    """药典克数 → **整数份数**：以该方最小剂量为 1 份，向上取整。

    口径（用户 2026-10-16 定）：复方丹参滴丸 = 丹参90 / 三七17.6 / 冰片1.0（g）
    → 90 / 18 / 1 份。份数只在打开 `--dose-budget` 时放大配额，不开就只记录。
    """
    ds = [(str(c.get("herb") or ""), float(c.get("dose") or 0))
          for c in (overlay_entry.get("组成") or [])]
    ds = [(h, d) for h, d in ds if h and d > 0]
    if not ds:
        return {}
    lo = min(d for _h, d in ds)
    return {h: max(1, int(round(d / lo))) for h, d in ds}


def formula_versions(name: str, path: str = FJ_DEFAULT,
                     db_path: str = TCM_DEFAULT) -> List[dict]:
    """一个方剂名下的**全部版本**（每个来源一条），按权威度排序。

    ★ 只认**精确方名**或药典 overlay 独有方名；找不到就返回空，
      不再用 `find_formulas()` 的第一个子串命中顶替 —— 那会把不同方剂
      （如「牛黄清心片」与「醒脑牛黄清心片」）静默认成同一首。

    每条：``{"name","source","gongxiao","category","peifang","herbs","unmatched"}``
    """
    d = _load(path)
    key = str(name or "").strip()
    ov = _overlay().get(key)
    if key not in d and ov is None:
        return []
    out = []
    for r in d.get(key, []):
        herbs, bad = resolve_ingredients(str(r.get("peifang") or ""),
                                         db_path=db_path, _root_name=key)
        if not herbs:
            continue
        # ★ 出处分档（第七十五轮 H1）：内部 0–5；界面显示药典/ETCM/ITCM/CPMCP/古籍/AI现查（未核对）
        #   判据是 sources/formula_source.py 的纯函数（category + chuchu 两个已有字段）。
        try:
            _t = FS.tier_of_record(r)
            _tl = FS.tier_display(_t, str(r.get("chuchu") or ""))
        except ValueError as _ex:                 # 认不出的出处 → 标注出来，不猜、不中止
            print("   [warn] 出处分档：%s" % _ex)
            _t, _tl = -1, "? 认不出出处"
        # ★ H2 抽检结论（只显示，不影响选版/排序）：没抽到的就是 None → 界面显示「未抽检」
        _pr = HP.verdict(key, str(r.get("chuchu") or ""))
        out.append({"name": key,
                    "source": str(r.get("chuchu") or "").strip(),
                    "source_display": _source_display(str(r.get("chuchu") or "")),
                    "gongxiao": str(r.get("gongxiao") or "").strip(),
                    "category": str(r.get("category") or "").strip(),
                    "peifang": str(r.get("peifang") or ""),
                    "tier": _t, "tier_label": _tl,
                    "probe": ({"verdict": _pr.get("判定"),
                               "url": _pr.get("来源URL") or "",
                               "cov": _pr.get("覆盖率")} if _pr else None),
                    "herbs": herbs, "unmatched": bad})
    # ★ 药典 overlay（用户 2026-10-16）：法定组成 + 法定剂量；**不改用户的库**，
    #   只在读的时候多挂一个版本。来源名含"中国药典" → SRC_RANK 0 → 默认版本就是它。
    if ov:
        names, alias = _names_alias(db_path)
        hs: List[str] = []
        bad2: List[str] = []
        grams: Dict[str, float] = {}
        for c in (ov.get("组成") or []):
            t = _clean_chp_herb(c.get("herb"))
            got = _resolve_one(t, names, alias)
            shown = got or str(c.get("herb") or "")
            if got:
                if got not in hs:
                    hs.append(got)
            else:
                bad2.append(str(c.get("herb") or ""))
            try:
                grams[shown] = grams.get(shown, 0.0) + float(c.get("dose") or 0)
            except (TypeError, ValueError):
                pass
        if hs:
            pos = [x for x in grams.values() if x > 0]
            lo = min(pos) if pos else 0.0
            mult = ({h: max(1, int(round(v / lo))) for h, v in grams.items()}
                    if lo > 0 else {})
            out.append({"name": key,
                        "source": str(ov.get("source") or "中国药典2025版一部"),
                        "source_display": _source_display(
                            str(ov.get("source") or "中国药典2025版一部")),
                        "gongxiao": str(ov.get("功能主治") or ""),
                        "category": "成方制剂和单味制剂（药典）",
                        "peifang": str(ov.get("处方原文") or ""),
                        "tier": 0, "tier_label": FS.tier_display(
                            0, str(ov.get("source") or "中国药典2025版一部")),
                        "herbs": hs, "unmatched": bad2,
                        "grams": grams, "dose_multiples": mult,
                        "url": str(ov.get("url") or "")})
    # ★ 排序：权威度 → **带法定剂量的优先**（药典 overlay vs 用户库引用"2020药典"同为 0 档，
    #   但只有 overlay 带剂量）→ 味数多的优先。
    out.sort(key=lambda v: (_src_rank(v["source"]),
                            0 if v.get("dose_multiples") else 1,
                            -len(v["herbs"])))
    return out


def get_formula(name: str, path: str = FJ_DEFAULT,
                db_path: str = TCM_DEFAULT) -> Optional[dict]:
    """取**最权威的那个版本**，并把其余版本列为 ``alternatives``（供用户改选）。

    ``{"name","source","herbs","unmatched",…,"n_versions","alternatives":[…] }``
    """
    vs = formula_versions(name, path, db_path)
    if not vs:
        return None
    best = dict(vs[0])
    best["n_versions"] = len(vs)
    best["alternatives"] = [{"source": v["source"],
                             "source_display": v.get("source_display") or v["source"],
                             "n_herbs": len(v["herbs"]),
                             "tier": v.get("tier", -1),
                             "tier_label": v.get("tier_label", "?"),
                             "probe": v.get("probe"),
                             "peifang": v["peifang"][:80]} for v in vs[1:12]]
    return best


def _selftest() -> int:
    d = _load()
    print("方剂名 %d 个，记录 %d 条"
          % (len(d), sum(len(v) for v in d.values())))
    alias = alias_map()
    print("别名表（来自 herbs.alias）= %d 条" % len(alias))
    conn = sqlite3.connect("file:" + str(Path(TCM_DEFAULT).resolve()).replace("\\", "/")
                           + "?mode=ro", uri=True)
    names = {r[0] for r in conn.execute("SELECT name_cn FROM herbs")}
    conn.close()
    tot = hit = 0
    miss = {}
    for v in d.values():
        for rec in v:
            h, b = resolve_ingredients(str(rec.get("peifang") or ""), names, alias)
            tot += len(h) + len(b)
            hit += len(h)
            for x in b:
                miss[x] = miss.get(x, 0) + 1
    print("解析后命中率 = %d / %d = %.1f%%" % (hit, tot, 100.0 * hit / max(1, tot)))
    print("仍未命中 Top 20：", sorted(miss.items(), key=lambda t: -t[1])[:20])
    for nm in ("四君子汤", "六味地黄丸", "桂枝汤"):
        vs = formula_versions(nm)
        print("  %s：%d 个版本" % (nm, len(vs)))
        for v in vs[:4]:
            print("      [%s] %d 味 %s ｜ 未对上 %d"
                  % (v["source"][:34], len(v["herbs"]), v["herbs"][:8],
                     len(v["unmatched"])))
        g = get_formula(nm)
        if g:
            print("      → 默认取「%s」：%d 味" % (g["source"][:34], len(g["herbs"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())

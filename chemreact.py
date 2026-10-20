# -*- coding: utf-8 -*-
r"""Christos（炼膏师）—— TCMAI 的化学 AI 桥接入口（接的是 chemreact-staging 里的通用引擎）。

三个子命令：
    predict  给定底物（--herb 中药名 / --smiles 列表 / --mol 单个）枚举候选产物，
             写出台账 CSV + 索引 TSV（含方向标注 / 条件依据 / 完整出处）
    routes   给定目标分子，找"怎么造"：模板式逆合成搜索（可用 --pool-* 限定用你给的底物池）
    info     环境自检：引擎路径、模板数、黑名单数、数据库只读连通性

约定（与 chemreact-staging 一致）：
    * 只打标记、不打分、不排序；查不到 ≠ 不存在
    * 数据库一律**只读**访问（tcm.db / coconut.db 不会写入）
    * 输出写到本目录下 out\ ；引擎源码在 chemreact-staging（单一来源，这里不复制代码）
    * 引擎目录可用环境变量 CHEMCREACT_STAGE 覆盖（默认 D:\ProgramData\DSHNS\chemreact-staging）

用法（用 TCMAI 的 venv）：
    D:\TCMAI\venv\Scripts\python.exe chemreact.py info
    D:\TCMAI\venv\Scripts\python.exe chemreact.py predict --herb 甘草 --limit 12 --rounds 1
    D:\TCMAI\venv\Scripts\python.exe chemreact.py routes  --target "CC(=O)Oc1ccccc1C(=O)O" --depth 2
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent


def _research_enabled() -> bool:
    """Public builds keep route search and free-form reagents disabled."""
    return os.environ.get("CHRISTOS_RESEARCH_MODE") == "1"


def _stage() -> Path:
    """Locate the chemistry engine.

    Order: CHEMCREACT_STAGE env var -> this script's own directory (source
    checkout layout, where core/ sits next to this file) -> the author's
    development layout.  The last fallback only matters on the machine where
    this was developed; everywhere else the first two rules apply.
    """
    env = os.environ.get("CHEMCREACT_STAGE")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    if (here / "core").is_dir():
        return here
    return Path(r"D:\ProgramData\DSHNS\chemreact-staging")


def _bootstrap() -> Path:
    st = _stage()
    if not (st / "core").is_dir():
        print("找不到化学引擎目录：%s" % st)
        print("  * 如果 chemreact-staging 挪过位置，请设置环境变量 CHEMCREACT_STAGE 指向它，例如：")
        print("      set CHEMCREACT_STAGE=D:\\新位置\\chemreact-staging")
        print("  * 或把本脚本移回与引擎同级的地方。")
        sys.exit(3)
    for sub in ("core", "rules", "libs", "tools", "sources", "conditions"):
        d = st / sub
        if d.is_dir() and str(d) not in sys.path:
            sys.path.insert(0, str(d))
    tc = Path(r"D:\TCMAI\src")
    if tc.is_dir() and str(tc) not in sys.path:
        sys.path.append(str(tc))
    return st


def _sp_note(species: str, n_variants: int) -> str:
    """物种候选的备注：属级混合条目（abelmoschus spp）/ 合并了几个异写拼法。"""
    try:
        import coconut as _CC
        if _CC.NONDET.search(species or ""):
            return "属级混合条目（非确定种）"
    except Exception:                                # noqa: BLE001 —— 备注不该影响跑批
        pass
    return ("含 %d 个异写" % n_variants) if n_variants > 1 else ""


_EGG_KEYS = (
    # 用户 2026-10-17 清单（截图）：特朗普/希特勒/汪精卫/内裤/内衣/泳装照/结婚照/
    # 高市早苗/安倍晋三/裕仁/天皇/孙笑川/张顺飞/蔡徐坤/蒋中正/汪兆铭/兔女郎；
    # 另加：奶娃 + 上一轮 8 个（常凯申/东北雨姐/汗脚/玉足/袜子/黑丝/白丝/丝袜）。
    # 既有别名（奶龙/奶蛙/蒋介石/蒋介石内裤）保留，不影响清单里的词。
    "奶龙", "奶娃", "奶蛙",
    "特朗普", "特朗普和高市早苗结婚照",
    "希特勒",
    "汪精卫", "汪兆铭",
    "蒋介石", "蒋中正", "蒋介石内裤",
    "高市早苗", "安倍晋三", "裕仁", "天皇",
    "孙笑川", "张顺飞", "蔡徐坤",
    "内裤", "内衣", "泳装照", "结婚照", "兔女郎",
    # 用户 2026-10-17 追加（方剂页也要同一套彩蛋）
    "常凯申", "东北雨姐", "汗脚", "玉足", "袜子", "黑丝", "白丝", "丝袜",
)
EGG_REPLY = "根本没有这样的中药"
LANG = "zh"


def T(zh: str, en: str) -> str:
    """Small backend translation helper (UI passes --lang en)."""
    return en if LANG == "en" else zh


COND_EN = {
    "煎煮": "Decoction", "室温浸泡": "Room-temperature soak", "水提": "Water extraction",
    "醇提": "Ethanol extraction", "酸水解": "Acid hydrolysis", "碱水解": "Base hydrolysis",
    "酶催化": "Enzymatic", "还原": "Reduction", "氧化": "Oxidation",
    "无氧煎煮": "Anaerobic decoction",
}


def _cond_label(x: str) -> str:
    return COND_EN.get(x, x) if LANG == "en" else x


def _stat_text(stat) -> str:
    """Render the route stat dict in English when --lang en (keys stay readable)."""
    s = str(stat)
    if LANG != "en":
        return s
    for a, b in (
        ("启发式", "heuristic"), ("可用路线", "usable_routes"),
        ("重复路线跳过", "duplicate_routes_skipped"), ("无切断方案", "no_disconnections"),
        ("达路线上限", "route_limit_reached"), ("耗时秒", "seconds"),
        ("时间上限触发", "time_limit"), ("节点预算耗尽", "node_budget_exhausted"),
    ):
        s = s.replace(a, b)
    s = re.sub(r"深度(\d+)_切断方案", r"depth\1_disconnections", s)
    s = re.sub(r"深度(\d+)_递归分支", r"depth\1_recursive_branches", s)
    return s.replace("不可用:", "unusable:")


def _egg(name: str) -> str:
    """彩蛋（用户 2026-10-16）：明显不是药材的输入 → 回一句人话。

    去掉空格/标点后**子串**命中即可（所以「奶龙的皮」也会中）。命中返回提示语，
    否则返回空串。判据只有这几条固定词，不会影响正常药材名。

    ★ 用户 2026-10-17：彩蛋不翻译，只认**简体中文**输入；
      含拉丁字母/数字（英文、拼音等）一律不触发。
    """
    s = re.sub(r"[\s\W_]+", "", str(name or ""))
    if not s:
        return ""
    if re.search(r"[A-Za-z0-9]", s):
        return ""
    for k in _EGG_KEYS:
        if k in s:
            return EGG_REPLY
    return ""


def build_choice_window(name: str):
    """「查找相似」的唯一实现（命令行与网页共用，不写两遍）。

    返回 ``{"query","kind","items":[{"name","group","herb_id","n_compounds","note"}]}``。
    **永远有内容**（用户 2026-10-16 要求）：找不到相似 ≠ 什么都没找到 ——
    "唯一一条"和"库里有没收录"必须分得清：

    * **中文名** → HERB 里同字段的条目（炮制品 / 同名 / 药用部位，如 甘草 → 炙甘草、
      甘草节…）**加上**它们对应的**基元植物**（用 COCONUT 种名字典认出来的物种）。
      只有一条 → 也把它列出来（说明"它是独苗"）。
    * **拉丁药材名 / 英语名** → HERB 里命中该拉丁串的条目（甘草 → 甘草 / 炙甘草）。
    * **物种双名法** → **同属的其他物种**（"相似" = 同一个属）。
    * **拉丁属名** → 该属全部物种。
    * **什么都没命中** → 一条占位项 ``group="未收录"``（页面显示"（未收录）"）。
    """
    _bootstrap()
    from herb import list_named_herbs, list_latin_herbs
    import coconut as CC
    q = str(name or "").strip()
    if not q:
        return {"query": q, "kind": "missing", "items": [_missing_item(q)]}
    egg = _egg(q)
    if egg:
        return {"query": q, "kind": "egg", "items": [], "message": egg}
    if re.search(r"[A-Za-z]", q):
        items = []
        try:
            if CC.looks_like_drug_latin(q):
                # 药材拉丁名 → 列出命中的药材条目（而不是"没有相似项"）
                items = [{"name": r["name_cn"], "group": "药材",
                          "herb_id": r["herb_id"], "n_compounds": r["n_compounds"],
                          "note": ""} for r in list_latin_herbs(q)]
                if not items:
                    return {"query": q, "kind": "missing", "items": [_missing_item(q)]}
                return {"query": q, "kind": "herb", "items": items}
            sp, _how = CC.looks_like_species(q)
            rows = CC.genus_species((sp or q).split()[0]) if (sp or len(q.split()) == 1) else []
        except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
            print("   [warn] 相似项查找失败（%s: %s）" % (type(ex).__name__, ex))
            rows = []
        if not rows:
            return {"query": q, "kind": "missing", "items": [_missing_item(q)]}
        for s, n, nv in rows:
            note = _sp_note(s, nv)
            if s == sp:
                note = (note + " ·" if note else "") + "就是你输入的这个"
            items.append({"name": s, "group": "基元植物", "herb_id": "",
                          "n_compounds": n, "note": note})
        return {"query": q, "kind": "genus", "items": items}
    hc_rows, sp_rows = [], []
    try:
        hc_rows = list_named_herbs(q)
    except Exception as ex:                          # noqa: BLE001 —— 打印，不静默
        print("   [warn] 同字段药材查询失败（%s: %s）" % (type(ex).__name__, ex))
    # ★ 别名优先于"字面包含"（与 herb._resolve_herb_ids 同序）：精确名没有时先问别名表，
    #   否则 `龙胆草` 会被"滇龙胆草/德国龙胆草"抢走，而辞典说它指向 龙胆 等 6 个候选。
    if not any(r["name_cn"] == q for r in hc_rows):
        try:
            import alias_index as AI
            cands = AI.in_db(q)
        except Exception as ex:                          # noqa: BLE001
            cands = []
            print("   [warn] 别名索引查询失败：%s: %s" % (type(ex).__name__, ex))
        if cands:
            items = []
            for c in cands:
                n = 0
                try:
                    got = list_named_herbs(c["canonical"])
                    if got:
                        n = got[0]["n_compounds"]
                except Exception:                        # noqa: BLE001
                    pass
                src = c.get("dict") or ""
                items.append({"name": c["canonical"], "group": "药材",
                              "herb_id": c.get("herb_id", ""), "n_compounds": n,
                              "note": "别名「%s」→ 本条%s"
                                      % (q, ("（%s）" % src) if src else "")})
            print("   「%s」是**别名**，可能指：%s"
                  % (q, "、".join(c["canonical"] for c in cands)))
            return {"query": q, "kind": "alias", "items": items}
    if hc_rows:
        try:
            sp_rows = CC.species_from_blobs(
                [r["latin"] for r in hc_rows] + [r["name_en"] for r in hc_rows])
        except Exception as ex:                      # noqa: BLE001
            print("   [warn] 基元植物识别失败（%s: %s）" % (type(ex).__name__, ex))
    if not hc_rows:
        # ★ 别名（多候选）：打一个俗名可能对应好几味药 —— 全部列出来让用户挑
        try:
            import alias_index as AI
            cands = AI.in_db(q)
        except Exception as ex:                              # noqa: BLE001
            cands = []
            print("   [warn] 别名索引查询失败：%s: %s" % (type(ex).__name__, ex))
        if cands:
            items = [{"name": c["canonical"], "group": "药材",
                      "herb_id": c.get("herb_id", ""), "n_compounds": 0, "note": ""}
                     for c in cands]
            for it, c in zip(items, cands):
                try:
                    got = list_named_herbs(it["name"])
                    if got:
                        it["n_compounds"] = got[0]["n_compounds"]
                except Exception:                            # noqa: BLE001
                    pass
                src = c.get("dict") or ""
                it["note"] = "别名「%s」→ 本条" % q + (("（%s）" % src) if src else "")
            print("   「%s」是**别名**，可能指：%s"
                  % (q, "、".join(c["canonical"] for c in cands)))
            return {"query": q, "kind": "alias", "items": items}
        return {"query": q, "kind": "missing", "items": [_missing_item(q)]}
    items = [{"name": r["name_cn"], "group": "药材", "herb_id": r["herb_id"],
              "n_compounds": r["n_compounds"], "note": ""} for r in hc_rows]
    items += [{"name": s, "group": "基元植物", "herb_id": "", "n_compounds": n,
               "note": _sp_note(s, nv)} for s, n, nv in sp_rows]
    return {"query": q, "kind": "herb", "items": items}


def _missing_item(q: str) -> dict:
    """「库里没有这个名字」的占位项（页面会把复选框禁用、只显示提示）。"""
    return {"name": q, "group": "未收录", "herb_id": "", "n_compounds": 0,
            "note": "（未收录）：HERB 药材库与 COCONUT 物种库里都没有这个名字"}


def _print_choices(cw: dict) -> None:
    if cw.get("kind") == "egg":
        print("   🥚 %s" % cw.get("message", EGG_REPLY))
        return
    if cw.get("kind") == "missing":
        print("   （未收录）「%s」" % cw["query"])
        return
    print("   【查找相似】「%s」：%d 个候选——勾选后重跑："
          % (cw["query"], len(cw["items"])))
    for i, it in enumerate(cw["items"][:30], 1):
        print("       %2d) [%s] %-30s %d 个成分  %s"
              % (i, it["group"], it["name"], it["n_compounds"],
                 ("← " + it["note"]) if it.get("note") else ""))
    if len(cw["items"]) > 30:
        print("       …（共 %d 个，只列前 30）" % len(cw["items"]))


def _split_list(s: str):
    return tuple(x.strip() for x in str(s or "").replace(";", ",").split(",") if x.strip())


def _parse_limit(x):
    r"""--limit：'all'/'0'/'none'/'全部' -> None（不截取）；其余按整数；非法值回退 12。"""
    s = str(x).strip().lower()
    if s in ("all", "0", "none", "全部"):
        return None
    try:
        n = int(s)
    except ValueError:
        return 12
    return n if n > 0 else None


def _log_run(kind: str, note: str, files: dict) -> None:
    """运行台账：追加一行到本目录 out\\runs.jsonl（我们自己的文件；不碰任何外部库）。"""
    try:
        d = HERE / "out"
        d.mkdir(parents=True, exist_ok=True)
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": kind,
               "note": note, "files": files}
        with open(d / "runs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as ex:                     # noqa: BLE001 —— 打印，不静默
        print("   [warn] 运行台账写入失败：%s: %s" % (type(ex).__name__, ex))


def _pair_coverage(n_sub: int, budget: int, fair: bool) -> dict:
    r"""预估算：两两对子怎么被预算截断、各成分摊到多少伙伴（口径与引擎 step() 一致）。

    顺序模式 = 引擎旧行为 pair 列表 [:budget]；公平模式 = smartreact_engine.fair_sample_pairs。
    """
    from collections import Counter
    full = n_sub * (n_sub - 1) // 2
    if fair:
        from smartreact_engine import fair_sample_pairs
        pairs = (fair_sample_pairs(n_sub, budget) if full > budget else
                 [(i, j) for i in range(n_sub) for j in range(i + 1, n_sub)])
        mode = "fair"
    else:
        pairs = [(i, j) for i in range(n_sub) for j in range(i + 1, n_sub)][:max(0, budget)]
        mode = "sequential"
    cnt = Counter()
    for i, j in pairs:
        cnt[i] += 1
        cnt[j] += 1
    partners = [cnt.get(i, 0) for i in range(n_sub)]
    return {"pairs_total": full, "pairs_used": len(pairs), "mode": mode,
            "min_partners": (min(partners) if partners else 0),
            "max_partners": (max(partners) if partners else 0), "fair": bool(fair)}


# ---------------------------------------------------------------- predict
def cmd_predict(a) -> int:
    global LANG
    LANG = "en" if str(getattr(a, "lang", "zh")) == "en" else "zh"
    if str(getattr(a, "reagents", "") or "").strip() and not _research_enabled():
        print("公开版已关闭辅助试剂输入。")
        return 3
    _bootstrap()
    import query_base as qb
    # ★ 条件档案前置校验：友好报错，不再抛 traceback（第七十四轮）
    try:
        import templates as TP
        if str(a.cond) not in TP.TEMPLATES:
            print(T("条件档案 %r 不存在。可用：%s",
                    "Condition profile %r not found. Available: %s")
                  % (a.cond, "、".join(sorted(TP.TEMPLATES))))
            return 2
    except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
        print("   [warn] 条件档案校验跳过（%s: %s）" % (type(ex).__name__, ex))
    lim = _parse_limit(getattr(a, "limit", 12))
    seeds = []
    selection = {}
    # ★ 属名（拉丁）不直接开跑：收集候选，交给网页渲染一个**选择窗口**（用户 2026-10-15 要求）
    genus_hit = None
    choice_window = None
    missing_herbs = []          # ★ 未收录的名字：收集起来，跑批前直接中止（用户 2026-10-16）
    # ★ 剂量 = 份数（用户 2026-10-16）：同一个名字输入 k 次 = 该药材 k 份。
    #   成分只取一次（重复输入**不再**重复占对子预算），但份数会记进 meta/台账，
    #   并且开 --dose-budget 时按份数放大该药材的成分配额。
    _herb_names = list(_split_list(a.herb))
    doses: Dict[str, int] = {}
    for _nmx in _herb_names:
        doses[_nmx] = doses.get(_nmx, 0) + 1
    dose_on = bool(getattr(a, "dose_budget", False))
    only_one_name = (len(doses) == 1) if a.herb else False
    # ★ 彩蛋输入只用于查找提示；绝不允许进入跑批、报告或历史（用户 2026-10-17）。
    #   命中后只回一句通用提示，不打印、不落盘任何关键词。
    _egg_hit = any(_egg(_nm) for _nm in doses)
    if not _egg_hit:
        _egg_hit = bool(_egg(a.smiles) or _egg(getattr(a, "mol", None)))
    _fp_raw0 = str(getattr(a, "formula_provenance", "") or "").strip()
    if not _egg_hit and _fp_raw0:
        try:
            _fp0 = json.loads(_fp_raw0)
            if isinstance(_fp0, dict):
                _fp0 = [_fp0]
            if isinstance(_fp0, list):
                for _it0 in _fp0:
                    if not isinstance(_it0, dict):
                        continue
                    _vals0 = [str(_it0.get("name") or "")]
                    if isinstance(_it0.get("base_herbs"), list):
                        _vals0 += [str(x) for x in _it0["base_herbs"]]
                    if isinstance(_it0.get("final_herbs"), list):
                        _vals0 += [str(x) for x in _it0["final_herbs"]]
                    _vals0.append(str(_it0.get("doses") or ""))
                    _md0 = _it0.get("modifications")
                    if isinstance(_md0, dict) and isinstance(_md0.get("added"), list):
                        _vals0 += [str(x.get("herb") or "") for x in _md0["added"]
                                   if isinstance(x, dict)]
                    if any(_egg(_v0) for _v0 in _vals0):
                        _egg_hit = True
                        break
        except Exception:
            pass
    if _egg_hit:
        print(T("✗ 输入未通过校验；未跑批、未生成报告。",
                "✗ Input rejected; no run and no report generated."))
        return 2
    # ★ 方剂（用户 2026-10-16）：名字若是方剂 → 展开成**组成药材**，再走同一条路。
    #   组成里有对不上的（辅料/化学药/异名）→ 如实列出，**不当作"用户打错字"中止**。
    formulas_used = {}
    dose_note = {}          # 某味的份数**来自哪里**：药典剂量 g / 用户重复输入
    from_formula = set()    # 来自方剂展开的药材名 —— 缺了**不中止整方**，只如实标注
    if a.herb:
        try:
            import formula as FM
            for _fn in list(doses):
                # ★ 只认**精确**方剂名！子串兜底会把嵌在方剂名里的药材名劫走：
                #   实测「甘草」被"炙甘草汤"吃掉、「桂枝」会被"桂枝汤"吃掉。找相似窗口才用子串。
                if not FM.is_formula_name(_fn):
                    continue
                g = FM.get_formula(_fn)
                if not g:
                    continue
                formulas_used[_fn] = g
                k0 = doses.pop(_fn)
                mult = g.get("dose_multiples") or {}
                for hh in g["herbs"]:
                    doses[hh] = doses.get(hh, 0) + k0 * int(mult.get(hh, 1))
                    from_formula.add(hh)
                for hh, mv in mult.items():
                    if mv > 1 or hh in g["herbs"]:
                        _gm = (g.get("grams") or {}).get(hh)
                        if _gm:
                            dose_note[hh] = "药典剂量 %sg" % (("%g" % _gm))
                # ★ 出处分档（第七十五轮 H1）：药典 / ETCM / ITCM / CPMCP / 古籍 / AI现查（未核对）
                print("   方剂 %s（%s ｜ 出处档 %s）：%d 味入方 → %s"
                      % (g["name"], g["source"] or "出处未标",
                         g.get("tier_label") or "?", len(g["herbs"]),
                         "、".join(g["herbs"][:12])
                         + ("…" if len(g["herbs"]) > 12 else "")))
                if mult:
                    _g = g.get("grams") or {}
                    print("      法定剂量 → 份数（以方中最小剂量 = 1 份）：%s"
                          % "、".join("%s %sg→%d份" % (hh, _g.get(hh, "?"), mult.get(hh, 1))
                                      for hh in g["herbs"][:8]))
                    print("      ★ 份数只在勾选「剂量加权」时放大配额；不勾只做记录")
                if g["unmatched"]:
                    print("      未对上 %d 个（辅料 / 化学药 / 异名，已跳过）：%s"
                          % (len(g["unmatched"]), "、".join(g["unmatched"][:8])))
                if g.get("n_versions", 1) > 1:
                    _alts = g.get("alternatives", [])
                    print("      ⚠ 同名方剂共 %d 个版本，本次用「%s ｜ %s」；其他版本：%s"
                          % (g["n_versions"], g["source"] or "?",
                             g.get("tier_label") or "?",
                             "；".join("%s[%s](%d味)"
                                       % (v["source"][:16], v.get("tier_label", "?"),
                                          v["n_herbs"]) for v in _alts[:4])))
                    _n5 = sum(1 for v in _alts if v.get("tier") == 5)
                    if _n5:
                        print("      （其中来自 **AI 现查** 的版本 %d 个 —— 只标注，不隐藏、不排序；"
                              "网页结果里可按出处单独筛看）" % _n5)
                # ★ H2 抽检栏（第七十五轮）：本条版本**抽检到过没有**，抽到就报判定
                _pv = g.get("probe")
                _alts_p = [v for v in g.get("alternatives", []) if v.get("probe")]
                if _pv:
                    print("      抽检（H2，100 条固定种子）：%s（组成重合 %s）%s"
                          % (_pv.get("verdict") or "?", _pv.get("cov"),
                             ("  " + _pv.get("url", "")) if _pv.get("url") else ""))
                if _alts_p:
                    _nv = {}
                    for v in _alts_p:
                        _nv[v["probe"]["verdict"]] = _nv.get(v["probe"]["verdict"], 0) + 1
                    print("      本次未用的版本里有 %d 个抽检过：%s"
                          % (len(_alts_p),
                             "、".join("%s %d 个" % (k, n) for k, n in sorted(_nv.items()))))
        except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
            print("   [warn] 方剂展开失败（%s: %s）" % (type(ex).__name__, ex))
    # ★ 网页方剂页（第七十六轮）：多首方 / 加减药味的出处。
    #   只写 meta 与台账，不参与预测；为空时与旧版完全一致。
    formulas_prov = {}
    _fp_raw = str(getattr(a, "formula_provenance", "") or "").strip()
    if _fp_raw:
        try:
            _fp = json.loads(_fp_raw)
            if isinstance(_fp, dict):
                _fp = [_fp]          # 单个方剂也接受（UI 始终传数组；CLI 手写时常传对象）
            if not isinstance(_fp, list):
                raise ValueError("顶层必须是数组")
            for _it in _fp:
                if not isinstance(_it, dict):
                    continue
                _nm = str(_it.get("name") or "").strip()
                if _nm:
                    formulas_prov[_nm] = _it
        except Exception as ex:                      # noqa: BLE001 —— 出处失败不影响预测
            print("   [warn] 方剂出处 JSON 解析失败（预测继续，台账里不写方剂出处）：%s: %s"
                  % (type(ex).__name__, ex))
    if formulas_prov:
        for _nm, _it in formulas_prov.items():
            _md = _it.get("modifications") or {}
            _rm = [str(x) for x in (_md.get("removed") or []) if str(x).strip()]
            _ad = [str(x.get("herb")) for x in (_md.get("added") or [])
                   if isinstance(x, dict) and str(x.get("herb") or "").strip()]
            print("   方剂组合 %s（%s ｜ %s）：原方 %d 味 → 本次 %d 味%s%s"
                  % (_nm, _it.get("source_display") or _it.get("source") or "出处未标",
                     _it.get("tier_label") or "?",
                     len(_it.get("base_herbs") or []), len(_it.get("final_herbs") or []),
                     ("；减 " + "、".join(_rm)) if _rm else "",
                     ("；加 " + "、".join(_ad)) if _ad else ""))
    if a.herb:
        from herb import compounds_of_herb, LAST_RESOLVE, list_named_herbs
        import coconut as CC          # 物种级来源（只读 coconut.db）
        src_mode = str(getattr(a, "source", "auto") or "auto")
        cc_order = str(getattr(a, "coconut_order", "lib") or "lib")
        chp_on = bool(getattr(a, "chp_priority", False))
        # ★ C：中药成分的排序口径（marker=默认；ob=按 TCMSP 的 OB 降序）
        herb_order = str(getattr(a, "herb_order", "marker") or "marker")
        # ★ 「查找同名字段」开关（用户 2026-10-15）：**默认关**。关 = 你打什么就查什么；
        #   开 = 先弹查找窗口，列出同字段的药材条目与它们对应的基元植物，由你挑。
        lookup_on = bool(getattr(a, "herb_lookup", False))
        for h in doses:                       # 按首次出现顺序，每个名字只处理一次
            route = src_mode
            sp_out, how_sp = None, ""
            ev_stat = {}
            no_hint = False
            k = doses[h]                      # 该药材的份数（输入次数）
            _dn = dose_note.get(h, "")        # 份数从哪来：药典剂量 g / 用户重复输入
            egg = _egg(h)
            if egg:
                print("   🥚 %s「%s」" % (egg, h))
                print(T("   → 已**中止**，没有跑批。请换一个已收录的中药材中文名或双名法拉丁学名。",
                        "   → Aborted; no run. Use a known Chinese herb name or a Latin binomial."))
                return 2
            # ★ 中文名：同字段条目多于 1 个（炮制品 / 南北柴胡 / 药用部位）→ 选择窗口
            #   （用户 2026-10-15 追加）。排在 HERB 查找之前，精确命中也要先让用户看见
            #   "还有炙甘草/甘草节"这些兄弟条目。
            if (lookup_on and route == "auto" and only_one_name and h
                    and not re.search(r"[A-Za-z]", h)
                    and not getattr(a, "smiles", None)
                    and not getattr(a, "mol", None)):
                cw = build_choice_window(h)
                if cw:
                    choice_window = cw
                    _print_choices(cw)
                    no_hint = True
                    break
            if route == "auto" and re.search(r"[A-Za-z]", h):
                # ★ 只有带 ASCII 字母的输入才去建种名表：中文名直接走 HERB，省掉建表开销。
                #   三条**正向**判据，按先后来（用户 2026-10-15 明确）：
                #     ① 含药典部位词（Radix/Folium/Cortex…）→ 药材拉丁名 → HERB
                #     ② 命中 COCONUT 的种名字典 → 种名 → COCONUT
                #     ③ 单个词且是该属的属名 → **选择窗口**（列出该属全部物种，不直接跑）
                #   判据本身不是"有没有拉丁字母"——拉丁字母只用来决定"要不要查表"。
                #   ★ ③ 必须排在 HERB 之前：否则 "glycyrrhiza" 会被 HERB 的外文名子串匹配
                #     抢先命中「刺果甘草」，属名就永远弹不出选择窗口（实测过）。
                part = ""
                try:
                    part = CC.looks_like_drug_latin(h)
                except Exception as ex:              # noqa: BLE001 —— 打印，不静默
                    print("   [warn] 药材拉丁名守卫跳过（%s: %s）" % (type(ex).__name__, ex))
                if part:
                    route = "herb"
                    print("   名称 %s：含药典部位词「%s」→ 判为**药材拉丁名** → 走 HERB 药材库"
                          % (h, part))
                else:
                    try:
                        sp_out, how_sp = CC.looks_like_species(h)
                    except Exception as ex:          # noqa: BLE001 —— 打印，不静默
                        print("   [warn] 种名识别失败（%s: %s）→ 改走 HERB"
                              % (type(ex).__name__, ex))
                    if sp_out:
                        route = "coconut"
                    else:
                        route = "herb"
                        # ★ 属名（glycyrrhiza）：本身没有能直接跑的实体 → 列该属物种
                        if only_one_name:
                            cw = build_choice_window(h)
                            if cw:
                                choice_window = cw
                                print("   ⚠ 「%s」是**属名**：COCONUT 里有 %d 个物种"
                                      "——挑一个（也可直接改填双名法）："
                                      % (h, len(cw["items"])))
                                _print_choices(cw)
                                no_hint = True
                                break
            if route == "coconut":
                # 物种 → COCONUT：**植物化学的一等来源**，不是中药材查名的附件。
                # 库里 51,608 个物种含药用植物、真菌、海洋生物等，任何种名都能走这条。
                all_cs = CC.compounds_of_species(sp_out, limit=None, order=cc_order)
                src_tag = "coconut.db:%s" % sp_out
                order_txt = ("库内原序（cnp_id；不打分不排序）" if cc_order == "lib"
                             else "np_likeness 降序（开关已打开）")
                print("   物种 %s → COCONUT 植物化学库：%s（%s）"
                      "　【物种级来源，不限中药：植物/真菌/海洋生物皆可】"
                      % (h, sp_out, how_sp or "指定"))
                # ★ B（用户 2026-10-16）：COCONUT 自己没有"重要性"依据，就用结构比对
                #   去中药材库借：药典指标成分 > marker > TCMSP达标 > OB/DL。
                #   只标注，不筛选不排序；对不上的**不代表不重要**，只是这边没有依据。
                ev_stat = {}
                try:
                    import tcm_evidence as TEV
                    ev_stat = TEV.annotate(all_cs)
                    if ev_stat.get("n_found"):
                        print("      依据标注（按 InChIKey 比对中药材库）：%d / %d 个有依据"
                              " —— 药典指标 %d · marker %d · TCMSP达标 %d；其余 %d 个"
                              "**不代表不重要**，只是我们这边没有依据"
                              % (ev_stat["n_found"], ev_stat["n_total"], ev_stat["n_chp"],
                                 ev_stat["n_marker"], ev_stat["n_tcmsp"],
                                 ev_stat["n_total"] - ev_stat["n_found"]))
                except Exception as ex:                  # noqa: BLE001 —— 打印，不静默
                    print("   [warn] 依据标注失败（%s: %s）" % (type(ex).__name__, ex))
            else:
                # ★ 中文名走 HERB 时 route 一直停在 "auto"（只有拉丁输入那条分支才赋值），
                #   下游 `route == "herb"` 的判断因此全部落空、selection.source 也标错。
                route = "herb"
                all_cs = compounds_of_herb(h, limit=1_000_000, chp_first=chp_on,
                                           order_tcmsp=(herb_order == "ob"))   # 先全部取出（只读），再按开关截取
                src_tag = "tcm.db:%s" % h
                order_txt = ("药典判据优先（Tier-0 含量测定在前、同层按限量值降序）＋"
                             "marker 优先；其次分子量降序；按结构去重" if chp_on else
                             ("按 TCMSP 的 OB 降序（无 OB 者靠后）；只排序不筛选"
                              if herb_order == "ob" else
                              "marker 优先；其次分子量降序；按结构(SMILES)去重"))
                _m = dict(LAST_RESOLVE)
                if all_cs and _m.get("how") not in ("中文精确", ""):
                    print("   药材 %s → 命中「%s」（%s）" % (h, _m.get("matched"), _m.get("how")))
                if not all_cs and re.search(r"[A-Za-z]", h):
                    # 兜底：HERB 没命中但输入是拉丁/英文 → 试一次物种库
                    try:
                        sp_out, how_sp = CC.looks_like_species(h)
                    except Exception as ex:          # noqa: BLE001
                        sp_out, how_sp = None, ""
                        print("   [warn] 种名兜底识别失败（%s: %s）" % (type(ex).__name__, ex))
                    if sp_out:
                        all_cs = CC.compounds_of_species(sp_out, limit=None, order=cc_order)
                        src_tag = "coconut.db:%s" % sp_out
                        route = "coconut"
                        order_txt = ("库内原序（cnp_id；不打分不排序）" if cc_order == "lib"
                                     else "np_likeness 降序（开关已打开）")
                        print("   名称 %s：HERB 未命中 → 兜底走 COCONUT 植物化学库：%s（%s）"
                              % (h, sp_out, how_sp))
                    else:
                        # 「拼错了」：只在**失败路径**上才扫 5.1 万个种名，命中路径不付钱。
                        # （属名在上面就拦走了，这里不会再遇到属名。）
                        try:
                            sug = CC.suggest_species(h)
                        except Exception as ex:       # noqa: BLE001
                            sug = []
                            print("   [warn] 候选建议失败（%s: %s）"
                                  % (type(ex).__name__, ex))
                        if sug:
                            print("   ⚠ 没查到「%s」。也许你想找：%s"
                                  % (h, "、".join("%s(相似度 %.2f)" % (s, r)
                                                  for s, r in sug)))
                            no_hint = True
            # ★ 兜底（用户 2026-10-16）：HERB 里没有这个名字 → 查「中文药名 → 物种」
            #   （药典正文化的拉丁学名）→ 直接走 COCONUT。实测药典 617 味药材里 523 味
            #   能这样接上，包括 tcm.db 缺的那 12 味真缺口（杠板归 / 蓝布正 / 瓜子金…）。
            # ★ 炮制品闸（用户 2026-10-16）：药典收载的炮制品是独立药材，**不走物种兜底**。
            try:
                import processed as PR
                _is_proc = PR.is_processed(h)
                _proc_base = PR.base_of(h) if _is_proc else ""
            except Exception as ex:                      # noqa: BLE001
                _is_proc, _proc_base = False, ""
                print("   [warn] 炮制品闸查询失败：%s: %s" % (type(ex).__name__, ex))
            if _is_proc and not all_cs:
                print("   ⚠ %s 是**药典收载的炮制品**（基原：%s）——炮制品就是炮制品，"
                      "不替换成基原；本库暂无这一味。" % (h, _proc_base or "?"))
            if route == "herb" and not _is_proc and (not all_cs
                                                     or _m.get("how") in ("中文模糊",)):
                try:
                    import herb_species as HS
                    _sps = HS.species_of(h)
                except Exception as ex:                  # noqa: BLE001 —— 打印，不静默
                    _sps = []
                    print("   [warn] 中文药名→物种映射查询失败：%s: %s"
                          % (type(ex).__name__, ex))
                if _sps:
                    _merged, _seen_sm = [], set()
                    for _sp in _sps[:3]:
                        try:
                            for _c in CC.compounds_of_species(_sp, limit=None, order=cc_order):
                                if _c.smiles not in _seen_sm:
                                    _seen_sm.add(_c.smiles)
                                    _merged.append(_c)
                        except Exception as ex:              # noqa: BLE001
                            print("   [warn] COCONUT 取 %s 失败：%s: %s"
                                  % (_sp, type(ex).__name__, ex))
                    if _merged:
                        _why = ("HERB 药材库未收录" if not all_cs else
                                "HERB 只匹配到近名字条目「%s」" % _m.get("matched"))
                        if all_cs:
                            print("   ⚠ %s：%s（%d 个成分）——改用**药典收载的正品**"
                                  % (h, _why, len(all_cs)))
                        all_cs = _merged
                        route = "coconut"
                        sp_out = "、".join(_sps[:3])
                        src_tag = "药典物种:%s" % _sps[0]
                        how_sp = "药典正文物种兜底"
                        order_txt = ("库内原序（cnp_id；不打分不排序）"
                                     if cc_order == "lib"
                                     else "np_likeness 降序（开关已打开）")
                        print("   名称 %s：%s → **药典正文的物种兜底**：%s（拉丁原文：%s）"
                              % (h, _why, sp_out, "；".join(HS.latin_of(h)[:3])))
                        try:
                            import tcm_evidence as TEV
                            ev_stat = TEV.annotate(all_cs)
                        except Exception as ex:              # noqa: BLE001
                            print("   [warn] 依据标注失败：%s: %s" % (type(ex).__name__, ex))
                        no_hint = True
            if not all_cs and not no_hint:
                print("   ⚠ %s：没查到成分——可用「中药材中文名」（走 HERB 药材库，"
                      "如 甘草 / 白鲜皮），或「双名法拉丁学名」（走 COCONUT 植物化学库，"
                      "物种级，如 Glycyrrhiza uralensis）" % h)
            if not all_cs:
                # ★ 来自方剂展开的药材缺了**不中止整方**（方剂是数据，不是用户打错字）；
                #   用户手打的仍按"未收录就中止"处理。
                if h in from_formula:
                    print("      （方剂药材 %s 本库暂无 → 本次跳过，其余照跑）" % h)
                else:
                    missing_herbs.append(h)
            # ★ 剂量加权（开关 --dose-budget，默认关）：份数 k 的药材，成分配额 ×k。
            #   关掉时与旧行为完全一致（每味各取 lim 个）。
            lim_i = lim if (lim is None or not dose_on) else (lim * k)
            cs = all_cs if lim_i is None else all_cs[:lim_i]
            for c in cs:
                seeds.append((str(getattr(c, "name", "") or h),
                              str(getattr(c, "smiles", "") or ""),
                              src_tag + (("×%d" % k) if k > 1 else "")))
            def _nm(c):
                nm = str(getattr(c, "name", "") or "")
                info = getattr(c, "chp", None)
                if chp_on and info:
                    return "%s（药典：%s ≥ %s%%）" % (nm, info[3], info[1])
                ev = getattr(c, "evidence", "")
                if ev:
                    return "%s（%s）" % (nm, ev)
                return nm
            kept_names = [_nm(c) for c in cs]
            skip_names = [str(getattr(c, "name", "") or "") for c in all_cs[len(cs):]]
            selection[h] = {
                "n_available": len(all_cs), "n_kept": len(cs),
                "limit": ("all" if lim is None else lim),
                "limit_effective": ("all" if lim_i is None else lim_i),
                "n_doses": k,
                "dose_source": _dn or ("输入重复 %d 次" % k if k > 1 else ""),
                "evidence": ev_stat,
                "kept_names": kept_names,
                "skipped_n": len(skip_names),
                "skipped_names_preview": skip_names[:120],
                "source": route,
                "source_how": how_sp,
                "source_matched": sp_out or "",
                "order_rule": order_txt,
            }
            _dose_txt = ("" if k <= 1 else
                         ("（%s → %d 份%s）" % (_dn, k, "，配额 ×%d" % k if dose_on else "")
                          if _dn else
                          "（输入 %d 次 = %d 份%s）"
                          % (k, k, "，配额 ×%d" % k if dose_on else "")))
            print(T("   %s %s%s：可用成分 %d 个 → 本批取 %d 个（只读；%s）",
                    "   %s %s%s: %d available compounds -> selected %d (read-only; %s)")
                  % (("Species" if route == "coconut" else "Herb") if LANG == "en"
                     else ("物种" if route == "coconut" else "药材"),
                     h, _dose_txt, len(all_cs), len(cs), order_txt))
            # ★ A. 透明化：COCONUT 侧取的是"库内原序"的前 N 个 —— 那就是**任意取的**，
            #   必须说清楚，别让人误以为这 N 个是"挑出来的重要成分"。
            if route == "coconut" and cc_order == "lib" and len(cs) < len(all_cs):
                print("      ⚠ 顺序无化学依据（库内原序）：这 %d 个是从 %d 个里**任意截取**的，"
                      "不代表更重要；要看全部请把「每味取几个成分」设为全部"
                      % (len(cs), len(all_cs)))
            if route != "coconut" and herb_order == "ob":
                _n_ob = sum(1 for c in all_cs if getattr(c, "ob", None) is not None)
                _n_ok = sum(1 for c in all_cs if getattr(c, "tcmsp", False))
                print("      排序口径 OB（TCMSP）：%d 个有 OB 值，其中 %d 个满足"
                      " OB≥30%% 且 DL≥0.18 —— **只排序，未做任何筛选**"
                      % (_n_ob, _n_ok))
    if missing_herbs:
        # ★ 未收录就不跑（用户 2026-10-16）：原来会硬着头皮跑一遍，最后给一个空台账。
        print()
        print(T("✗ 有未收录的名字：%s", "✗ Unknown names: %s") % "、".join(missing_herbs))
        print(T("  已**中止**，没有跑批 —— 请换成已收录的名字再来：",
                "  Aborted; no run. Use a known name and retry:"))
        print(T("  * 网页：点那一行的「查找相似」，从候选里挑一个（会告诉你它是独苗还是未收录）",
                "  * Web: click “Find similar” on that row and pick a candidate"))
        print(T("  * 命令行：--herb 甘草 ／ --herb \"Glycyrrhiza uralensis\"",
                "  * CLI: --herb 甘草 / --herb \"Glycyrrhiza uralensis\""))
        return 2
    for sm in _split_list(getattr(a, "smiles", "") or ""):
        seeds.append((sm[:24], sm, "用户给定"))
    if getattr(a, "mol", None):
        seeds.append((a.mol[:24], a.mol, "用户给定"))
    if choice_window is not None and not seeds:
        # 需要用户拍板（属名 / 中文同字段多名）→ 只写一份 meta 给网页渲染选择窗口，
        # **不跑枚举**（没有底物）
        out_dir = Path(a.out) if a.out else (HERE / "out")
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        mp = out_dir / ("%s_%s.meta.json" % (ts, choice_window["query"]))
        mp.write_text(json.dumps({
            "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "kind": "choice_window",
            "choice_window": choice_window,
            "selection": {}, "switches": {}, "pair_coverage": {},
            "stats": {"n_products": 0, "n_paths_kept": 0, "seconds": 0},
            "notes": [
                ("输入的是**属名**（拉丁）。未跑枚举。请选物种（可多选）后重跑；"
                 "选中的物种会按双名法走 COCONUT 植物化学库。"
                 if choice_window["kind"] == "genus" else
                 "输入的**中文名**对应 HERB 里多个条目（炮制品 / 同名 / 药用部位）。"
                 "未跑枚举。请选条目（可多选）后重跑；选中的按 HERB 药材库走。"),
            ],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("   选择窗口数据已写出：%s（共 %d 个候选）"
              % (mp.name, len(choice_window["items"])))
        return 0
    if not seeds:
        print("没有底物：给 --herb / --smiles / --mol 之一")
        return 2

    fair = bool(getattr(a, "fair_pairs", False))
    cov = _pair_coverage(len(seeds), int(a.max_pairs), fair)
    if cov["pairs_used"] < cov["pairs_total"]:
        print("   ⚠ 对子预算 %d < 总对子 %d：**已截断**（%s 模式）——各成分伙伴数 %d~%d；"
              "提高 --max-pairs 或关注截断提示（结果已记录进 meta/报告）"
              % (a.max_pairs, cov["pairs_total"], cov["mode"],
                 cov["min_partners"], cov["max_partners"]))
    else:
        print("   对子预算 %d ≥ 总对子 %d：不截断（每个成分都能两两反应）"
              % (a.max_pairs, cov["pairs_total"]))

    switches = {
        "limit": ("all" if lim is None else lim),
        "rounds": int(a.rounds), "cond": str(a.cond),
        "triples": bool(a.triples),
        "fair_pairs": fair,
        "chp_priority": bool(getattr(a, "chp_priority", False)),
        "herb_source": str(getattr(a, "source", "auto") or "auto"),
        "coconut_order": str(getattr(a, "coconut_order", "lib") or "lib"),
        "dose_budget": bool(getattr(a, "dose_budget", False)),
        "doses": dict(doses),
        "herb_order": str(getattr(a, "herb_order", "marker") or "marker"),
        "max_pairs": int(a.max_pairs),
        "direction": (not bool(a.no_direction)),
        "score": (not bool(a.no_score)),
        "reagents": list(_split_list(a.reagents)),
    }
    # ★ 出处分档（第七十五轮 H1）：tier 随方剂进 meta 顶层的 formulas 与台账；
    #   versions 列出**全部**版本（含 AI 现查），供网页「按出处单独筛看」用 ——
    #   只是多显示信息，不改选版逻辑、不隐藏任何版本。
    formulas_meta = {
        k: {"source": v["source"],
            "source_display": v.get("source_display") or v["source"],
            "n_herbs": len(v["herbs"]),
            "n_versions": v.get("n_versions", 1),
            "tier": v.get("tier", -1),
            "tier_label": v.get("tier_label", "?"),
            "probe": v.get("probe"),
            "versions": ([{"source": v["source"],
                           "source_display": v.get("source_display") or v["source"],
                           "tier": v.get("tier", -1),
                           "tier_label": v.get("tier_label", "?"),
                           "probe": v.get("probe"),
                           "n_herbs": len(v["herbs"])}]
                         + [{"source": x["source"],
                             "source_display": x.get("source_display") or x["source"],
                             "tier": x.get("tier", -1),
                             "tier_label": x.get("tier_label", "?"),
                             "probe": x.get("probe"),
                             "n_herbs": x["n_herbs"]}
                            for x in v.get("alternatives", [])])}
        for k, v in formulas_used.items()}
    for _nm, _it in formulas_prov.items():
        _e = dict(formulas_meta.get(_nm) or {})
        _tier = _it.get("tier")
        if _tier is None:
            _tier = _e.get("tier", -1)
        _probe = _it.get("probe")
        if _probe is None:
            _probe = _e.get("probe")
        _e.update({
            "source": _it.get("source") or _e.get("source", ""),
            "source_display": (_it.get("source_display") or _it.get("source")
                               or _e.get("source_display", "")),
            "n_herbs": _it.get("n_herbs") or len(_it.get("final_herbs") or []),
            "n_versions": _it.get("n_versions") or _e.get("n_versions", 1),
            "tier": _tier,
            "tier_label": _it.get("tier_label") or _e.get("tier_label", "?"),
            "probe": _probe,
            "base_herbs": _it.get("base_herbs") or _e.get("base_herbs") or [],
            "final_herbs": _it.get("final_herbs") or _e.get("final_herbs") or [],
            "modifications": _it.get("modifications") or _e.get("modifications") or {},
            "doses": _it.get("doses") or _e.get("doses") or "",
        })
        _vs = _it.get("versions") or []
        if _vs:
            _e["versions"] = _vs
        formulas_meta[_nm] = _e
    spec = qb.RunSpec(seeds=seeds, cond_name=a.cond, rounds=a.rounds,
                      max_pairs=a.max_pairs, direction=not a.no_direction,
                      reagents=_split_list(a.reagents),
                      triples=bool(a.triples), triples_min_support=a.triples_min_support,
                      fair_pairs=fair, use_curated_templates=True,
                      use_mined_top_conditions=True,
                      meta_extra={"selection": selection, "switches": switches,
                                  "pair_coverage": cov, "formulas": formulas_meta})
    print("=" * 96)
    print(T("★ 一次枚举 ★  %s（底物 %d 个 · 轮数 %d · 条件「%s」）",
            "★ Single enumeration ★  %s (%d substrates · %d rounds · condition “%s”)")
          % (time.strftime("%Y-%m-%d %H:%M"), len(seeds), a.rounds, _cond_label(a.cond)))
    print("=" * 96)
    t0 = time.time()
    inv = qb.build_inventory(spec, score=not a.no_score, use_cache=not a.no_ik_cache)

    out_dir = Path(a.out) if a.out else (HERE / "out")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    if formulas_prov:
        tag = "+".join(list(formulas_prov)[:3])
    else:
        tag = (a.herb.split(",")[0].strip() if a.herb else "smiles")
    tag = re.sub(r'[\\/:*?"<>|]', "_", tag)[:40] or "run"
    pf, xf = qb.dump_inventory(inv, out_dir / f"{ts}_{tag}.csv", out_dir / f"{ts}_{tag}.tsv")
    try:
        import query_engine as qe
        qe.LANG = LANG
        qe.print_inv_summary(inv)
        qe._print_gate(inv)
        qe._print_direction(inv)
        qe._print_triples(inv)
        qe._print_cond_model(inv)
    except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
        print("   [warn] 摘要打印失败（台账已写出）：%s: %s" % (type(ex).__name__, ex))
    print(T("  台账 -> %s", "  Ledger -> %s") % pf)
    print(T("  索引 -> %s", "  Index -> %s") % xf)
    if not getattr(a, "no_report", False):
        try:
            import make_report as mr          # 引擎 tools\make_report.py（单一来源）
            mr.build_report(pf, lang=LANG)    # 默认输出到台账同目录 .report.html
        except Exception as ex:               # noqa: BLE001 —— 打印，不静默
            print("   [warn] 一页报告生成失败（台账/索引不受影响）：%s: %s"
                  % (type(ex).__name__, ex))
    # ★ 台账里带出处分档（第七十五轮 H1）：方名 + 本次用哪个档 + 该方名下 AI现查 版本数
    _ftxt = ""
    if formulas_meta:
        _pv_n = sum(1 for v in formulas_meta.values()
                    if (v.get("probe") or {}).get("verdict") == "查无")
        _pv_a = sum(1 for v in formulas_meta.values()
                    for x in (v.get("versions") or [])[1:]
                    if (x.get("probe") or {}).get("verdict") == "查无")
        _bits = []
        for _k, _v in formulas_meta.items():
            _md = _v.get("modifications") or {}
            _nrm = len(_md.get("removed") or [])
            _nad = len(_md.get("added") or [])
            _ai = sum(1 for x in (_v.get("versions") or [])[1:] if x.get("tier") == 5)
            _bit = "%s:%s(ai%d)" % (_k, _v.get("tier_label", "?"), _ai)
            if _nrm or _nad:
                _bit += "(-%d/+%d)" % (_nrm, _nad)
            _bits.append(_bit)
        _ftxt = " formula_tier=" + ",".join(_bits) + \
            (" probe_cha_wu=%d/%d" % (_pv_n, _pv_a) if (_pv_n or _pv_a) else "")
    _input_note = (("formulas:" + "+".join(list(formulas_prov)[:3]))
                   if formulas_prov else (a.herb or "(smiles)"))
    _log_run("predict",
             "herb=%s limit=%s rounds=%s cond=%s chp=%s fair=%s%s"
             % (_input_note, a.limit, a.rounds, a.cond,
                bool(getattr(a, "chp_priority", False)),
                bool(getattr(a, "fair_pairs", False)), _ftxt),
             {"csv": pf.name, "tsv": xf.name,
              "report": ("(未生成)" if getattr(a, "no_report", False)
                         else pf.stem + ".report.html")})
    print(T("  （只打标记：产物一条不删、不排序；查不到 ≠ 不存在）总耗时 %.1fs",
            "  (flags only: no products deleted, no ranking; not found ≠ nonexistent) "
            "total %.1fs") % (time.time() - t0))
    return 0


# ---------------------------------------------------------------- routes
def cmd_routes(a) -> int:
    global LANG
    LANG = "en" if str(getattr(a, "lang", "zh")) == "en" else "zh"
    if not _research_enabled():
        print("公开版已关闭任意目标逆合成路线。")
        return 3
    _bootstrap()
    import retro_search as rs
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")

    tm = Chem.MolFromSmiles(a.target)
    if tm is None:
        print(T("目标 SMILES 解析失败：", "Target SMILES parse failed: ") + a.target)
        return 2
    tgt = Chem.MolToSmiles(tm)

    templates = rs.load_rdchiral_templates(drop_blacklisted=bool(a.retro_blacklist))
    bl_note = "开" if a.retro_blacklist else "关（默认）"

    if a.pool_file or a.pool_csv:
        # 受限池口径：只用你给的这批底物（同 pool_query）
        import csv as _csv
        pool = []
        if a.pool_csv:
            with open(a.pool_csv, encoding="utf-8-sig", newline="") as f:
                for row in _csv.DictReader(f):
                    v = str(row.get(a.pool_col) or "").strip()
                    if v:
                        pool.append((str(row.get("source_name") or "")[:24], v))
            desc = "台账 %s 列 %s" % (a.pool_csv, a.pool_col)
        else:
            for line in Path(a.pool_file).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                pool.append((parts[0].strip(), parts[1].strip())
                            if len(parts) >= 2 else (line[:24], line))
            desc = "文件 " + a.pool_file
        avail, bad, seen = {}, 0, set()
        for nm, smi in pool:
            m = Chem.MolFromSmiles(str(smi or ""))
            if m is None:
                bad += 1
                continue
            cs = Chem.MolToSmiles(m)
            if cs in seen:
                continue
            seen.add(cs)
            try:
                k = Chem.MolToInchiKey(m)
            except Exception:
                bad += 1
                continue
            if k and k not in avail:
                avail[k] = "pool:" + str(nm or "?")
        print(T("池子：%s -> 去重 %d 个分子（解析失败 %d）",
                "Pool: %s -> %d unique molecules (%d parse failures)")
              % (desc, len(avail), bad))
        eng = rs.RetroSearch(templates, avail, blocks_full={}, blocks_skel={})
        mode = "受限池"
    else:
        av = rs.load_available()
        bf, bs = rs.load_purchasable_blocks()
        eng = rs.RetroSearch(templates, av, blocks_full=bf, blocks_skel=bs)
        mode = "全量终止集合（COCONUT + tcm.db + 可购砌块）"

    print("=" * 96)
    print(T("逆合成路线  %s", "Retrosynthetic routes  %s") % time.strftime("%Y-%m-%d %H:%M"))
    print("=" * 96)
    print(T("目标：%s", "Target: %s") % tgt)
    _mode_en = ("Restricted pool" if mode.startswith("受限池")
                else "Full terminal set (COCONUT + tcm.db + purchasable blocks)")
    _bl_en = "on" if bl_note.startswith("开") else ("off (default)" if "关" in bl_note else bl_note)
    print(T("模板：%d 条 · 黑名单：%s · 终止口径：%s",
            "Templates: %d · blacklist: %s · terminal set: %s")
          % (len(templates), _bl_en if LANG == "en" else bl_note,
             _mode_en if LANG == "en" else mode))
    routes, stat = eng.search(tgt, max_depth=a.depth, beam=a.beam)
    print(T("统计：", "Stats: ") + _stat_text(stat))
    if a.usable_only:
        n0 = len(routes)
        routes = [r for r in routes if getattr(r, "usable", True)]
        print(T("★ --usable-only：%d -> %d 条", "★ --usable-only: %d -> %d routes")
              % (n0, len(routes)))
    if not routes:
        print(T("结论：当前模板库 + 深度下没找到完整路线（不等于化学上不可能）。",
                "Conclusion: no complete route with the current templates and depth "
                "(this is not a proof of impossibility)."))
    out_dir = Path(a.out) if a.out else (HERE / "out")
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, rt in enumerate(routes[: a.show], 1):
        head = T("路线 %d（%d 步） 可用=%s 原因=%s",
                 "Route %d (%d steps) usable=%s reason=%s") % (
                     i, len(rt.steps), rt.usable, rt.unusable_reason)
        print(""); print(head)
        lines.append(head)
        for j, st in enumerate(rt.steps, 1):
            tags = [p + (T("[在池内]", "[in pool]") if eng.is_available(p)
                         else T("[不在池内]", "[not in pool]"))
                    for p in st.precursors]
            print("   %d. [%s]" % (j, st.reaction_name))
            print("      " + T("目标 ", "Target ") + st.target[:72])
            print("      " + T("前体 ", "Precursors ") + " | ".join(x[:72] for x in tags))
            lines += ["   %d. [%s]" % (j, st.reaction_name),
                      "      " + T("目标 ", "Target ") + st.target,
                      "      " + T("前体 ", "Precursors ") + " | ".join(tags)]
        print("      " + T("终点（落在终止集合的）：", "Terminals (in terminal set): ")
              + str(rt.terminals))
        lines.append("      " + T("终点：", "Terminals: ") + str(rt.terminals))
    if not routes:
        lines.append(T("结论：当前模板库 + 深度下没找到完整路线（不等于化学上不可能）。",
                       "Conclusion: no complete route with the current templates and depth "
                       "(this is not a proof of impossibility)."))
    ts = time.strftime("%Y%m%d-%H%M%S")
    rp = out_dir / ("%s_routes.txt" % ts)
    rp.write_text("\n".join(lines + ["", T("统计: ", "Stats: ") + _stat_text(stat)]),
                  encoding="utf-8")
    hp = None
    try:
        import make_report as mr                  # 引擎 tools\make_report.py（单一来源）
        hp = mr.build_routes_report(out_dir, tgt, routes, eng, stat,
                                    mode=mode, blacklist_note=bl_note,
                                    n_templates=len(templates), show_limit=a.show,
                                    pool_desc=(locals().get("desc") or ""),
                                    txt_name=rp.name, lang=LANG)
        print(T("  一页报告（HTML）-> %s", "  HTML report -> %s") % hp)
    except Exception as ex:                       # noqa: BLE001 —— 打印，不静默
        print("   [warn] routes 一页报告生成失败（txt 不受影响）：%s: %s"
              % (type(ex).__name__, ex))
    files = {"routes_txt": rp.name}
    if hp is not None:
        files["report"] = Path(hp).name
    _log_run("routes", "target=%s depth=%s show=%s" % (a.target[:48], a.depth, a.show),
             files)
    print("")
    print(T("  （不排序、不打分；可用性只打标记）路线报告 -> %s",
            "  (no ranking/scoring; usability is only a flag) Route report -> %s") % rp)
    return 0


# ---------------------------------------------------------------- history
def cmd_history(a) -> int:
    p = HERE / "out" / "runs.jsonl"
    if not p.exists():
        print("还没有运行记录（先跑 predict / routes）")
        return 0
    lines = p.read_text(encoding="utf-8").splitlines()[-max(1, int(getattr(a, "n", 20))):]
    for ln in lines:
        try:
            d = json.loads(ln)
        except Exception:
            print("  [坏行] " + ln[:90])
            continue
        print("  %s  %-7s %s" % (d.get("ts", "?"), d.get("kind", "?"),
                                 (d.get("note") or "")[:64]))
        fs = d.get("files") or {}
        if fs:
            print("        " + " · ".join("%s=%s" % (k, v) for k, v in fs.items()))
    return 0


# ---------------------------------------------------------------- info
def cmd_info(a) -> int:
    st = _bootstrap()
    print("chemreact 桥接（TCMAI）")
    print("  引擎目录：%s（存在=%s）" % (st, st.is_dir()))
    import retro_search as rs
    tmpl = rs.load_rdchiral_templates()
    bl = rs.load_retro_blacklist(verbose=False)
    n_noop = sum(1 for e in bl.values() if e.get("kind") == "noop")
    print("  逆模板：%d 条（可编译）· 黑名单：%d 条（no-op %d；默认关）"
          % (len(tmpl), len(bl), n_noop))
    try:
        from tcm_ro import open_db
        with open_db() as con:
            n = con.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
        print("  tcm.db（只读）：compounds %d 行 ✓" % n)
    except Exception as ex:
        print("  tcm.db（只读）: 打不开（%s: %s）" % (type(ex).__name__, ex))
    import platform
    print("  Python：%s %s" % (platform.python_version(), sys.executable))
    return 0


# ---------------------------------------------------------------- CLI
def main() -> int:
    ap = argparse.ArgumentParser(description="Christos（炼膏师）：TCMAI 的化学 AI 桥接")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("predict", help="枚举候选产物（台账 CSV + 索引 TSV）")
    pp.add_argument("--lang", default="zh", choices=("zh", "en"))
    pp.add_argument("--herb", default=None, help="中药名（逗号分隔多个；读 tcm.db，只读）")
    pp.add_argument("--smiles", default=None, help="逗号/分号分隔的 SMILES 列表")
    pp.add_argument("--mol", default=None, help="单个 SMILES（可重复用 --smiles）")
    pp.add_argument("--limit", default="12",
                    help="每味药取几个成分：整数或 all（不截取；注意对子预算，见运行提示）")
    pp.add_argument("--rounds", type=int, default=1, help="★轮数由你掌握★（默认 1）")
    pp.add_argument("--cond", default="煎煮",
                    help="条件档案名（默认 煎煮）。可用：煎煮/室温浸泡/水提/醇提/"
                         "酸水解/碱水解/酶催化/还原/氧化/无氧煎煮")
    pp.add_argument("--max-pairs", type=int, default=4000, dest="max_pairs")
    pp.add_argument("--fair-pairs", action="store_true", dest="fair_pairs",
                    help="对子超预算时公平截断：每个成分摊到大致相同的伙伴数（默认关=旧行为）")
    pp.add_argument("--chp-priority", action="store_true", dest="chp_priority",
                    help="按药典判据优先排序成分（Tier-0 含量测定成分在前；默认关）")
    pp.add_argument("--reagents", default="",
                    help="内部研究专用；公开版关闭（需 CHRISTOS_RESEARCH_MODE=1）")
    pp.add_argument("--triples", action="store_true", help="三组分模板（默认关；很慢）")
    pp.add_argument("--triples-min-support", type=int, default=2, dest="triples_min_support")
    pp.add_argument("--no-direction", action="store_true", dest="no_direction")
    pp.add_argument("--no-score", action="store_true", dest="no_score")
    pp.add_argument("--no-ik-cache", action="store_true", dest="no_ik_cache")
    pp.add_argument("--species", "--plant", default=None, dest="herb",
                    help="物种名（同 --herb，但语义正名）：双名法拉丁学名 → COCONUT 植物化学库，"
                         "不限中药（植物/真菌/海洋生物皆可）；中文名 → HERB 药材库")
    pp.add_argument("--herb-lookup", action="store_true", dest="herb_lookup",
                    help="打开「查找同名字段」：中文名先列出 HERB 的同字段条目"
                         "（炮制品 / 同名 / 药用部位）与它们对应的**基元植物**，由你勾选。"
                         "默认关（你打什么就查什么）")
    pp.add_argument("--dose-budget", action="store_true", dest="dose_budget",
                    help="剂量加权（默认关）：同一个名字输入 k 次 = 该药材 k 份，"
                         "其成分配额 ×k（剂量大的药多带成分）。关掉时每味各取 --limit 个。"
                         "无论开关如何，份数都会记进 meta/台账，且重复输入不会重复占对子预算")
    pp.add_argument("--herb-order", default="marker", dest="herb_order",
                    choices=("marker", "ob"),
                    help="中药材成分的排序口径：marker（默认，库标注指标成分优先）/ "
                         "ob（按 TCMSP 的 OB 口服生物利用度降序）。★ 只排序、不筛选，"
                         "产物一条不删；OB≥30%% 且 DL≥0.18 的成分会被标为 TCMSP 达标")
    pp.add_argument("--formula-provenance", default="", dest="formula_provenance",
                    help="网页方剂页传的 JSON：方名/版本/加减药味。只写入 meta 与台账，"
                         "不改预测；为空时行为与旧版完全一致。")
    pp.add_argument("--source", default="auto", choices=("auto", "herb", "coconut"),
                    help="名称的解释路线：auto（默认，自动判种名/药材名）/ "
                         "herb（强制走 tcm.db 药材库）/ coconut（强制走 COCONUT 植物化学库，"
                         "须给双名法学名）")
    pp.add_argument("--coconut-order", default="lib", dest="coconut_order",
                    choices=("lib", "npl"),
                    help="COCONUT 成分顺序：lib（默认，库内原序，不打分不排序）/ "
                         "npl（按 np_likeness 降序，需显式打开）")
    pp.add_argument("--out", default=None, help="输出目录（默认 本目录\\out）")
    pp.add_argument("--no-report", action="store_true", dest="no_report",
                    help="不生成一页 HTML 报告（默认生成）")
    pp.set_defaults(func=cmd_predict)

    pr = sub.add_parser("routes", help="逆合成：目标 -> 路线")
    pr.add_argument("--lang", default="zh", choices=("zh", "en"))
    pr.add_argument("--target", required=True, help="目标分子 SMILES")
    pr.add_argument("--pool-file", default=None, dest="pool_file",
                    help="受限池文件（每行 name\\tSMILES）")
    pr.add_argument("--pool-csv", default=None, dest="pool_csv",
                    help="受限池台账 CSV（配 --pool-col）")
    pr.add_argument("--pool-col", default="source_smiles", dest="pool_col")
    pr.add_argument("--depth", type=int, default=2)
    pr.add_argument("--beam", type=int, default=4)
    pr.add_argument("--show", type=int, default=3, help="打印前几条路线")
    pr.add_argument("--usable-only", action="store_true", dest="usable_only")
    pr.add_argument("--retro-blacklist", action="store_true", dest="retro_blacklist",
                    help="启用 never-usable 逆模板黑名单（默认关）")
    pr.add_argument("--out", default=None)
    pr.set_defaults(func=cmd_routes)

    pi = sub.add_parser("info", help="环境自检")
    pi.set_defaults(func=cmd_info)

    ph = sub.add_parser("history", help="最近的运行记录（本目录 out\\runs.jsonl）")
    ph.add_argument("-n", type=int, default=20, help="显示条数（默认 20）")
    ph.set_defaults(func=cmd_history)

    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())

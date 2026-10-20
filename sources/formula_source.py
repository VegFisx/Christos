# -*- coding: utf-8 -*-
r"""方剂记录的**出处可信度分层**（第七十五轮 H1，用户 2026-10-16 点单）。

任务书原话：给 ``formula_db.json`` 的**每条**记录打 ``source_tier``：

    内部 code：0 药典 / 1 ETCM / 2 ITCM / 3 CPMCP / 4 古籍 / 5 AI现查
    界面显示：药典 / ETCM / ITCM / CPMCP / 古籍 / AI 现查（未核对）

**判据只用已有的两个字段**（不新增任何人工判断、不手写任何名单）：

* 记录属「AI 现查」批 → ``category`` 字段**缺失**（与 ``formula_db_api_only.json``
  的那 5,332 条一致；实测两边的记录数、字段组合完全对得上）→ **tier 5**。
  这一条是**来源（provenance）标签**，不看它自称哪本书 ——
  AI 现查的记录里也有 40+ 条写着《中国药典》，那正是"出处可能编出来"要防的情形，
  所以照标 tier 5，同时在产出里单独统计「自称药典」的条数（只标注，不隐藏）。
* 其余记录按 ``chuchu`` 查表（实测 6,739 条的取值只有 5 种，全部可映射）：

    中国药典 / Pharmacopoeia → 0 ｜ ETCM → 1 ｜ ITCM → 2 ｜ CPMCP → 3 ｜
    Catalogue of Ancient Classic Prescriptions → 4 古籍

产出文件：``data/formula_source_tier.json``（由 ``tools/build_formula_source_tier.py``
生成；本模块运行时**不需要**读它 —— 判据就是下面这个纯函数，产出文件是留给审计的台账）。
自检：``python sources/formula_source.py``（打印 tier 分布 + 与产出文件核对）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FJ_DEFAULT = r"D:\TCMAI\data\formula_db.json"
ARTIFACT = Path(__file__).resolve().parent.parent / "data" / "formula_source_tier.json"

# ---- 层级定义（与任务书逐字一致）------------------------------------------
TIER_LABELS = {
    0: "药典",
    1: "ETCM",
    2: "ITCM",
    3: "CPMCP",
    4: "古籍",
    5: "AI 现查（未核对）",
}

# ``chuchu`` 子串 → tier（顺序即优先级；大小写不敏感）
SRC_TIER = (
    ("Pharmacopoeia", 0),
    ("中国药典", 0),
    ("ETCM", 1),
    ("ITCM", 2),
    ("CPMCP", 3),
    ("Catalogue of Ancient Classic Prescriptions", 4),
)

AI_TIER = 5


def tier_label(tier: int) -> str:
    return TIER_LABELS.get(int(tier), "? (%s)" % tier)


def tier_display(tier: int, source: str = "") -> str:
    """界面显示用：不暴露 0–5 编号；tier 0 再区分 2025 法定 / 2020 英文导入。"""
    t = int(tier)
    if t == 0:
        s = str(source or "")
        low = s.lower()
        if "chinese pharmacopoeia 2020" in low:
            return "药典 2020·英文导入（未核对）"
        if "中国药典2025" in s or "中国药典 2025" in s:
            return "药典 2025·法定"
        return "药典"
    return tier_label(t)


def tier_of_record(rec: dict) -> int:
    """单条记录 → tier。**纯函数**（生成脚本与运行时用同一个判据）。"""
    cat = str(rec.get("category") or "").strip()
    src = str(rec.get("chuchu") or "").strip()
    if not cat:
        # ★ AI 现查批：出处自称什么都不改判（自证不算证）
        return AI_TIER
    low = src.lower()
    for key, t in SRC_TIER:
        if key.lower() in low:
            return t
    # 认不出的出处：如实报出来，**不猜**
    raise ValueError("认不出的出处（chuchu=%r, category=%r）—— 请先看清数据再加规则" % (src, cat))


def tier_of_versions(name: str, path: str = FJ_DEFAULT) -> list:
    """某方名下的 tier 列表（顺序与 formula_db.json 里的记录顺序一致）。"""
    from formula import _load                                  # 同一个缓存，不重复读盘
    recs = _load(path).get(str(name or "").strip()) or []
    return [tier_of_record(r) for r in recs]


_ART_CACHE: Optional[dict] = None


def artifact(path: Path = ARTIFACT) -> dict:
    global _ART_CACHE
    if _ART_CACHE is None:
        try:
            _ART_CACHE = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as ex:                                 # noqa: BLE001
            print("   [warn] 读不到 tier 产出文件（%s: %s）" % (type(ex).__name__, ex))
            _ART_CACHE = {}
    return _ART_CACHE


def distribution(path: str = FJ_DEFAULT) -> dict:
    """全库 tier 分布（**实测**，不缓存 —— 只给自检/报告用）。"""
    from formula import _load
    cnt = {t: 0 for t in TIER_LABELS}
    unknown = []
    n = 0
    for nm, recs in _load(path).items():
        for i, r in enumerate(recs):
            n += 1
            try:
                t = tier_of_record(r)
            except ValueError as ex:
                unknown.append((nm, i, str(ex)))
                continue
            cnt[t] = cnt.get(t, 0) + 1
    return {"n_records": n, "counts": cnt, "unknown": unknown}


def _selftest() -> int:
    d = distribution()
    print("=" * 96)
    print("方剂出处分档（tier）分布 —— 实测自 formula_db.json")
    print("=" * 96)
    for t in sorted(TIER_LABELS):
        print("   %-10s %6d 条" % (tier_label(t), d["counts"].get(t, 0)))
    tot = sum(d["counts"].values())
    print("   %-10s %6d 条（含认不出出处的 %d 条）"
          % ("合计", tot, len(d["unknown"])))
    art = artifact()
    if art:
        same = (art.get("counts") or {}) == {str(k): v for k, v in d["counts"].items()}
        print("\n   产出文件 data/formula_source_tier.json：%s"
              % ("与实测一致 ✓" if same else "★ 与实测不一致，需重跑生成脚本 ★"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())

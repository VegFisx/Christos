# -*- coding: utf-8 -*-
r"""给「物种库成分」打上**中药材库的依据标签**（用户 2026-10-16，B 项）。

背景：COCONUT（物种级）里**没有任何"重要性"依据** —— ``np_likeness`` 测的是"像不像
天然产物"，实测甘草按它排前 5 都没有真正的指标成分甘草酸。而 ``tcm.db``（中药材）里有
三档真判据。两库按**规范结构**是能对上的（实测甘草 73/323 = 22.6%、白鲜皮 13/81、
银杏叶 34/293），所以做法是：**按 InChIKey 做结构比对，对得上的借它的标签**。

标签优先级（高到低）：

  1. ``药典指标成分`` —— 药典含量测定项（带限量值），最硬
  2. ``marker``        —— 库标注的指标成分
  3. ``TCMSP达标``     —— OB≥30% 且 DL≥0.18（TCMSP 经典口径；答的是"能不能口服吸收"）
  4. ``OB/DL``         —— 只有数值，未达上述口径
  5. ``''``（空）       —— **不是"不重要"，只是我们这边没有依据**

只标注，**不筛选、不排序、不删**。InChIKey 计算复用 ``core/query_base.inchikeys_of``
（子进程 + 超时保护：RDKit 在个别分子上会挂死，项目里已有实例）。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TCM_DEFAULT = r"D:\TCMAI\tcm.db"
_CHUNK = 400                     # SQLite 默认变量上限 999，留余量


def _ro(p: str) -> sqlite3.Connection:
    return sqlite3.connect("file:" + str(Path(p).resolve()).replace("\\", "/")
                           + "?mode=ro", uri=True)


def _f(x: Any):
    try:
        return float(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


def annotate(compounds: Sequence[Any], db_path: str = TCM_DEFAULT,
             use_cache: bool = True) -> Dict[str, Any]:
    """就地给每个 Compound 设 ``evidence`` / ``tcm_id`` / ``ob`` / ``dl``，并返回统计。"""
    from query_base import inchikeys_of, load_ik_cache     # core 已在本目录的 sys.path

    if not compounds:
        return {}
    smis = [str(getattr(c, "smiles", "") or "") for c in compounds]
    cache = None
    if use_cache:
        try:
            cache = load_ik_cache()
        except Exception:                                   # noqa: BLE001
            cache = None
    ik_map, ik_stat = inchikeys_of(smis, cache=cache)
    by_ik: Dict[str, List[Any]] = {}
    for c in compounds:
        ik = ik_map.get(str(getattr(c, "smiles", "") or ""))
        if ik:
            by_ik.setdefault(ik, []).append(c)

    wanth = list(by_ik)
    if not wanth:
        return {"n_total": len(compounds), "n_ik": 0, "n_found": 0,
                "n_chp": 0, "n_marker": 0, "n_tcmsp": 0,
                "ik_fail": int(ik_stat.get("fail", 0))}

    conn = _ro(db_path)
    try:
        row_by_ik: Dict[str, tuple] = {}
        for i in range(0, len(wanth), _CHUNK):
            part = wanth[i:i + _CHUNK]
            ph = ",".join("?" * len(part))
            for ik, iid, ob, dl in conn.execute(
                    f"SELECT inchi_key, ingredient_id, ob_score, drug_likeness "
                    f"FROM compounds WHERE inchi_key IN ({ph})", part):
                row_by_ik.setdefault(ik, (iid, ob, dl))
        markers = {r[0] for r in conn.execute(
            "SELECT DISTINCT ingredient_id FROM herb_compound WHERE match_level='marker'")}
    finally:
        conn.close()

    try:
        import chp_priority as CP
        chp_ids = {iid for g in CP.load_map().values() for iid in g}
    except Exception as ex:                                 # noqa: BLE001 —— 打印，不静默
        print("   [warn] 药典判据加载失败，本次不标「药典指标成分」：%s: %s"
              % (type(ex).__name__, ex))
        chp_ids = set()

    stat = {"n_total": len(compounds), "n_ik": len(by_ik), "n_found": 0,
            "n_chp": 0, "n_marker": 0, "n_tcmsp": 0,
            "ik_fail": int(ik_stat.get("fail", 0))}
    for ik, cs in by_ik.items():
        hit = row_by_ik.get(ik)
        if not hit:
            continue                      # 该分子不在中药材库里 → 无依据（不是"不重要"）
        iid, ob_raw, dl_raw = hit
        ob, dl = _f(ob_raw), _f(dl_raw)
        if iid in chp_ids:
            ev = "药典指标成分"
            stat["n_chp"] += 1
        elif iid in markers:
            ev = "marker"
            stat["n_marker"] += 1
        elif ob is not None and ob >= 30 and dl is not None and dl >= 0.18:
            ev = "TCMSP达标"
            stat["n_tcmsp"] += 1
        elif ob is not None or dl is not None:
            ev = "OB/DL"
        else:
            ev = ""
        stat["n_found"] += 1
        for c in cs:
            c.evidence = ev
            c.tcm_id = iid
            c.ob, c.dl = ob, dl
    return stat


def _selftest() -> int:
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    sys.path.insert(0, str(here.parent / "core"))
    import coconut as CC
    for sp in ("glycyrrhiza uralensis", "dictamnus dasycarpus", "ginkgo biloba"):
        cs = CC.compounds_of_species(sp)
        st = annotate(cs)
        print("%-26s 成分 %3d ｜ 算得 InChIKey %3d ｜ 中药材库对上 %3d"
              "（药典 %d / marker %d / TCMSP达标 %d）"
              % (sp, st.get("n_total", 0), st.get("n_ik", 0), st.get("n_found", 0),
                 st.get("n_chp", 0), st.get("n_marker", 0), st.get("n_tcmsp", 0)))
        for c in [c for c in cs if getattr(c, "evidence", "")][:6]:
            print("      [%s] %s" % (c.evidence, str(getattr(c, "name", ""))[:46]))
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())

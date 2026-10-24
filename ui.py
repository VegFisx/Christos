# -*- coding: utf-8 -*-
r"""Christos（炼膏师）三步页（真能点的版本）——本机小服务器 + 调用 chemreact.py。

启动：D:\TCMAI\venv\Scripts\python.exe ui.py   （或双击 start_ui.bat）
只绑 127.0.0.1；只写本目录 out\；引擎就是命令行那条路（chemreact.py predict），
所以"报告 / 留证 / 开关"与命令行完全一致。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PAGE = HERE / "ui_page.html"
# ★ 第七十五轮（桌面化）：引擎用哪个解释器可配置。
#   平时 = 当前解释器；打包成 Windows 桌面程序时，由 desktop.py 把 CHEMREACT_PY
#   指向用户 venv 里的 python.exe（exe 因此不必打包 500 MB 依赖）。
PY_EXE = os.environ.get("CHEMREACT_PY") or sys.executable
PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
STATE_FILE = OUT_DIR / "run_state.json"

RUNS: dict = {}
LOCK = threading.Lock()


def _research_enabled() -> bool:
    """Route search and free-form reagents are opt-in research features."""
    return os.environ.get("CHRISTOS_RESEARCH_MODE") == "1"


def _now() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def _safe_name(name: str) -> str:
    """只允许 中文/字母/数字/点/横线/下划线（防目录穿越）。"""
    return name if re.fullmatch(r"[\w\u4e00-\u9fff.\-]+", name or "") else ""


def _out_dir(form, key: str):
    """解析可选输出目录：空=默认 out\\；相对路径按本目录解析；建目录失败返回报错。"""
    x = str(form.get(key, "")).strip()
    if not x:
        return OUT_DIR, None
    p = Path(x)
    if not p.is_absolute():
        p = HERE / p
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as ex:
        return None, "输出目录不可用：%s" % ex
    return p, None


def _start_run(form: dict) -> dict:
    kind = str(form.get("kind", "predict")).strip()
    if kind == "routes":
        if not _research_enabled():
            return {"error": "公开版已关闭任意目标逆合成路线。"}
        target = str(form.get("target", "")).strip()
        if not target:
            return {"error": "请填目标分子 SMILES"}
        try:
            depth = str(max(1, min(4, int(form.get("depth", 2)))))
            show = str(max(1, min(10, int(form.get("show", 3)))))
        except ValueError:
            return {"error": "深度/显示条数要填数字"}
        od, err = _out_dir(form, "outdir_r")
        if err:
            return {"error": err}
        argv = [PY_EXE, "-u", str(HERE / "chemreact.py"), "routes",
                "--target", target, "--depth", depth, "--show", show,
                "--out", str(od)]
        lang = str(form.get("lang", "zh")).strip()
        if lang not in ("zh", "en"):
            lang = "zh"
        argv += ["--lang", lang]
        if str(form.get("usable_only")) in ("1", "true", "on"):
            argv.append("--usable-only")
        if str(form.get("retro_blacklist")) in ("1", "true", "on"):
            argv.append("--retro-blacklist")
        rid = _now() + "-" + str(int(time.time() * 1000) % 100000)
        log_path = OUT_DIR / ("ui_%s.log" % rid)
        with LOCK:
            busy = [r for r in RUNS.values()
                    if r.get("proc") is not None and r["proc"].poll() is None]
            if busy:
                return {"error": "已有一个任务在跑（%s）；等它完成再试。" % busy[0]["rid"]}
            f = open(log_path, "w", encoding="utf-8")
            proc = subprocess.Popen(argv, stdout=f, stderr=subprocess.STDOUT, cwd=str(HERE))
            RUNS[rid] = {"proc": proc, "log": log_path, "f": f, "out_dir": od,
                         "start": time.time(), "result": None,
                         "kind": "routes", "lang": lang,
                         "note": "target=%s depth=%s show=%s" % (target[:48], depth, show),
                         "state": "running", "cancelled": False, "interrupted": False}
            _persist_runs_locked()
        return {"id": rid}
    herb = str(form.get("herb", "")).strip()
    smi = str(form.get("smiles", "")).strip()
    if not herb and not smi:
        return {"error": "请填药材名（或分子 SMILES）"}
    limit = str(form.get("limit", "12"))
    if limit != "all" and not limit.isdigit():
        return {"error": "成分数量要填整数或 all"}
    try:
        rounds = str(max(1, min(5, int(form.get("rounds", 1)))))
        max_pairs = str(max(10, int(form.get("max_pairs", 4000))))
    except ValueError:
        return {"error": "轮数 / 对子预算要填数字"}
    cond = str(form.get("cond", "煎煮"))
    if str(form.get("reagents", "")).strip() and not _research_enabled():
        return {"error": "公开版已关闭辅助试剂输入。"}
    od, err = _out_dir(form, "outdir")
    if err:
        return {"error": err}
    argv = [PY_EXE, "-u", str(HERE / "chemreact.py"), "predict",
            "--limit", limit, "--rounds", rounds, "--cond", cond,
            "--max-pairs", max_pairs, "--out", str(od)]
    # 自定义条件：只在用户显式填了值时才覆盖预设档案
    for _key, _flag in (("solvent", "--solvent"),
                        ("temperature", "--temperature"),
                        ("time_min", "--time-min"),
                        ("ph", "--ph"),
                        ("catalyst", "--catalyst"),
                        ("atmosphere", "--atmosphere")):
        _v = str(form.get(_key, "") or "").strip()
        if _v:
            argv += [_flag, _v]
    if herb:
        argv += ["--herb", herb]
    else:
        argv += ["--smiles", smi]
    if str(form.get("triples")) in ("1", "true", "on"):
        argv.append("--triples")
    if str(form.get("fair_pairs")) in ("1", "true", "on"):
        argv.append("--fair-pairs")
    if str(form.get("chp_priority")) in ("1", "true", "on"):
        argv.append("--chp-priority")
    if str(form.get("herb_lookup")) in ("1", "true", "on"):
        argv.append("--herb-lookup")
    if str(form.get("dose_budget")) in ("1", "true", "on"):
        argv.append("--dose-budget")
    if str(form.get("herb_order") or "") == "ob":
        argv += ["--herb-order", "ob"]
    if str(form.get("reagents", "")).strip():
        argv += ["--reagents", str(form["reagents"]).strip()]
    fp = str(form.get("formula_provenance", "")).strip()
    if fp:
        if len(fp) > 20000:
            return {"error": "方剂出处信息过长（>20000 字符）"}
        argv += ["--formula-provenance", fp]
    lang = str(form.get("lang", "zh")).strip()
    if lang not in ("zh", "en"):
        lang = "zh"
    argv += ["--lang", lang]
    rid = _now() + "-" + str(int(time.time() * 1000) % 100000)
    log_path = OUT_DIR / ("ui_%s.log" % rid)
    with LOCK:
        busy = [r for r in RUNS.values()
                if r.get("proc") is not None and r["proc"].poll() is None]
        if busy:
            return {"error": "已有一个任务在跑（%s）；等它完成再试。" % busy[0]["rid"]}
        f = open(log_path, "w", encoding="utf-8")
        proc = subprocess.Popen(argv, stdout=f, stderr=subprocess.STDOUT,
                                cwd=str(HERE))
        RUNS[rid] = {"proc": proc, "log": log_path, "f": f, "out_dir": od,
                     "start": time.time(), "result": None,
                     "kind": "predict", "lang": lang,
                     "note": ("herb=%s" % herb) if herb else ("smiles=%s" % smi),
                     "state": "running", "cancelled": False, "interrupted": False}
        _persist_runs_locked()
    return {"id": rid}


def _find_result(out_dir, start: float) -> dict:
    """Find the newest report/CSV/TSV produced after a run started."""
    base = Path(out_dir or OUT_DIR)
    t0 = float(start) - 3
    try:
        cand = sorted((p for p in base.glob("*")
                       if p.stat().st_mtime >= t0
                       and p.name != "run_state.json"
                       and not p.name.startswith("run_state.")),
                      key=lambda p: -p.stat().st_mtime)
    except Exception:
        return {"report": "", "csv": "", "tsv": "", "meta": {}}
    rep = next((p.name for p in cand if p.suffix == ".html"), "")
    csvp = next((p.name for p in cand if p.suffix == ".csv"), "")
    tsv = next((p.name for p in cand if p.suffix == ".tsv"), "")
    meta = next((p for p in cand if p.suffix == ".json"), None)
    meta_info = {}
    if meta is not None:
        try:
            meta_info = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            meta_info = {}
    if not isinstance(meta_info, dict):
        meta_info = {}
    return {"report": rep, "csv": csvp, "tsv": tsv, "meta": meta_info}


def _persist_runs_locked() -> None:
    """Persist lightweight run state (never the Popen object). Caller holds LOCK."""
    try:
        items = []
        for rid, r in RUNS.items():
            if not rid:
                continue
            res = r.get("result") or {}
            st = ("interrupted" if r.get("interrupted") else
                  ("cancelled" if r.get("cancelled") else
                   ("done" if r.get("state") == "done" else
                    ("error" if r.get("state") == "error" else "running"))))
            items.append({
                "rid": rid, "kind": r.get("kind", "predict"),
                "note": r.get("note", ""),
                "log": Path(r["log"]).name if r.get("log") else "",
                "out_dir": str(r.get("out_dir") or OUT_DIR),
                "start": float(r.get("start") or time.time()),
                "end": float(r["end"]) if r.get("end") else None,
                "seconds": r.get("seconds"),
                "lang": r.get("lang", "zh"), "state": st,
                "cancelled": bool(r.get("cancelled")),
                "interrupted": bool(r.get("interrupted")),
                "result": {k: res.get(k, "") for k in ("report", "csv", "tsv")},
            })
        items = sorted(items, key=lambda x: x["start"])[-200:]
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    except Exception as ex:                    # noqa: BLE001 —— 状态保存失败不能拖垮服务
        print("   [warn] 运行状态保存失败：%s: %s" % (type(ex).__name__, ex))


def _append_interrupted_history(rid: str, e: dict, result: dict) -> None:
    try:
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": "interrupted",
               "note": "run %s interrupted by server restart (partial files kept)" % rid,
               "files": {k: result.get(k, "") for k in ("report", "csv", "tsv")}}
        with open(OUT_DIR / "runs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as ex:                    # noqa: BLE001
        print("   [warn] 中断记录写入失败：%s: %s" % (type(ex).__name__, ex))


def _load_runs() -> None:
    """Rehydrate run state after a server restart; running jobs become interrupted."""
    if not STATE_FILE.exists():
        return
    try:
        items = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as ex:                    # noqa: BLE001
        print("   [warn] 运行状态读取失败：%s: %s" % (type(ex).__name__, ex))
        return
    if not isinstance(items, list):
        return
    changed = False
    with LOCK:
        for e in items:
            if not isinstance(e, dict):
                continue
            rid = str(e.get("rid") or "").strip()
            if not rid or rid in RUNS:
                continue
            log_name = str(e.get("log") or "")
            log = OUT_DIR / log_name if log_name else OUT_DIR / ("ui_%s.log" % rid)
            out = Path(e.get("out_dir") or OUT_DIR)
            start = float(e.get("start") or time.time())
            result = {k: (e.get("result") or {}).get(k, "") for k in ("report", "csv", "tsv")}
            state = str(e.get("state") or "")
            interrupted = bool(e.get("interrupted"))
            cancelled = bool(e.get("cancelled"))
            if state == "running" and not interrupted and not cancelled:
                interrupted = True
                changed = True
                try:
                    with open(log, "a", encoding="utf-8") as f:
                        f.write("\n[server] 服务重启：该任务被标记为已中断；已生成的部分文件保留。\n")
                except Exception:
                    pass
                part = _find_result(out, start)
                if part.get("report") or part.get("csv") or part.get("tsv"):
                    result = {k: part.get(k, "") for k in ("report", "csv", "tsv")}
                _append_interrupted_history(rid, e, result)
            RUNS[rid] = {
                "proc": None, "f": None, "log": log, "out_dir": out,
                "start": start, "end": e.get("end"),
                "seconds": e.get("seconds") or 0,
                "result": result, "cancelled": cancelled,
                "interrupted": interrupted,
                "kind": e.get("kind", "predict"),
                "lang": e.get("lang", "zh"),
                "note": e.get("note", ""),
                "state": ("interrupted" if interrupted else
                          ("cancelled" if cancelled else
                           (state if state in ("done", "error") else "done"))),
            }
        if changed:
            _persist_runs_locked()


def _status_rehydrated(r: dict) -> dict:
    try:
        tail = Path(r["log"]).read_text(encoding="utf-8", errors="replace")[-1800:]
    except Exception:
        tail = ""
    st = r.get("state") or ("interrupted" if r.get("interrupted") else "done")
    out = {"state": st, "tail": tail, "seconds": r.get("seconds") or 0}
    if st == "done":
        out["rc"] = 0
    if r.get("result"):
        out.update(r["result"])
    if r.get("cancelled"):
        out["cancelled"] = True
    if r.get("interrupted"):
        out["interrupted"] = True
    return out


def _status(rid: str) -> dict:
    with LOCK:
        r = RUNS.get(rid)
    if not r:
        return {"error": "没有这个任务"}
    if r.get("proc") is None:
        return _status_rehydrated(r)
    with LOCK:
        rc = r["proc"].poll()
    state = ("running" if rc is None else
             ("cancelled" if r.get("cancelled") else ("done" if rc == 0 else "error")))
    if rc is not None and r["result"] is None:
        try:
            r["f"].close()
        except Exception:
            pass
        r["result"] = _find_result(r.get("out_dir") or OUT_DIR, r["start"])
        r["state"] = state
        r["end"] = time.time()
        r["seconds"] = round(r["end"] - r["start"], 1)
        with LOCK:
            _persist_runs_locked()
    try:
        tail = r["log"].read_text(encoding="utf-8", errors="replace")[-1800:]
    except Exception:
        tail = ""
    out = {"state": state, "tail": tail, "seconds": round(time.time() - r["start"], 1)}
    if rc is not None:
        out["rc"] = rc
    if r["result"]:
        out.update(r["result"])
    if r.get("cancelled"):
        out["cancelled"] = True
    return out


def _stop_run(rid: str) -> dict:
    """终止一个正在跑的任务；保留已生成的部分文件，不删除。"""
    with LOCK:
        r = RUNS.get(rid)
        if not r:
            return {"error": "没有这个任务"}
        proc = r.get("proc")
        if proc is None:
            return {"error": "该任务不是当前进程在跑（可能已中断）"}
        if proc.poll() is not None:
            return {"id": rid, "stopped": False, "state": "done"}
        r["cancelled"] = True
        r["state"] = "cancelled"
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception as ex:                    # noqa: BLE001 —— 失败要回给 UI
            r["cancelled"] = False
            r["state"] = "running"
            return {"error": "终止失败：%s: %s" % (type(ex).__name__, ex)}
        r["end"] = time.time()
        r["seconds"] = round(r["end"] - r["start"], 1)
        _persist_runs_locked()
    return {"id": rid, "stopped": True}


def _lookup_raw(q: str) -> dict:
    """「查找相似」的后端：**在服务器进程内**直接算，不新起进程、不跑枚举。

    好处：COCONUT 的 5.1 万种名表只在第一次调用时建一次，之后每次不到 100 ms，
    所以按钮可以做到"点了就出"——不必先跑一遍枚举再看窗口。
    """
    q = str(q or "").strip()
    if not q:
        return {"query": "", "kind": "", "choices": []}
    import chemreact as CR                     # 同目录的桥接层（含 _bootstrap）
    CR._bootstrap()
    # ★ 方剂优先（第七十五轮修正：`生脉饮` 曾因只查药材/物种库而被误判「未收录」）
    try:
        import formula as FM
        if FM.is_formula_name(q):
            g = FM.get_formula(q)
            n = len(g["herbs"]) if g else 0
            return {"query": q, "kind": "formula",
                    "choices": [{"group": "方剂", "name": q, "n_compounds": n,
                                 "note": "方剂：按典籍版本展开成 %d 味" % n}]}
    except Exception as ex:                    # noqa: BLE001 —— 打印，不静默
        print("   [warn] 方剂查找失败：%s: %s" % (type(ex).__name__, ex))
    cw = CR.build_choice_window(q)
    if not cw:
        # ★ 未收录时给出**相似方名**（只提示，不自动选）——用户 2026-10-17：三黄汤 → 三黄泻心汤/三黄片
        sugg = []
        try:
            import formula as FM2
            sugg = [{"group": "方剂(相似)", "name": k, "n_compounds": 0,
                     "note": "相似方名（点「查找相似」后勾选）"} for k in FM2.similar_formulas(q, limit=8)]
        except Exception:                    # noqa: BLE001
            pass
        return {"query": q, "kind": "", "choices": sugg}
    out = {"query": cw["query"], "kind": cw["kind"], "choices": cw["items"]}
    # ★ 单段拉丁词（uralensis / glycyrrhiza）→ 按**种加词/属名**反查物种
    if cw.get("kind") in ("missing", "") and q.isascii() and q.isalpha() and len(q) >= 3:
        try:
            import coconut as CO
            have = {x.get("name") for x in out["choices"]}
            for sp in CO.species_by_word(q, limit=30):
                if sp not in have:
                    out["choices"].append({
                        "group": "物种", "name": sp, "n_compounds": 0,
                        "note": "按种加词/属名匹配（COCONUT）"})
            if out["choices"]:
                # 有真实物种命中时，去掉「未收录」占位项（第七十五轮分级查找）
                out["choices"] = [c for c in out["choices"]
                                  if c.get("group") != "未收录"]
                out["kind"] = "species"
        except Exception as ex:                # noqa: BLE001 —— 打印，不静默
            print("   [warn] 种加词反查失败：%s: %s" % (type(ex).__name__, ex))
    # ★ 未收录时追加**相似方名**（只提示，不自动选）——用户 2026-10-17：三黄汤 → 三黄泻心汤/三黄片
    if cw.get("kind") == "missing":
        try:
            import formula as FM2
            have = {x.get("name") for x in out["choices"]}
            for k in FM2.similar_formulas(q, limit=8):
                if k not in have:
                    out["choices"].append({"group": "方剂(相似)", "name": k,
                                           "n_compounds": 0,
                                           "note": "相似方名：勾选后按方剂展开"})
        except Exception as ex:                # noqa: BLE001 —— 打印，不静默
            print("   [warn] 相似方名查询失败：%s: %s" % (type(ex).__name__, ex))
    if cw.get("message"):                      # 彩蛋那句话要原样带出去
        out["message"] = cw["message"]
    return out


_CHP_NAMES = None


def _chp_names() -> set:
    """药典判据覆盖的药材名（只用于查找结果分档，不改任何数据）。"""
    global _CHP_NAMES
    if _CHP_NAMES is None:
        try:
            import chp_priority
            _CHP_NAMES = set(chp_priority.load_map().keys())
        except Exception as ex:                    # noqa: BLE001 —— 分档失败不中止查找
            print("   [warn] 药典判据名表加载失败：%s: %s" % (type(ex).__name__, ex))
            _CHP_NAMES = set()
    return _CHP_NAMES


def _choice_tier(c: dict) -> tuple:
    g = str(c.get("group") or "")
    note = str(c.get("note") or "")
    if g.startswith("方剂"):
        return "formula", "方剂"
    if g in ("基元植物", "物种"):
        return "coconut", "基元植物（COCONUT）"
    if g == "未收录":
        return "missing", "未收录"
    if g == "药材":
        if "别名" in note:
            return "alias", "别名候选"
        if str(c.get("name") or "") in _chp_names():
            return "chp", "药材 · 药典判据"
        return "herb", "药材 · 库内"
    return "other", "其他"


_TIER_ORDER = ("formula", "chp", "herb", "coconut", "alias", "other", "missing")


def _grade_lookup(out: dict, q: str) -> dict:
    """在原有 /lookup 结果上补：域 / 粒度 / 来源档计数（不改 choices 本身）。"""
    q = str(q or "").strip()
    kind = str(out.get("kind") or "")
    choices = out.get("choices") or []

    if kind == "formula":
        domain, gran = "formula", "方剂全名"
    elif re.search(r"[\u4e00-\u9fff]", q):
        domain = "chinese"
        if kind == "alias":
            gran = "别名（多候选）"
        elif kind == "herb":
            gran = "正名" if any(c.get("name") == q for c in choices) else "包含匹配"
        elif kind == "missing":
            gran = "无匹配"
        else:
            gran = "中文名"
    elif re.search(r"[A-Za-z]", q):
        domain = "latin"
        if kind == "genus":
            gran = "属名/同属" if len(q.split()) == 1 else "种名/同属"
        elif kind == "species":
            gran = "种加词"
        elif kind == "herb":
            gran = "药材拉丁名"
        elif kind == "missing":
            gran = "无匹配"
        else:
            gran = "拉丁名"
    elif q:
        domain, gran = "smiles", "SMILES"
    else:
        domain, gran = "unknown", "空输入"

    buckets: dict = {}
    for c in choices:
        key, label = _choice_tier(c)
        b = buckets.setdefault(key, {"key": key, "label": label, "count": 0,
                                     "items": []})
        b["count"] += 1
        b["items"].append(c)
    # 展示顺序：精确名优先 → 成分数多者在前 → 名字；别名档保留索引原序
    # （这是查找候选的组织方式，不是对产物打分/排序）
    for key, b in buckets.items():
        if key != "alias":
            b["items"].sort(key=lambda c: (
                0 if c.get("name") == q else 1,
                -(c.get("n_compounds") or 0),
                str(c.get("name") or ""),
            ))
        b["items"] = b["items"][:50]
    tiers = [buckets[k] for k in _TIER_ORDER if k in buckets]
    out["domain"] = domain
    out["granularity"] = gran
    out["tiers"] = tiers
    return out


def _lookup(q: str) -> dict:
    return _grade_lookup(_lookup_raw(q), q)


def _formula(name: str) -> dict:
    """方剂页：返回一个方名下的全部版本（组成 / 剂量 / 出处档 / 抽检）。"""
    name = str(name or "").strip()
    if not name:
        return {"error": "请填方剂名"}
    try:
        import chemreact as CR
        # ★ 彩蛋（第七十六轮）：方剂页与药材查找共用同一张关键词表；只提示，不碰库。
        _egg = CR._egg(name)
        if _egg:
            return {"name": name, "versions": [], "kind": "egg", "message": _egg}
        CR._bootstrap()
        import formula as FM
        vs = FM.formula_versions(name)
    except Exception as ex:                        # noqa: BLE001
        return {"error": "方剂查询失败：%s: %s" % (type(ex).__name__, ex)}
    if not vs:
        known = False
        sug = []
        try:
            known = bool(FM.is_formula_name(name))
            # 只给候选，不自动选；精确名本身不在候选里重复出现。
            sug = [x for x in FM.similar_formulas(name, limit=8) if x != name]
        except Exception as ex:                    # noqa: BLE001 —— 建议失败不改变主错误
            print("   [warn] 方剂相似名查询失败：%s: %s" % (type(ex).__name__, ex))
        return {"name": name, "versions": [],
                "error": ("该方名已收录，但组成未能解析" if known else "未收录该方剂"),
                "suggestions": [{"name": x} for x in sug]}
    out = []
    for v in vs:
        out.append({
            "source": v.get("source") or "",
            "source_display": v.get("source_display") or v.get("source") or "",
            "tier": v.get("tier", -1),
            "tier_label": v.get("tier_label") or "?",
            "probe": v.get("probe"),
            "gongxiao": v.get("gongxiao") or "",
            "category": v.get("category") or "",
            "peifang": v.get("peifang") or "",
            "herbs": v.get("herbs") or [],
            "grams": v.get("grams") or {},
            "dose_multiples": v.get("dose_multiples") or {},
            "unmatched": v.get("unmatched") or [],
            "url": v.get("url") or "",
        })
    # 仅用于方剂页展示：先按出处档（药典 → AI 现查（未核对）），
    # 同档优先带法定剂量的，再按味数；不改 CLI 的选版逻辑。
    out.sort(key=lambda x: (x["tier"] if x["tier"] >= 0 else 99,
                            0 if x["dose_multiples"] else 1,
                            -len(x["herbs"])))
    return {"name": vs[0].get("name") or name, "n_versions": len(out),
            "versions": out}


def _history(limit: int = 40) -> dict:
    """侧边栏历史：读 out\\runs.jsonl（只读，不删不改）。"""
    p = OUT_DIR / "runs.jsonl"
    if not p.is_file():
        return {"runs": []}
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception as ex:                        # noqa: BLE001
        return {"error": "%s: %s" % (type(ex).__name__, ex), "runs": []}
    runs = []
    for ln in reversed(lines):
        ln = ln.strip()
        if not ln:
            continue
        try:
            runs.append(json.loads(ln))
        except Exception:
            continue
        if len(runs) >= max(1, min(200, limit)):
            break
    return {"runs": runs}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):        # 安静一点
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/index.html"):
            if not PAGE.exists():
                return self._send(500, b"ui_page.html missing", "text/plain; charset=utf-8")
            return self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        if u.path == "/status":
            rid = urllib.parse.parse_qs(u.query).get("id", [""])[0]
            return self._send(200, json.dumps(_status(rid), ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        if u.path == "/shutdown":          # 本机专用：测试/收工时停服务器
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return self._send(200, b"bye", "text/plain; charset=utf-8")
        if u.path == "/lookup":            # ★「查找相似」：不跑批，立刻返回候选
            qq = urllib.parse.parse_qs(u.query).get("q", [""])[0].strip()
            try:
                res = _lookup(qq)
            except Exception as ex:        # noqa: BLE001 —— 打印，不静默
                print("   [warn] /lookup 失败：%s: %s" % (type(ex).__name__, ex))
                res = {"query": qq, "kind": "", "choices": [],
                       "error": "%s: %s" % (type(ex).__name__, ex)}
            return self._send(200, json.dumps(res, ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        if u.path == "/formula":           # ★ 方剂页：全部版本 / 剂量 / 出处档
            nm = urllib.parse.parse_qs(u.query).get("name", [""])[0].strip()
            try:
                res = _formula(nm)
            except Exception as ex:        # noqa: BLE001
                print("   [warn] /formula 失败：%s: %s" % (type(ex).__name__, ex))
                res = {"error": "%s: %s" % (type(ex).__name__, ex), "versions": []}
            return self._send(200, json.dumps(res, ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        if u.path == "/history":           # ★ 侧边栏历史：只读 out\runs.jsonl
            try:
                lim = int(urllib.parse.parse_qs(u.query).get("limit", ["40"])[0])
            except ValueError:
                lim = 40
            try:
                res = _history(lim)
            except Exception as ex:        # noqa: BLE001
                res = {"error": "%s: %s" % (type(ex).__name__, ex), "runs": []}
            return self._send(200, json.dumps(res, ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        if u.path.startswith("/files/"):
            name = _safe_name(urllib.parse.unquote(u.path[len("/files/"):]))
            rid = urllib.parse.parse_qs(u.query).get("rid", [""])[0]
            base = OUT_DIR
            if rid:
                base = (RUNS.get(rid) or {}).get("out_dir") or OUT_DIR
            else:
                # 历史记录没有 rid：在本进程跑过的自定义输出目录里找同名文件
                with LOCK:
                    for r in RUNS.values():
                        d = r.get("out_dir") or OUT_DIR
                        if (d / name).is_file():
                            base = d
                            break
            fp = base / name
            if not name or not fp.is_file():
                return self._send(404, b"not found", "text/plain; charset=utf-8")
            ctype = {".html": "text/html; charset=utf-8", ".csv": "text/csv; charset=utf-8",
                     ".tsv": "text/tab-separated-values; charset=utf-8",
                     ".json": "application/json; charset=utf-8"}.get(
                         fp.suffix, "application/octet-stream")
            return self._send(200, fp.read_bytes(), ctype)
        return self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path.startswith("/stop"):
            qs = urllib.parse.urlparse(self.path).query
            rid = urllib.parse.parse_qs(qs).get("id", [""])[0]
            res = _stop_run(rid)
            code = 400 if "error" in res else 200
            return self._send(code, json.dumps(res, ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        if self.path != "/run":
            return self._send(404, b"not found", "text/plain; charset=utf-8")
        n = int(self.headers.get("Content-Length") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8", "replace"))
        flat = {k: v[0] for k, v in form.items()}
        res = _start_run(flat)
        code = 409 if "error" in res else 200
        return self._send(code, json.dumps(res, ensure_ascii=False).encode("utf-8"),
                          "application/json; charset=utf-8")


def main() -> int:
    _load_runs()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = "http://127.0.0.1:%d/" % PORT
    print("Christos（炼膏师）三步页已启动：%s（Ctrl+C 退出）" % url)
    if "--no-browser" not in sys.argv:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with LOCK:
            for r in RUNS.values():
                if r.get("proc") is not None and r["proc"].poll() is None:
                    r["proc"].terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())

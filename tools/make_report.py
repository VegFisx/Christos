# -*- coding: utf-8 -*-
r"""一页式报告生成器（方案 C）：把产物台账 CSV 渲染成人能读的单文件 HTML。

用法:
  python tools\make_report.py <台账.csv> [--out 输出.html]

* 自动找同名 .meta.json（枚举条件/轮数/耗时）
* 两张表：产物表（按分子去重，带方向/出处汇总）+ 出处明细表（逐条路径）
* 附分布小图（方向 / 分子量 / 每轮新增）与判据口径附录
* 页内提供"方向筛选/关键词过滤"（纯展示层；不改数据、不排序）
* 运行记录块：成分取舍（取谁 / 共多少 / 谁没参与）+ 开关状态 + 对子截断提示（读 .meta.json）
* 分子结构图：RDKit 现场绘制（可选；没有 RDKit 时跳过并提示；超量只画前 MAXDRAW 个）
* 输出为单文件 HTML（自带样式与脚本，离线可开）
* 也可被 TCMAI 桥接直接调用：build_report(csv_path, out_path)（predict 默认自动生成）
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import sys
import time
from collections import Counter, OrderedDict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ★ 第八十六轮：反应路径视图需要 core/reaction_paths.py。
# 这个脚本平时由 chemreact.py 调用（那里已经把 core/conditions 放进 sys.path），
# 但也要能单独 `python tools\make_report.py 台账.csv` 跑 —— 所以这里自己兜一次。
_ROOT = Path(__file__).resolve().parent.parent
for _sub in ("core", "conditions", "tools"):
    _p = str(_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import reaction_paths as rp        # noqa: E402
except Exception as _ex:               # noqa: BLE001 —— 打印，不静默降级
    rp = None
    print("   [warn] 反应路径模块不可用（%s）；报告仍会生成，但没有路径视图" % _ex)

# 第八十九轮：逐跳立体判断（可选依赖；不可用时只是不显示这一栏）
try:
    import judge_stereo_hops as jst    # noqa: E402
except Exception as _ex:               # noqa: BLE001
    jst = None
    print("   [warn] 立体判断模块不可用（%s）；路径里不显示立体结论" % _ex)


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def load_rows(csv_path: Path):
    rows = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("product_smiles"):
                rows.append(r)
    return rows


def load_meta(csv_path: Path):
    meta = None
    cand = csv_path.parent / (csv_path.stem + ".meta.json")
    if cand.exists():
        try:
            return json.loads(cand.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _classify_gate(why) -> str:
    """条件依据 -> 四类。口径与引擎 core/query_base.classify_activation 完全一致
    （本脚本是纯展示层、只依赖标准库，所以在这里复刻同一套字符串规则）。"""
    w = str(why or "").strip()
    if not w:
        return "依据未记录"
    if "无 ORD 条件数据" in w or "无数据" in w or "放行" in w or "按中性处理" in w:
        return "无数据放行"
    if ("降权" in w) or ("不在" in w) or ("超出" in w):
        return "降权"
    return "窗口命中"


def _bars_svg(counter, width=320, row_h=20, label_w=76, color="#2b6cb0") -> str:
    items = counter.most_common()
    if not items:
        return ""
    maxv = max(v for _, v in items) or 1
    height = len(items) * row_h + 6
    parts = ["<svg width='%d' height='%d' role='img'>" % (width, height)]
    for i, (k, v) in enumerate(items):
        y = i * row_h + 3
        wpx = max(2, int((width - label_w - 46) * v / maxv))
        parts.append("<text x='0' y='%d' font-size='12'>%s</text>" % (y + 12, esc(k)))
        parts.append("<rect x='%d' y='%d' width='%d' height='13' fill='%s'/>" % (label_w, y, wpx, color))
        parts.append("<text x='%d' y='%d' font-size='11'>%d</text>" % (label_w + wpx + 4, y + 11, v))
    parts.append("</svg>")
    return "".join(parts)


def _hist_svg(values, edges=(0, 200, 300, 400, 500, 700, 1000, 2000), width=320, height=132) -> str:
    vals = [v for v in values if v is not None]
    if not vals:
        return ""
    counts = [sum(1 for v in vals if lo <= v < hi) for lo, hi in zip(edges[:-1], edges[1:])]
    maxv = max(counts) or 1
    bw = (width - 30) / len(counts)
    parts = ["<svg width='%d' height='%d' role='img'>" % (width, height)]
    for i, c in enumerate(counts):
        x = 10 + i * bw
        hh = int((height - 34) * c / maxv) if c else 0
        y = height - 20 - hh
        parts.append("<rect x='%.1f' y='%d' width='%.1f' height='%d' fill='#63b3ed'/>"
                     % (x + 2, y, bw - 4, hh))
        parts.append("<text x='%.1f' y='%d' font-size='10' text-anchor='middle'>%d</text>"
                     % (x + bw / 2, y - 3, c))
        parts.append("<text x='%.1f' y='%d' font-size='10' text-anchor='middle' fill='#666'>%d</text>"
                     % (x + bw / 2, height - 6, edges[i]))
    parts.append("</svg>")
    return "".join(parts)


def _round_svg(per, width=320, height=132) -> str:
    rows = [(x.get("round"), x.get("new") or 0) for x in per]
    if not rows:
        return ""
    maxv = max(n for _, n in rows) or 1
    bw = (width - 30) / max(1, len(rows))
    parts = ["<svg width='%d' height='%d' role='img'>" % (width, height)]
    for i, (rd, n) in enumerate(rows):
        x = 10 + i * bw
        hh = int((height - 34) * n / maxv) if n else 0
        y = height - 20 - hh
        parts.append("<rect x='%.1f' y='%d' width='%.1f' height='%d' fill='#9ae6b4'/>"
                     % (x + 2, y, bw - 4, hh))
        parts.append("<text x='%.1f' y='%d' font-size='10' text-anchor='middle'>%d</text>"
                     % (x + bw / 2, y - 3, n))
        parts.append("<text x='%.1f' y='%d' font-size='10' text-anchor='middle' fill='#666'>r%s</text>"
                     % (x + bw / 2, height - 6, esc(str(rd))))
    parts.append("</svg>")
    return "".join(parts)


MAXDRAW = 120          # 结构图最多画多少个（按台账顺序；纯展示，不全画是大表的体积考虑）


def _mol_svg(smiles, w=150, h=110) -> str:
    """RDKit 画分子结构 SVG（失败返回空串）。调用方负责处理无 RDKit 的情况。"""
    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return ""
    d = rdMolDraw2D.MolDraw2DSVG(w, h)
    rdMolDraw2D.PrepareAndDrawMolecule(d, m)
    d.FinishDrawing()
    s = d.GetDrawingText()
    i = s.find("<svg")
    return s[i:] if i >= 0 else ""


def build_report(csv_path, out_path=None, lang="zh"):
    """把产物台账 CSV 渲染成单文件 HTML 报告。

    csv_path: 台账 CSV（str/Path）；out_path: 输出 HTML（None -> 与台账同目录同名 .report.html）
    返回 (out_path, n_products, n_paths)；台账不存在时返回 (None, 0, 0)。
    纯展示层：不改数据、不排序；筛选只影响浏览器里的显示。
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return None, 0, 0
    out_path = Path(out_path) if out_path else csv_path.with_suffix(".report.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = load_rows(csv_path)
    meta = load_meta(csv_path)
    L = lambda zh, en: en if lang == "en" else zh
    DIR_EN = {"方向明确": "clear", "平衡": "equilibrium", "方向可疑": "suspicious",
              "方向未定": "undetermined", "（无）": "(none)"}
    GATE_EN = {"窗口命中": "window hit", "降权": "downweighted",
               "无数据放行": "no-data pass", "依据未记录": "not recorded"}
    COND_EN = {"煎煮": "Decoction", "室温浸泡": "Room-temperature soak", "水提": "Water extraction",
               "醇提": "Ethanol extraction", "酸水解": "Acid hydrolysis", "碱水解": "Base hydrolysis",
               "酶催化": "Enzymatic", "还原": "Reduction", "氧化": "Oxidation",
               "无氧煎煮": "Anaerobic decoction"}
    TIER_EN = {"药典": "Pharmacopoeia", "古籍": "Classics",
               "AI 现查（未核对）": "AI lookup (unverified)"}
    ORDER_EN = {"marker 优先；其次分子量降序；按结构(SMILES)去重":
                "marker first; then descending MW; deduplicated by structure (SMILES)",
                "库内原序": "library order"}

    def _dir(x):
        return DIR_EN.get(x, x) if lang == "en" else x

    def _gate(x):
        return GATE_EN.get(x, x) if lang == "en" else x

    def _cond(x):
        return COND_EN.get(x, x) if lang == "en" else x

    def _order(x):
        return ORDER_EN.get(x, x) if lang == "en" else x

    def _why(x):
        s = str(x)
        if lang == "en":
            for a, b in (("无 ORD 条件数据，放行", "no ORD condition data; passed"),
                         ("窗口命中", "window hit"), ("降权", "downweighted"),
                         ("依据未记录", "not recorded")):
                s = s.replace(a, b)
        return s

    # ---- 聚合：产物表 ----
    # 逐行条件依据类别（"只看有条件证据"的展示层开关用；不改数据、不排序）
    row_gate = [_classify_gate(r.get("activation_why")) for r in rows]
    HAS_EV = ("窗口命中", "降权")
    prod = OrderedDict()
    for r, gt in zip(rows, row_gate):
        ps = r["product_smiles"]
        p = prod.get(ps)
        if p is None:
            p = {"smiles": ps, "formula": r.get("formula", ""), "mw": r.get("mw", ""),
                 "hac": r.get("heavy_atoms", ""), "n_paths": 0, "ev_any": False,
                 "dirs": Counter(), "rules": Counter(), "herbs": set(),
                 "min_round": 99, "max_support": 0, "co": set(), "cond": set()}
            prod[ps] = p
        p["n_paths"] += 1
        if gt in HAS_EV:
            p["ev_any"] = True
        p["dirs"][_dir(r.get("direction_cn") or "（无）")] += 1
        p["rules"][r.get("rule_name") or "?"] += 1
        if r.get("source_herb"):
            p["herbs"].add(str(r["source_herb"]).replace("tcm.db:", ""))
        try:
            p["min_round"] = min(p["min_round"], int(r.get("round") or 0))
        except Exception:
            pass
        try:
            p["max_support"] = max(p["max_support"], int(r.get("template_support") or 0))
        except Exception:
            pass
        for c in str(r.get("co_products") or "").split("|"):
            c = c.strip()
            if c:
                p["co"].add(c)
        if r.get("cond_model"):
            p["cond"].add(r["cond_model"])

    dir_total = Counter(_dir(r.get("direction_cn") or "（无）") for r in rows)
    gate_total = Counter(_gate(gt) for gt in row_gate)
    n_triples = sum(1 for r in rows if r.get("rule_name") == "mined_triple")
    n_cond = sum(1 for r in rows if r.get("cond_model"))

    # ---- 明细行（保持原顺序；展示层过滤） ----
    detail = []
    for idx, (r, gt) in enumerate(zip(rows, row_gate), 1):
        detail.append({
            "k": idx, "ev": (1 if gt in HAS_EV else 0),
            "product": r.get("product_smiles", ""),
            "formula": r.get("formula", ""),
            "dir": _dir(r.get("direction_cn") or "（无）"),
            "rule": r.get("rule_name", ""), "round": r.get("round", ""),
            "source": r.get("source_name", ""), "herb": r.get("source_herb", ""),
            "act": r.get("activation", ""), "why": _why(r.get("activation_why", "")),
            "cond": r.get("cond_model", ""), "sup": r.get("template_support", ""),
            "co": r.get("co_products", ""),
        })

    runinfo = ""
    if meta:
        st = meta.get("stats", {})
        per = st.get("per_round_new") or []
        runinfo = (L("轮数 %s · 耗时 %s s · 输入 %d 个（%s）",
                     "Rounds %s · elapsed %s s · %d inputs (%s)")
                   % (meta.get("rounds", "?"), st.get("seconds", "?"),
                      len(meta.get("seeds", []) or []),
                      "、".join(str(s.get("name", ""))[:14] for s in
                               (meta.get("seeds", []) or [])[:6])))
        if per:
            runinfo += " · " + "  ".join(L("r%d 新增 %d", "r%d new %d")
                                         % (x.get("round"), x.get("new"))
                                         for x in per)
    condinfo = ""
    cond_details = (meta or {}).get("condition_details") or {}
    if cond_details:
        cond_parts = []
        for key, label_zh, label_en in (
                ("solvent", "溶剂", "solvent"),
                ("catalyst", "催化剂", "catalyst"),
                ("atmosphere", "气氛", "atmosphere"),
                ("temperature", "温度", "temperature"),
                ("time_min", "时长", "time"),
                ("pH", "pH", "pH")):
            item = cond_details.get(key) or {}
            if "value" in item:
                value = item.get("value")
                unit = str(item.get("unit") or "")
                detail_text = ("%g %s" % (float(value), unit)).strip()
                category = ""
                if detail_text:
                    cond_parts.append("%s %s" % (L(label_zh, label_en), detail_text))
                continue
            detail_text = str(item.get("detail") or item.get("category") or "").strip()
            category = str(item.get("category") or "").strip()
            if detail_text:
                if category and category != detail_text:
                    detail_text += " [%s]" % category
                cond_parts.append("%s %s" % (L(label_zh, label_en), detail_text))
        if cond_parts:
            condinfo = L("实际条件：", "Selected conditions: ") + " · ".join(cond_parts)
    fxinfo = ""
    fx = (meta or {}).get("formulas") or {}
    if fx:
        parts = []
        for nm, v in fx.items():
            md = v.get("modifications") or {}
            _tier_lbl = v.get("tier_label") or "?"
            if lang == "en":
                _tier_lbl = TIER_EN.get(_tier_lbl, _tier_lbl)
            s = (L("%s（%s ｜ %s）", "%s (%s | %s)")
                 % (nm, v.get("source_display") or v.get("source") or "?",
                    _tier_lbl))
            rm = md.get("removed") or []
            ad = [str(x.get("herb")) for x in (md.get("added") or []) if isinstance(x, dict)]
            if rm:
                s += L(" 减：", " remove: ") + "、".join(str(x) for x in rm)
            if ad:
                s += L(" 加：", " add: ") + "、".join(ad)
            if v.get("final_herbs"):
                s += L("；本次 %d 味", "; %d herbs this run") % len(v["final_herbs"])
            parts.append(s)
        fxinfo = L("方剂：", "Formulas: ") + "；".join(parts)

    title = csv_path.stem
    h = []
    h.append("<!DOCTYPE html><html lang='%s'><head><meta charset='utf-8'>" % L("zh", "en"))
    h.append("<title>chemreact report · %s</title>" % esc(title))
    h.append("<style>body{font-family:system-ui,'Segoe UI','Microsoft YaHei';margin:18px;"
             "background:#f7f8fa;color:#222}h1{font-size:20px}.cards{display:flex;gap:12px;"
             "flex-wrap:wrap;margin:12px 0}.card{background:#fff;border:1px solid #ddd;"
             "border-radius:8px;padding:10px 14px;min-width:150px}.card b{font-size:20px}"
             "table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}"
             "th,td{border:1px solid #e2e2e2;padding:4px 7px;text-align:left;vertical-align:top}"
             "th{background:#eef1f5;position:sticky;top:0}tr:nth-child(even){background:#fafbfc}"
             "tbody tr{content-visibility:auto;contain-intrinsic-size:auto 128px}"
             ".wrap{max-height:70vh;overflow:auto;border:1px solid #ddd;border-radius:8px}"
             ".bar{margin:10px 0}.bar button{margin-right:6px;padding:4px 10px;border-radius:14px;"
             "border:1px solid #bbb;background:#fff;cursor:pointer}.bar button.on{background:#2b6cb0;"
             "color:#fff;border-color:#2b6cb0}input[type=text]{padding:5px 8px;width:260px}"
             ".note{color:#666;font-size:12px;margin:6px 0 16px}code{font-size:12px;"
             "word-break:break-all}</style></head><body>")
    h.append("<h1>chemreact · %s</h1>" % L("反应产物报告", "Reaction Product Report"))
    h.append("<div class='note'>%s<code>%s</code>%s%s%s<br>%s</div>"
             % (L("台账：", "Ledger: "), esc(str(csv_path)),
                ("<br>" + esc(runinfo)) if runinfo else "",
                ("<br>" + esc(condinfo)) if condinfo else "",
                ("<br>" + esc(fxinfo)) if fxinfo else "",
                L("只打标记、不删产物、不排序（筛选仅用于浏览）",
                  "Flags only; no artifacts deleted; no ranking (filters are display-only).")))

    # ---- 运行记录（成分取舍 / 开关 / 对子截断；全部来自 meta，纯展示、不改数据） ----
    sw = (meta or {}).get("switches") or {}
    sel = (meta or {}).get("selection") or {}
    pc = (meta or {}).get("pair_coverage") or {}
    trunc = bool(((meta or {}).get("stats") or {}).get("truncated"))
    if sel or sw or pc:
        h.append("<div class='note' style='background:#fff;border:1px solid #ddd;"
                 "border-radius:8px;padding:10px 14px;line-height:1.9'>")
        h.append(L("<b>运行记录</b>（本次是怎么取成分、开了哪些开关的；台账数字不受此块影响）<br>",
                   "<b>Run record</b> (compound selection and switches; ledger numbers are unaffected)<br>"))
        for herb, s in sel.items():
            n_av, n_kept = int(s.get("n_available", 0) or 0), int(s.get("n_kept", 0) or 0)
            h.append(L("· 药材 <b>%s</b>：可用成分 <b>%d</b> 个 → 本批取 <b>%d</b> 个"
                       "（未参与 <b>%d</b> 个；排序口径：%s）<br>",
                       "· Herb <b>%s</b>: available compounds <b>%d</b> → selected <b>%d</b>"
                       " (not used: <b>%d</b>; ordering: %s)<br>")
                     % (esc(herb), n_av, n_kept, max(0, n_av - n_kept),
                        esc(_order(s.get("order_rule", "")))))
            kept = "、".join(s.get("kept_names", [])[:80]) or L("（无）", "(none)")
            skip = "、".join(s.get("skipped_names_preview", [])[:60]) or L("（无）", "(none)")
            more = max(0, n_av - n_kept - 60)
            h.append("<details><summary>%s</summary>%s%s<br>%s%s%s</details>"
                     % (L("看名单（本批参与 / 未参与）", "Show names (selected / not selected)"),
                        L("本批参与：", "Selected: "), esc(kept),
                        L("未参与：", "Not selected: "), esc(skip),
                        (esc(L("　…同序还有 %d 个", "  …and %d more in the same order") % more)
                         if more else "")))
        if sw:
            def _v(x, key=None):
                if key == "cond":
                    return _cond(str(x))
                if x is True:
                    return L("开", "on")
                if x is False:
                    return L("关", "off")
                if isinstance(x, (list, tuple)):
                    return "、".join(str(i) for i in x) or L("（无）", "(none)")
                return str(x)
            h.append(L("· 开关：%s<br>", "· Switches: %s<br>")
                     % " · ".join("%s=%s" % (esc(k), esc(_v(v, k))) for k, v in sw.items()))
        if pc:
            if pc.get("pairs_used", 0) < pc.get("pairs_total", 0) or trunc:
                h.append(L("<span style='color:#b45309'>· ⚠ 对子被截断：预算 %s / 共 %s（%s 模式）；"
                           "各成分伙伴数 %s~%s（截断方式可在命令行切换）</span><br>",
                           "<span style='color:#b45309'>· ⚠ Pairs truncated: budget %s / total %s"
                           " (%s mode); partners per compound %s~%s (switchable on the CLI)</span><br>")
                         % (esc(pc.get("pairs_used")), esc(pc.get("pairs_total")),
                            esc(pc.get("mode")), esc(pc.get("min_partners")),
                            esc(pc.get("max_partners"))))
            else:
                h.append(L("· 对子：共 %s 对，预算 %s（未截断，全员可两两反应）<br>",
                           "· Pairs: %s total, budget %s (not truncated; all pairs allowed)<br>")
                         % (esc(pc.get("pairs_total")), esc(pc.get("pairs_used"))))
        h.append("</div>")
    dirs = " · ".join("%s %d" % (k, v) for k, v in dir_total.most_common())
    gates = " · ".join("%s %d" % (k, v) for k, v in gate_total.most_common())
    h.append("<div class='cards'>")
    h.append("<div class='card'>%s<br><b>%d</b> %s</div>"
             % (L("产物分子", "Product molecules"), len(prod), L("个", "")))
    h.append("<div class='card'>%s<br><b>%d</b> %s</div>"
             % (L("出处路径", "Evidence paths"), len(rows), L("条", "")))
    h.append("<div class='card'>%s<br>%s</div>" % (L("方向", "Direction"), esc(dirs)))
    h.append("<div class='card'>%s<br>%s</div>" % (L("条件依据", "Condition evidence"), esc(gates)))
    h.append("<div class='card'>%s<br><b>%d</b> %s</div>"
             % (L("三组分出处", "Three-component evidence"), n_triples, L("条", "")))
    h.append("<div class='card'>%s<br><b>%d</b> %s</div>"
             % (L("条件模型标记", "Condition-model flags"), n_cond, L("条", "")))
    h.append("</div>")

    # ---- 分布图（纯展示层；内联 SVG，离线可看，不改数据、不排序） ----
    h.append("<div class='cards'>")
    h.append("<div class='card'><div style='font-size:12px;color:#666'>%s</div>"
             % L("方向分布（按出处路径）", "Direction distribution (by evidence path)")
             + _bars_svg(dir_total) + "</div>")
    mws = []
    for p in prod.values():
        try:
            mws.append(float(p["mw"]))
        except Exception:
            pass
    if mws:
        h.append("<div class='card'><div style='font-size:12px;color:#666'>%s</div>"
                 % L("产物分子量分布（个/区间，横轴为下限）",
                     "Product MW distribution (count/bin; x-axis = lower bound)")
                 + _hist_svg(mws) + "</div>")
    if meta:
        per = (meta.get("stats") or {}).get("per_round_new") or []
        if per:
            h.append("<div class='card'><div style='font-size:12px;color:#666'>%s</div>"
                     % L("每轮新增产物", "New products per round")
                     + _round_svg(per) + "</div>")
    h.append("</div>")

    # 产物表（结构图：RDKit 可选；超量只画前 MAXDRAW 个，按台账顺序、不排序）
    draw_ok = True
    try:
        _ = _mol_svg("CCO")
    except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
        draw_ok = False
        print("   [warn] 无 RDKit，跳过结构图：%s" % ex)
    h.append("<h2 style='font-size:16px'>%s</h2>" % L("产物（去重）", "Products (deduplicated)"))
    h.append("<div class='wrap'><table id='pt'><thead><tr><th>#</th>"
             + "<th>%s</th><th>%s</th><th>MW</th><th>%s</th><th>%s</th>"
               "<th>%s</th><th>%s</th><th>%s</th><th>SMILES</th><th>%s</th></tr></thead><tbody>"
               % (L("分子式", "Formula"), L("重原子", "Heavy atoms"), L("方向（按路径）", "Direction (by path)"),
                  L("路径数", "Paths"), L("最少轮数", "Min rounds"), L("规则", "Rule"),
                  L("来源药材", "Source herb"), L("来路", "How")))
    for i, p in enumerate(prod.values(), 1):
        h.append("<tr data-dir='%s' data-ev='%d' data-herb='%s' data-smi=\"%s\">"
                 "<td>%d</td>%s<td>%s</td><td>%s</td><td>%s</td>"
                 "<td>%d</td><td>%d</td><td>%s</td><td>%s</td>"
                 "<td><code>%s</code></td>"
                 "<td><button class='pthb' onclick='showPaths(this)'>%s</button></td></tr>"
                 % (esc(",".join(p["dirs"].keys())), (1 if p["ev_any"] else 0),
                    esc("、".join(sorted(p["herbs"]))), esc(p["smiles"]), i,
                    esc(p["formula"]), esc(p["hac"]), esc(p["mw"]),
                    esc(" / ".join("%s×%d" % (k, v) for k, v in p["dirs"].most_common())),
                    p["n_paths"], p["min_round"],
                    esc(" / ".join(k for k, _ in p["rules"].most_common(3))),
                    esc("、".join(sorted(p["herbs"]))), esc(p["smiles"][:90]),
                    L("看路径", "path")))
    h.append("</tbody></table></div>")
    if draw_ok and len(prod) > MAXDRAW:
        h.append("<div class='note'>%s</div>"
                 % L("结构图只画了前 %d 个（按台账顺序；其余以 SMILES 为准，不排序）" % MAXDRAW,
                     "Only the first %d structures are drawn (ledger order; use SMILES for the rest; no ranking)"
                     % MAXDRAW))

    # ---- 反应路径（第八十六轮）：产物是怎么一步步变来的 ----
    # 台账每行只是一跳；多轮时上一轮产物就是下一轮底物，把行拼成图才能看出链。
    # 纯展示：不改台账、不排序、不加任何化学假设。
    if rp is not None and rows:
        # 第八十九轮：逐跳立体结论。
        # 口径：旁观中心 = 底物指定手性中心 − 落在规则作用范围内的那些；
        # 产物（主产物 + co_products 各片段）的指定中心数 ≥ 旁观数 => ok。
        # 只做「本反应不该动的手性中心有没有丢」，不判断 R/S 是否翻转。
        _st_of = {}
        if jst is not None:
            try:
                _byid, _byname = jst.load_rule_smarts()
                _byname = dict(_byname)      # 台账里 rule_name 存的是规则 id，两个键都认
                _byname.update(_byid)
            except Exception as _ex:       # noqa: BLE001
                _byname = {}
                print("   [warn] 读 rules.json 失败（%s）；立体结论降级为 unknown" % _ex)
            for _r in rows:
                try:
                    _st_of[id(_r)] = jst.judge_hop(_r, _byname)[0]
                except Exception:          # noqa: BLE001 —— 单行失败不影响整份报告
                    _st_of[id(_r)] = "unknown"
        path_hops = []
        _ak_low = 0
        for r in rows:
            _st = _st_of.get(id(r), "")
            _ak = rp.atom_conservation(r.get("source_smiles", ""), r.get("product_smiles", ""),
                                       r.get("co_products", ""),
                                       r.get("partner_smiles", ""))
            if _ak is not None and _ak < 0.7:
                _ak_low += 1
            path_hops.append({
                "s": r.get("source_smiles", ""), "p": r.get("product_smiles", ""),
                "r": r.get("rule_name", ""), "d": str(r.get("round", "") or ""),
                "n": r.get("source_name", ""), "f": r.get("formula", ""),
                "w": _why(r.get("activation_why", "")), "a": r.get("activation", ""),
                "b": r.get("extent_band", ""), "e": r.get("extent", ""),
                "dir": _dir(r.get("direction_cn") or ""), "co": r.get("co_products", ""),
                "st": _st,
                "ak": (round(_ak, 3) if _ak is not None else ""),
            })
            # 伴生产物也是产物：双底物规则常把「另一半」（往往是文献关心的脱酯骨架）
            # 放进 co_products。不展开的话，链上会缺掉一半分子（第八十七轮实测）。
            for _frag in str(r.get("co_products", "") or "").split("|"):
                _frag = _frag.strip()
                if not _frag:
                    continue
                _ak_f = _ak   # 行级口径：同一行主产物与伴生产物共用一个守恒率，只计一次
                path_hops.append({
                    "s": r.get("source_smiles", ""), "p": _frag,
                    "r": r.get("rule_name", ""), "d": str(r.get("round", "") or ""),
                    "n": r.get("source_name", ""), "f": "",
                    "w": "", "a": r.get("activation", ""),
                    "b": "", "e": "", "dir": "", "co": r.get("co_products", ""), "zc": 1,
                    "st": "",
                    "ak": (round(_ak_f, 3) if _ak_f is not None else ""),
                })
        labels = {}
        for s in ((meta or {}).get("seeds") or []):
            nm = str(s.get("name") or "").strip()
            smi = str(s.get("smiles") or "").strip()
            if nm and smi and nm != smi and not rp.looks_like_smiles(nm):
                labels[smi] = nm
        for p in prod.values():
            if p["smiles"] not in labels and p["formula"]:
                labels[p["smiles"]] = p["formula"]
        # 种子（输入成分）若既没名字也不是产物：现算分子式，最多 60 个（RDKit 可选）
        _need = [h["s"] for h in path_hops if h["s"] not in labels]
        for _smi in list(dict.fromkeys(_need))[:60]:
            _f = rp.formula_of(_smi)
            if _f:
                labels[_smi] = _f
        _used_rules = {h["r"] for h in path_hops}
        rule_names = {k: v for k, v in (rp.load_rule_names() or {}).items() if k in _used_rules}
        _j = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        opts = "".join(
            "<option value=\"%s\">%s</option>"
            % (esc(p["smiles"]),
               esc("%s · %d 条 · 最少 %d 轮" % (p["formula"] or "?", p["n_paths"], p["min_round"])))
            for p in prod.values())
        h.append("<h2 style='font-size:16px'>%s</h2>"
                 % L("反应路径（这个产物是怎么一步步变来的）",
                     "Reaction paths (how each product came to be)"))
        h.append("<style>"
                 ".pthb{padding:2px 8px;border-radius:5px;border:1px solid #2b6cb0;"
                 "background:#fff;color:#2b6cb0;cursor:pointer;font-size:12px}"
                 ".pthb:hover{background:#ebf4ff}"
                 ".chain{background:#fff;border:1px solid #e2e8f0;border-left:3px solid #2b6cb0;"
                 "border-radius:7px;padding:9px 11px;margin:8px 0;line-height:1.9;font-size:13px}"
                 ".chain .mol{display:inline-block;background:#f1f5f9;border-radius:5px;"
                 "padding:1px 7px;font-weight:600}"
                 ".chain .arw{color:#4a5568;padding:0 4px;font-size:12px}"
                 ".chain .det{color:#718096;font-size:11.5px;margin-top:3px}"
                 "</style>")
        h.append("<div class='card' style='padding:12px'>"
                 "<div style='display:flex;gap:8px;flex-wrap:wrap;align-items:center'>"
                 "<span>%s</span>"
                 "<select id='pathSel' style='flex:1;min-width:280px;padding:7px 9px;"
                 "border:1px solid #cbd5e0;border-radius:6px'>%s</select>"
                 "</div>"
                 "<div class='note' style='font-size:12px;color:#666;margin-top:8px'>%s</div>"
                 "<div id='pathOut' style='margin-top:10px'></div></div>"
                 % (L("选一个产物看它的来路：", "Pick a product to see how it was made:"),
                    opts,
                    L("一条链 = 从上一步的分子到下一步的分子，方括号里是规则 + 轮次 + 条件分（+ 进程档位）。"
                      "多步链表示上一轮的产物又当了下一轮的底物；这只表达「按这些规则，A 能变成 B」，"
                      "不是生化合成路线，也不含任何未落进台账的东西。"
                      "进程档位只是**趋势提示**（按现有文献数据估的深浅），不参与筛选、不会删掉任何产物。",
                      "A chain = one molecule to the next; brackets carry rule + round + condition score "
                      "(+ extent band). Multi-step chains mean a product became the next round's substrate. "
                      "It says only 'by these rules A can become B', not a biosynthetic route. "
                      "The extent band is a trend hint only (estimated depth from the available literature); "
                      "it never filters or removes products.")))
        if jst is not None:
            _stc = {}
            for r in rows:
                _k = _st_of.get(id(r), "")
                if _k:
                    _stc[_k] = _stc.get(_k, 0) + 1
            _lbl = {"ok": "保住", "partial": "部分丢", "lost_all": "整层丢",
                    "no_src_stereo": "底物本来没手性", "unknown": "无法判断",
                    "": "未判"}
            _parts = ["%s %d" % (_lbl.get(k, k), _stc[k])
                      for k in ("ok", "partial", "lost_all", "no_src_stereo", "unknown")
                      if _stc.get(k)]
            h.append("<div class='note' style='font-size:12px;color:#444;margin-top:6px'>"
                     "<b>%s</b> %s<br><span style='color:#718096'>%s</span></div>"
                     % (L("立体检查（逐跳）：", "Stereo check (per hop): "),
                        esc(" · ".join(_parts) or "—"),
                        L("判据 = 本反应不该动的那些手性中心有没有丢；"
                          "「无法判断」多为 mined 模板（台账只记类别名，反查不到作用范围）。"
                          "这里不判 R/S 是否翻转。",
                          "Criterion = whether stereo centres outside this rule's scope were lost; "
                          "'unknown' is mostly mined templates (ledger stores only the category). "
                          "R/S inversion is not judged.")))
            if _ak_low:
                h.append("<div class='note' style='font-size:12px;color:#444;margin-top:6px'>"
                         "<b>%s</b> %d<br><span style='color:#718096'>%s</span></div>"
                         % (L("原子守恒率低于 70% 的行：", "Rows keeping under 70% of heavy atoms: "),
                            _ak_low,
                            L("主产物 + 伴生产物的重原子数加总仍远少于底物。这类行多来自 mined 模板"
                              "（ORD 记录只写主产物，模板里没出现的原子就被删掉），不是引擎的化学判断；"
                              "看到它请回去查模板。",
                              "Product plus co-products together keep far fewer heavy atoms than the "
                              "substrate. These rows are mostly mined templates whose SMARTS omit part of "
                              "the substrate; check the template before trusting the product.")))
        h.append("<script>"
                 "var HOPS=" + _j(path_hops) + ";"
                 "var NM=" + _j(labels) + ";"
                 "var RN=" + _j(rule_names) + ";"
                 "var IDX={};"
                 "HOPS.forEach(function(h){(IDX[h.p]=IDX[h.p]||[]).push(h);});"
                 "function lab(s){return NM[s]||(s.length>26?s.slice(0,26)+'…':s);}"
                 "function pathsFor(t){var out=[],seen={};"
                 "function walk(s,d,stack,vis){if(out.length>=6)return;var inc=IDX[s]||[];"
                 "if(!inc.length){var k=stack.map(function(h){return h.s+'|'+h.r+'|'+h.d;}).join('>');"
                 "if(stack.length&&!seen[k]){seen[k]=1;out.push(stack.slice().reverse());}return;}"
                 "if(d>=10)return;"
                 "for(var i=0;i<inc.length;i++){var h=inc[i];if(vis[h.s])continue;"
                 "stack.push(h);vis[h.p]=1;walk(h.s,d+1,stack,vis);vis[h.p]=0;stack.pop();"
                 "if(out.length>=6)return;}}"
                 "var v={};v[t]=1;walk(t,0,[],v);return out;}"
                 "function bandTxt(b){return b==='major'?'主要':b==='minor'?'次要':b==='none'?'痕量':b;}"
                 "function stTxt(s){return s==='ok'?'立体✓':s==='partial'?'立体部分丢':"
                 "s==='lost_all'?'立体丢':s==='unknown'?'立体判断不了':'';}"
                 "function renderPaths(smi){"
                 "var o=document.getElementById('pathOut');if(!o)return;"
                 "if(!smi){o.innerHTML='';return;}"
                 "var chs=pathsFor(smi);"
                 "if(!chs.length){o.innerHTML='<div class=\"note\">没有台账路径（可能是输入成分本身，或上游被截断）</div>';return;}"
                 "var html='';"
                 "chs.forEach(function(ch,ci){"
                 "var line='<span class=\"mol\">'+esc2(lab(ch[0].s))+'</span>';"
                 "var det='';"
                 "ch.forEach(function(h){"
                 "var bits=[(RN[h.r]||h.r)||'?'];"
                 "if(h.d)bits.push('第 '+h.d+' 轮');"
                 "if(h.a)bits.push('条件 '+h.a);"
                 "if(h.b)bits.push('进程 '+bandTxt(h.b)+(h.e?' ('+h.e+')':''));"
                 "if(h.dir)bits.push(h.dir);"
                 "if(h.zc)bits.push('伴生产物');"
                 "if(h.st)bits.push(stTxt(h.st));"
                 "if(h.ak!==''&&h.ak!==undefined&&h.ak<0.7)bits.push('原子守恒'+Math.round(h.ak*100)+'%');"
                 "line+='<span class=\"arw\">--['+esc2(bits.join(' · '))+']--&gt;</span>';"
                 "line+='<span class=\"mol\">'+esc2(lab(h.p))+'</span>';"
                 "if(h.w)det+='<div class=\"det\">· '+esc2(h.w)+'</div>';"
                 "});"
                 "html+='<div class=\"chain\"><div>'+line+'</div>'+(det||'')+'</div>';});"
                 "o.innerHTML=html;}"
                 "function esc2(t){var d=document.createElement('div');"
                 "d.textContent=(t==null?'':String(t));return d.innerHTML;}"
                 "function showPaths(btn){var tr=btn.closest('tr');"
                 "var smi=tr.getAttribute('data-smi');"
                 "var sel=document.getElementById('pathSel');if(sel)sel.value=smi;"
                 "renderPaths(smi);var o=document.getElementById('pathOut');"
                 "if(o&&o.scrollIntoView)o.scrollIntoView({block:'center',behavior:'smooth'});}"
                 "var _sel=document.getElementById('pathSel');"
                 "if(_sel){_sel.onchange=function(){renderPaths(_sel.value);};}"
                 "</script>")

    h.append("<h2 style='font-size:16px'>%s</h2>"
             % L("结构查看器（输入 SMILES 自行渲染）",
                 "Structure viewer (enter a SMILES)"))
    h.append("<div class='card' style='padding:12px'>"
             "<div style='display:flex;gap:8px;flex-wrap:wrap'>"
             "<input id='svIn' placeholder='CC(=O)Oc1ccccc1C(=O)O' "
             "style='flex:1;min-width:280px;padding:8px 10px;border:1px solid #cbd5e0;border-radius:6px'>"
             "<button onclick='svDraw()' style='padding:8px 18px;border-radius:6px;border:1px solid #2b6cb0;background:#2b6cb0;color:#fff;cursor:pointer'>"
             + L("渲染", "Draw") + "</button></div>"
             "<div id='svOut' style='margin-top:10px;min-height:120px'></div>"
             "<div class='note' style='font-size:12px;color:#666'>"
             + L("结构由本地服务用 RDKit 现场绘制；请通过 http://127.0.0.1:8765/ 打开本页。",
                 "Rendered locally with RDKit; open this page via http://127.0.0.1:8765/.")
             + "</div></div>")
    h.append("<script>"
             "function svDraw(){"
             "var v=document.getElementById('svIn').value.trim();"
             "var o=document.getElementById('svOut');"
             "if(!v){o.textContent='请输入 SMILES';return;}"
             "o.textContent='渲染中…';"
             "fetch('/render?smiles='+encodeURIComponent(v))"
             ".then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.text();})"
             ".then(function(t){o.innerHTML=t;})"
             ".catch(function(e){o.textContent='渲染失败：'+e.message;});}"
             "</script>")
    # 明细表
    h.append("<h2 style='font-size:16px'>%s</h2>"
             % L("出处明细（逐条路径，保持原顺序）", "Evidence details (per path, original order)"))
    h.append("<div class='bar' id='bar'></div>")
    h.append("<label class='note' style='display:inline-block;margin-left:6px'>"
             "<input type='checkbox' id='evt' onchange='apply()'> %s</label>"
             % L("只看有条件证据的（窗口命中/降权；默认关 = 显示全部）",
                 "Only rows with condition evidence (window hit / downweighted; default off = show all)"))
    _herbs = sorted({str(r.get("source_herb") or "").replace("tcm.db:", "")
                     for r in rows if r.get("source_herb")})
    if len(_herbs) > 1:      # 多药材批量：加一个"按药材看"的下拉（纯展示层）
        _opts = "".join("<option>%s</option>" % esc(x) for x in _herbs)
        h.append("<label class='note' style='display:inline-block;margin-left:6px'>%s"
                 "<select id='hsel' onchange='apply()'><option value=''>%s</option>%s"
                 "</select></label>"
                 % (L("药材：", "Herb: "), L("全部", "All"), _opts))
    h.append("<div class='wrap'><table id='dt'><thead><tr><th>#</th><th>%s</th>"
             "<th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th>"
             "<th>support</th><th>%s</th><th>%s</th></tr></thead><tbody>"
             % (L("方向", "Direction"), L("规则", "Rule"), L("轮", "Round"), L("底物", "Substrate"),
                L("药材", "Herb"), L("条件依据", "Condition evidence"), L("副产物", "Co-products"),
                L("产物", "Product")))
    for d in detail:
        h.append("<tr data-dir='%s' data-ev='%d' data-herb='%s'><td>%d</td><td>%s</td><td>%s</td><td>%s</td>"
                 "<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                 "<td><code>%s</code></td></tr>"
                 % (esc(d["dir"]), d["ev"], esc(str(d["herb"]).replace("tcm.db:", "")), d["k"],
                    esc(d["dir"]), esc(d["rule"]), esc(d["round"]),
                    esc(str(d["source"])[:48]), esc(d["herb"]), esc(str(d["why"])[:70]),
                    esc(d["sup"]), esc(str(d["co"])[:48]), esc(str(d["product"])[:90])))
    h.append("</tbody></table></div>")

    # ---- 附录：判据口径（与页面上的标记一一对应；口径出处 = 引擎源码） ----
    if lang == "en":
        h.append("<h2 style='font-size:16px'>Appendix · How to read the flags</h2>")
        h.append("<div class='note' style='background:#fff;border:1px solid #ddd;border-radius:8px;"
                 "padding:10px 14px;line-height:1.9'>"
                 "<b>Direction</b> (per path; no products deleted) — "
                 "<b>clear</b>: chemically supported (including 9 experimentally confirmed hydrolysis cases); "
                 "<b>equilibrium</b>: condensation-hydrolysis equilibrium; also a substrate for the reverse direction, not a final product; "
                 "<b>suspicious</b>: opposite to the current medium (aqueous should hydrolyze, not condense); "
                 "<b>undetermined</b>: not covered by the rule table, or depends on reagents/conditions.<br>"
                 "<b>Condition evidence</b> (strength of “can it happen”) — "
                 "<b>window hit</b>: inside an ORD measured condition window; "
                 "<b>downweighted</b>: temperature/solvent/reagent mismatch (kept, flagged); "
                 "<b>no-data pass</b>: no ORD condition data — no condition evidence for “can happen”; "
                 "<b>not recorded</b>: no condition evidence recorded for this path.<br>"
                 "<b>General</b>: flags only; no products deleted; no ranking; not found ≠ nonexistent "
                 "(only means not enumerated with the current templates/depth). Filters only affect display.<br>"
                 "Generated by <code>tools/make_report.py</code> from the ledger CSV (display layer only); "
                 "numbers match the ledger.</div>")
    else:
        h.append("<h2 style='font-size:16px'>附录 · 判据口径（怎么读上面的标记）</h2>")
        h.append("<div class='note' style='background:#fff;border:1px solid #ddd;border-radius:8px;"
                 "padding:10px 14px;line-height:1.9'>"
                 "<b>方向</b>（逐条路径标注，不删产物）——"
                 "<b>方向明确</b>：该方向在化学上成立（含水解侧已被实测确认的 9 类）；"
                 "<b>平衡</b>：缩合-水解平衡——它同时是另一个方向的底物，别当终产物；"
                 "<b>方向可疑</b>：与当前介质相反（水相里应往水解走，而非往缩合走）；"
                 "<b>方向未定</b>：判据表覆盖不到（自抽模板），或方向本身取决于试剂/条件。<br>"
                 "<b>条件依据</b>（「能不能发生」的证据强弱）——"
                 "<b>窗口命中</b>：落在 ORD 实测条件窗口内；"
                 "<b>降权</b>：温度/溶剂/辅助试剂与实测记录不符（保留、只标注）；"
                 "<b>无数据放行</b>：没有 ORD 条件数据——「能发生」没有任何条件证据支撑；"
                 "<b>依据未记录</b>：该路径未记录条件依据。<br>"
                 "<b>总则</b>：只打标记、不删产物、不排序；查不到 ≠ 不存在（只说明「当前模板库 + "
                 "当前轮数没枚举出来」）。页内筛选/分组只影响浏览显示。<br>"
                 "本报告由 <code>tools/make_report.py</code> 从台账 CSV 渲染（纯展示层），"
                 "数字与台账一一对应。</div>")

    dirs_js = json.dumps([k for k, _ in dir_total.most_common()], ensure_ascii=False)
    _all = L("全部", "All")
    _ph = L("关键词过滤（分子式/规则/药材…）", "Filter (formula/rule/herb…)")
    h.append("<script>const DIRS=%s,ALL=%s;let cur=ALL;"
             "const bar=document.getElementById('bar');"
             "function apply(){for(const tb of ['pt','dt']){"
             "document.querySelectorAll('#'+tb+' tbody tr').forEach(tr=>{"
             "const okd=(cur===ALL||tr.dataset.dir.includes(cur));"
             "const okq=!kw||tr.textContent.includes(kw);"
             "const evt=document.getElementById('evt');"
             "const oke=!(evt&&evt.checked)||tr.dataset.ev==='1';"
             "const hv=document.getElementById('hsel');"
             "const okh=!(hv&&hv.value)||(tr.dataset.herb||'').includes(hv.value);"
             "tr.style.display=(okd&&okq&&oke&&okh)?'':'none';});}}"
             "let kw='';"
             "function mk(items){bar.innerHTML='';"
             "for(const d of items){const b=document.createElement('button');"
             "b.textContent=d;b.className=(d===cur?'on':'');"
             "b.onclick=()=>{cur=d;mk(items);apply();};bar.appendChild(b);}"
             "const inp=document.createElement('input');inp.type='text';"
             "inp.placeholder=%s;"
             "inp.oninput=()=>{kw=inp.value;apply();};bar.appendChild(inp);}"
             "mk([ALL,...DIRS]);</script></body></html>"
             % (dirs_js, json.dumps(_all, ensure_ascii=False),
                json.dumps(_ph, ensure_ascii=False)))

    out_path.write_text("\n".join(h), encoding="utf-8")
    print(L("报告已生成：%s（%d 产物 / %d 路径 / %.0f KB）",
            "Report written: %s (%d products / %d paths / %.0f KB)")
          % (out_path, len(prod), len(rows), out_path.stat().st_size / 1024))
    return out_path, len(prod), len(rows)


def build_routes_report(out_dir, target_smiles, routes, eng, stat, *,
                        mode="", blacklist_note="", n_templates=0,
                        show_limit=None, pool_desc=None, txt_name="", lang="zh"):
    """逆合成路线的单文件 HTML（与产物报告同风格）。返回输出路径。

    routes/eng 来自 retro_search.RetroSearch.search（只读消费，不改任何数据）。
    显示上限与命令行 --show 一致（默认全部可用条目都会写 txt，报告只画前 show_limit 条）。
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / ("%s_routes.report.html" % ts)
    n_total = len(routes)
    n_usable = sum(1 for rt in routes if getattr(rt, "usable", True))
    L = lambda zh, en: en if lang == "en" else zh
    h = []
    h.append("<!DOCTYPE html><html lang='%s'><head><meta charset='utf-8'>" % L("zh", "en"))
    h.append("<title>chemreact route report · %s</title>" % esc(target_smiles[:40]))
    h.append("<style>body{font-family:system-ui,'Segoe UI','Microsoft YaHei';margin:18px;"
             "background:#f7f8fa;color:#222;max-width:1100px}h1{font-size:20px}"
             ".note{color:#666;font-size:12px;margin:6px 0 14px}"
             ".cards{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0}"
             ".card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:8px 14px}"
             ".card b{font-size:18px}table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}"
             "th,td{border:1px solid #e2e2e2;padding:4px 7px;text-align:left;vertical-align:top}"
             "th{background:#eef1f5}code{font-size:12px;word-break:break-all}"
             ".route{background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px 14px;margin:12px 0}"
             ".ok{color:#1a7f37;font-weight:600}.bad{color:#b45309;font-weight:600}"
             ".chip{display:inline-block;border-radius:12px;padding:1px 8px;margin:2px;font-size:12px;"
             "border:1px solid #bbb;background:#f7f7f7}.chip.in{border-color:#8ec08e;background:#ecf7ec}"
             ".chip.out{border-color:#e0b4b4;background:#fbf1f1}</style></head><body>")
    h.append("<h1>chemreact · %s</h1>" % L("逆合成路线报告", "Retrosynthetic Route Report"))
    h.append("<div class='note'>%s<code>%s</code>%s%s</div>"
             % (L("目标：", "Target: "), esc(target_smiles),
                ("<br>" + L("对应文本：", "Text: ") + esc(txt_name)) if txt_name else "",
                ("<br>" + L("池子：", "Pool: ") + esc(pool_desc)) if pool_desc else ""))
    try:
        svg = _mol_svg(target_smiles, 220, 160)
        if svg:
            h.append("<div class='route' style='max-width:260px'>%s</div>" % svg)
    except Exception:
        pass
    secs = (stat or {}).get("耗时秒") or (stat or {}).get("seconds") or "?"
    h.append("<div class='cards'>")
    _bl = blacklist_note or "关（默认）"
    if lang == "en":
        _bl = ("off (default)" if ("关" in _bl or _bl.startswith("off"))
               else ("on" if ("开" in _bl or _bl.startswith("on")) else _bl))
    _mode = mode or "?"
    if lang == "en":
        _mode = ("Restricted pool" if _mode.startswith("受限池")
                 else ("Full terminal set (COCONUT + tcm.db + purchasable blocks)"
                       if _mode.startswith("全量终止集合") else _mode))
    h.append("<div class='card'>%s<br><b>%d</b></div>" % (L("路线", "Routes"), n_total))
    h.append("<div class='card'>%s<br><b>%d</b></div>" % (L("判为可用", "Marked usable"), n_usable))
    h.append("<div class='card'>%s<br><b>%s</b> s</div>" % (L("搜索耗时", "Search time"), esc(secs)))
    h.append("<div class='card'>%s<br><b>%s</b></div>" % (L("模板", "Templates"), esc(n_templates)))
    h.append("<div class='card'>%s<br>%s</div>" % (L("黑名单", "Blacklist"), esc(_bl)))
    h.append("<div class='card'>%s<br>%s</div>" % (L("终止口径", "Terminal set"), esc(_mode)))
    h.append("</div>")
    lim = show_limit if show_limit else len(routes)
    for i, rt in enumerate(routes[:lim], 1):
        usable = getattr(rt, "usable", True)
        badge = ("<span class='ok'>%s</span>" % L("可用", "usable") if usable else
                 "<span class='bad'>%s（%s）</span>"
                 % (L("不可用", "unusable"), esc(getattr(rt, "unusable_reason", ""))))
        _head = L("路线 %d（%d 步）· %s", "Route %d (%d steps) · %s") % (
            i, len(getattr(rt, "steps", [])), badge)
        h.append("<div class='route'><h2 style='font-size:15px;margin:0 0 6px'>%s</h2>"
                 % _head)
        h.append("<table><thead><tr><th>#</th><th>%s</th><th>%s</th><th>%s</th></tr></thead><tbody>"
                 % (L("反应", "Reaction"), L("目标", "Target"), L("前体", "Precursors")))
        for j, st in enumerate(getattr(rt, "steps", []), 1):
            chips = []
            for p in getattr(st, "precursors", []):
                try:
                    inn = bool(eng.is_available(p))
                except Exception:
                    inn = False
                chips.append("<span class='chip %s'>%s</span>"
                             % ("in" if inn else "out", esc(p[:64])))
            h.append("<tr><td>%d</td><td>%s</td><td><code>%s</code></td><td>%s</td></tr>"
                     % (j, esc(getattr(st, "reaction_name", "")), esc(str(getattr(st, "target", ""))[:64]),
                        "".join(chips)))
        h.append("</tbody></table>")
        terms = getattr(rt, "terminals", None)
        if terms:
            h.append("<div class='note'>%s%s</div>"
                     % (L("终点说明：", "Terminals: "),
                        esc(" | ".join(str(t)[:56] for t in terms))))
        h.append("</div>")
    h.append("<div class='note'>%s</div>"
             % L("不排序、不打分；「可用」是启发式判据（残基/放大/惰性/荒谬四类），"
                 "会标原因供人工判断。查不到 ≠ 存在路线。前体的「在池内」= 落在当前终止集合/受限池。",
                 "No ranking or scoring; “usable” is a heuristic flag (residue/upsizing/inert/absurd), "
                 "with the reason shown for human review. Not found ≠ a route exists. "
                 "“in pool” means the precursor is in the current terminal set/restricted pool."))
    h.append("</body></html>")
    out_path.write_text("\n".join(h), encoding="utf-8")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description="产物台账 -> 一页式 HTML 报告")
    ap.add_argument("csv", help="台账 CSV 路径")
    ap.add_argument("--out", default=None, help="输出 HTML（默认与台账同目录）")
    a = ap.parse_args()
    res = build_report(Path(a.csv), Path(a.out) if a.out else None)
    if res[0] is None:
        print("台账不存在：%s" % a.csv)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

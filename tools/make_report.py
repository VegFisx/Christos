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
             ".wrap{max-height:70vh;overflow:auto;border:1px solid #ddd;border-radius:8px}"
             ".bar{margin:10px 0}.bar button{margin-right:6px;padding:4px 10px;border-radius:14px;"
             "border:1px solid #bbb;background:#fff;cursor:pointer}.bar button.on{background:#2b6cb0;"
             "color:#fff;border-color:#2b6cb0}input[type=text]{padding:5px 8px;width:260px}"
             ".note{color:#666;font-size:12px;margin:6px 0 16px}code{font-size:12px;"
             "word-break:break-all}</style></head><body>")
    h.append("<h1>chemreact · %s</h1>" % L("反应产物报告", "Reaction Product Report"))
    h.append("<div class='note'>%s<code>%s</code>%s%s<br>%s</div>"
             % (L("台账：", "Ledger: "), esc(str(csv_path)),
                ("<br>" + esc(runinfo)) if runinfo else "",
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
             + (("<th>%s</th>" % L("结构", "Structure")) if draw_ok else "")
             + "<th>%s</th><th>%s</th><th>MW</th><th>%s</th><th>%s</th>"
               "<th>%s</th><th>%s</th><th>%s</th><th>SMILES</th></tr></thead><tbody>"
               % (L("分子式", "Formula"), L("重原子", "Heavy atoms"), L("方向（按路径）", "Direction (by path)"),
                  L("路径数", "Paths"), L("最少轮数", "Min rounds"), L("规则", "Rule"),
                  L("来源药材", "Source herb")))
    for i, p in enumerate(prod.values(), 1):
        svg_cell = ""
        if draw_ok:
            if i <= MAXDRAW:
                svg_cell = _mol_svg(p["smiles"]) or L("（画失败）", "(draw failed)")
            else:
                svg_cell = L("（略）", "(omitted)")
        h.append("<tr data-dir='%s' data-ev='%d' data-herb='%s'><td>%d</td>%s<td>%s</td><td>%s</td><td>%s</td>"
                 "<td>%s</td><td>%d</td><td>%d</td><td>%s</td><td>%s</td>"
                 "<td><code>%s</code></td></tr>"
                 % (esc(",".join(p["dirs"].keys())), (1 if p["ev_any"] else 0),
                    esc("、".join(sorted(p["herbs"]))), i,
                    ("<td>%s</td>" % svg_cell) if draw_ok else "",
                    esc(p["formula"]), esc(p["hac"]), esc(p["mw"]),
                    esc(" / ".join("%s×%d" % (k, v) for k, v in p["dirs"].most_common())),
                    p["n_paths"], p["min_round"],
                    esc(" / ".join(k for k, _ in p["rules"].most_common(3))),
                    esc("、".join(sorted(p["herbs"]))), esc(p["smiles"][:90])))
    h.append("</tbody></table></div>")
    if draw_ok and len(prod) > MAXDRAW:
        h.append("<div class='note'>%s</div>"
                 % L("结构图只画了前 %d 个（按台账顺序；其余以 SMILES 为准，不排序）" % MAXDRAW,
                     "Only the first %d structures are drawn (ledger order; use SMILES for the rest; no ranking)"
                     % MAXDRAW))

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

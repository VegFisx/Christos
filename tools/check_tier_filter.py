# -*- coding: utf-8 -*-
r"""判定性检查：网页里那颗「按出处筛看」的下拉**真的会筛**吗？

为什么要写它：光看控件在不在，判不出"点了没用"（这类静默失效在本项目踩过多次，
例如 `route` 变量停在 `"auto"`）。所以这里把 ``ui_page.html`` 里的
``renderResult`` 原样抠出来，在 node 里喂一份**固定的 meta**，然后真的改下拉的值、
真的看每一行是显示还是隐藏。

判据（三条全过才算 PASS）：
  1. 默认（'all'）时**每一行都显示** —— 不隐藏；
  2. 选 '5' 时**只有 tier=5 的行显示** —— 能单独筛出 AI现查；
  3. 选 '1' 时只有 tier=1 的行显示（换一档同样成立）—— 不是硬编码某一档。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
HTML = STAGE / "integration" / "tcmai_bridge" / "ui_page.html"


def extract_html_js() -> str:
    """抠出 q() / esc4() / renderResult() 三个函数（按行锚点，别硬编码行号）。"""
    lines = HTML.read_text(encoding="utf-8").splitlines()
    out = {}
    for name, pat in (("q", r"^function q\(id\)\{"),
                      ("esc4", r"^function esc4\(x\)\{"),
                      ("fmtSec", r"^function fmtSec\(s\)\{"),
                      ("renderResult", r"^function renderResult\(j\)\{")):
        start = next(i for i, ln in enumerate(lines) if re.match(pat, ln))
        # 逐行累计大括号，找到闭合那一行
        depth = 0
        for i in range(start, len(lines)):
            depth += lines[i].count("{") - lines[i].count("}")
            if depth == 0 and i > start:
                out[name] = "\n".join(lines[start:i + 1])
                break
        else:
            raise SystemExit("抠不出函数 %s（文件结构变了？）" % name)
    return "\n".join(out[k] for k in ("q", "esc4", "fmtSec", "renderResult"))


HARNESS = r"""
// ---- 假的 DOM：只实现 renderResult 会用到的那几样 ----
const cache = {};
function mkEl(){
  return {style:{}, innerHTML:"", textContent:"", href:"", value:"all", onchange:null};
}
global.document = {
  getElementById: id => (cache[id] = cache[id] || mkEl()),
  querySelectorAll: () => rows
};
const metaEl = document.getElementById("meta");
const selEl = document.getElementById("tierfilter");
let metaHTML = "";
Object.defineProperty(metaEl, "innerHTML", {
  get(){return metaHTML;}, set(v){metaHTML = v;}
});
function mkRows(){                       // 把刚渲染出来的表行变成假节点
  const rows = [];
  const re = /<tr data-tier="([^"]+)"/g; let m;
  const re2 = /<tr data-tier="([^"]+)" data-probe="([^"]*)"/g;
  while((m = re2.exec(metaHTML)) !== null){
    rows.push({tier:m[1], probe:m[2], style:{},
               getAttribute(k){
                 return k==="data-tier"?this.tier:(k==="data-probe"?this.probe:null);
               }});
  }
  return rows;
}
let rows = [];
let rid = null;                 // 页面里的模块级变量，renderResult 会读
let lastFormula = null;         // 方剂页运行提示；本测试不启用
__FUNCS__

const meta = __META__;
renderResult({meta: meta, seconds: 1, report:null, csv:null, tsv:null});
rows = mkRows();

function shown(){ return rows.filter(r => r.style.display !== "none").map(r => r.tier); }
function check(cond, msg){ console.log((cond ? "  PASS  " : "  FAIL  ") + msg); return cond ? 0 : 1; }

let bad = 0;
console.log("  表格渲染出 " + rows.length + " 行，tier 依次为 [" + rows.map(r=>r.tier).join(",") + "]");
bad += check(selEl.onchange !== null, "下拉挂上了 onchange（控件真的接线了）");
bad += check(rows.length > 0, "默认渲染出全部版本行");
bad += check(shown().length === rows.length, "默认（全部出处）：每一行都显示 —— 不隐藏");
selEl.value = "5"; selEl.onchange();
const s5 = shown();
bad += check(s5.length > 0 && s5.every(t => t === "5"), "选『AI 现查（未核对）』：只剩 tier=5 的行（" + s5.join(",") + "）");
selEl.value = "1"; selEl.onchange();
const s1 = shown();
bad += check(s1.length > 0 && s1.every(t => t === "1"), "选『ETCM』：只剩 tier=1 的行（" + s1.join(",") + "）");
selEl.value = "all"; selEl.onchange();
bad += check(shown().length === rows.length, "切回『全部出处』：又都显示（可逆）");
selEl.value = "p:查无"; selEl.onchange();
const sw = rows.filter(r => r.style.display !== "none").map(r => r.probe);
bad += check(sw.length > 0 && sw.every(p => p === "查无"),
             "选『抽检=查无』：只剩抽检结论为查无的行（" + sw.join(",") + "）");
selEl.value = "all"; selEl.onchange();
process.exit(bad ? 1 : 0);
"""


def main() -> int:
    funcs = extract_html_js()
    meta = {"formulas": {"四君子汤": {
        "source": "ETCM", "n_herbs": 4, "n_versions": 3, "tier": 1, "tier_label": "ETCM",
        "probe": {"verdict": "部分命中", "url": "https://example.invalid/a", "cov": 0.5},
        "versions": [
            {"source": "ETCM", "tier": 1, "tier_label": "ETCM", "n_herbs": 4,
             "probe": {"verdict": "部分命中", "url": "https://example.invalid/a", "cov": 0.5}},
            {"source": "《回春》卷二。", "tier": 5, "tier_label": "AI 现查（未核对）", "n_herbs": 12,
             "probe": {"verdict": "查无", "url": "https://example.invalid/b", "cov": 0.0}},
            {"source": "《中国药典》一部。", "tier": 5, "tier_label": "AI 现查（未核对）", "n_herbs": 6},
        ]}}}
    js = HARNESS.replace("__FUNCS__", funcs).replace(
        "__META__", json.dumps(meta, ensure_ascii=False))
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "tier_filter_test.js"
        p.write_text(js, encoding="utf-8")
        r = subprocess.run(["node", str(p)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    print("=" * 96)
    print("判定：网页「按出处筛看」下拉是否真的生效（node 跑 renderResult 本体）")
    print("=" * 96)
    print((r.stdout or "").rstrip())
    if r.returncode != 0:
        print((r.stderr or "")[-800:])
        print("★ 有 FAIL —— 筛选没真正生效")
        return 1
    print("  全部 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
r"""论文配套：把 ~190 条切断做成一个**盲标**专家标注页（单文件 HTML，离线可用）。

口径：页面只显示「目标 + 前体」结构式，不显示系统判定（先盲标探真实水平）；
标注三选一（合理 / 不合理 / 不确定）+ 备注；导出 CSV 后与本文件里的系统判定对照。
输入：reports/paper/results/annotation_candidates.jsonl
输出：reports/paper/annotation/annotation.html
用法: python tools/paper_build_annotation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                        # noqa: E402
from rdkit.Chem.Draw import rdMolDraw2D                 # noqa: E402

RDLogger.DisableLog("rdApp.*")

SRC = STAGE / "reports" / "paper" / "results" / "annotation_candidates.jsonl"
OUT = STAGE / "reports" / "paper" / "annotation" / "annotation.html"


def svg_of(smi: str, w=300, h=210) -> str:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return "<div class='err'>解析失败</div>"
    d = rdMolDraw2D.MolDraw2DSVG(w, h)
    d.DrawMolecule(m)
    d.FinishDrawing()
    s = d.GetDrawingText()
    s = s.replace("<?xml version='1.0' encoding='iso-8859-1'?>", "")
    return s


def main() -> int:
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8") if l.strip()]
    print("标注候选 %d 条" % len(rows))
    # ★ 第七十五轮：给每条切断配**文献条件样例**（用户：没有条件说什么也白费）
    cond_path = STAGE / "data" / "annotation_conditions.json"
    cond_by_i = {}
    if cond_path.exists():
        cond_by_i = json.loads(cond_path.read_text(encoding="utf-8"))
    items = []
    for k, r in enumerate(rows):
        c = cond_by_i.get(str(r.get("i"))) or {}
        ex = c.get("examples") or []
        parts = []
        for e in ex[:2]:
            bits = []
            if e.get("catalysts"):
                bits.append("催化剂 " + "、".join(e["catalysts"][:2]))
            if e.get("reagents"):
                bits.append("试剂 " + "、".join(e["reagents"][:3]))
            if e.get("solvents"):
                bits.append("溶剂 " + "、".join(e["solvents"][:2]))
            if e.get("temp"):
                bits.append(e["temp"])
            if bits:
                parts.append("；".join(bits))
        cond_txt = " ｜ ".join(parts)
        items.append({
            "k": k, "i": r.get("i"), "class": r.get("class"),
            "target_smi": r["target"], "precursor_smis": r["precursors"],
            "svgs": [svg_of(r["target"])] + [svg_of(p) for p in r["precursors"]],
            "freq": c.get("template_freq"),
            "cond": cond_txt,
        })
    data_js = json.dumps(items, ensure_ascii=False)
    html = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>切断可用性盲标</title>
<style>
 body{font-family:system-ui,Segoe UI,Microsoft YaHei;margin:20px;background:#fafafa}
 .card{background:#fff;border:1px solid #ddd;border-radius:8px;margin:14px 0;padding:12px}
 .row{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
 .arrow{font-size:30px;color:#666}
 svg{max-width:300px;height:auto}
 .q{margin-top:8px}
 label{margin-right:14px}
 textarea{width:420px;height:40px}
 .bar{position:sticky;top:0;background:#fff;border-bottom:2px solid #333;padding:10px;z-index:9}
 .err{color:#c00}
</style></head><body>
<div class="bar"><b>切断可用性盲标（三轴）</b>　★ <b>结构可行 ≠ 条件可行</b>：理论上有机会的有机反应很多，
但"能不能在现实里做"取决于<b>条件</b>与<b>试剂</b>。请分别判三件事：
① 结构上说得通吗（合理/不合理/不确定）　② 所需条件是否常规（常规/极端/不确定）
③ 所需试剂是否常见可得（常见/稀有或昂贵/不确定）。条件样例来自 ORD 原始记录，仅供参考。
&nbsp;<button onclick="exportCSV()">导出 CSV</button>
&nbsp;<span id="cnt"></span></div>
<div id="app"></div>
<script>
const DATA = __DATA__;
const answers = {};
const app = document.getElementById('app');
for (const it of DATA) {
  const div = document.createElement('div'); div.className='card';
  let h = '<div class="row"><div><div style="font-size:12px;color:#888">目标 #'+it.k+' (idx '+it.i+', class '+it.class+')</div>'+it.svgs[0]+'</div>';
  for (let j=1;j<it.svgs.length;j++) h += '<div class="arrow">←</div><div><div style="font-size:12px;color:#888">前体 '+j+'</div>'+it.svgs[j]+'</div>';
  h += '</div>';
  if (it.cond) h += '<div class="q" style="background:#f2f6ff;border:1px solid #cdd9f5;border-radius:6px;padding:6px 8px"><b>文献条件样例</b>（模板频次 '+(it.freq==null?'?':it.freq)+'）：'+it.cond+'</div>';
  else h += '<div class="q" style="color:#888">文献条件样例：<b>无</b>（该模板无 ORD 溯源反应）</div>';
  h += '<div class="q"><b>① 结构</b>：'+
       '<label><input type="radio" name="v'+it.k+'" value="合理"> 合理</label>'+
       '<label><input type="radio" name="v'+it.k+'" value="不合理"> 不合理</label>'+
       '<label><input type="radio" name="v'+it.k+'" value="不确定"> 不确定</label></div>';
  h += '<div class="q"><b>② 条件</b>：'+
       '<label><input type="radio" name="x'+it.k+'" value="常规"> 常规</label>'+
       '<label><input type="radio" name="x'+it.k+'" value="极端"> 极端（高温/高压/无水无氧等）</label>'+
       '<label><input type="radio" name="x'+it.k+'" value="不确定"> 不确定</label></div>';
  h += '<div class="q"><b>③ 试剂</b>：'+
       '<label><input type="radio" name="y'+it.k+'" value="常见"> 常见可得</label>'+
       '<label><input type="radio" name="y'+it.k+'" value="稀有或昂贵"> 稀有或昂贵</label>'+
       '<label><input type="radio" name="y'+it.k+'" value="不确定"> 不确定</label></div>';
  h += '<div class="q">备注 <textarea id="c'+it.k+'"></textarea></div>';
  div.innerHTML = h; app.appendChild(div);
}
function bind(){for (const it of DATA){
  const rec = answers[it.k] = answers[it.k] || {};
  for (const [pre,name] of [['v','struct'],['x','cond'],['y','reag']]){
    document.getElementsByName(pre+it.k).forEach(r=>r.addEventListener('change',()=>{rec[name]=r.value;upd();}));
  }
}}
bind();
function upd(){let n=0;for(const k in answers){const a=answers[k];if(a.struct&&a.cond&&a.reag)n++;}document.getElementById('cnt').textContent=n+'/'+DATA.length+' 三条全标';}
upd();
function exportCSV(){
  let csv='k,idx,class,target,precursors,结构,条件,试剂,备注,文献条件样例\\n';
  for (const it of DATA){
    const a=answers[it.k]||{}; const c=(document.getElementById('c'+it.k)||{}).value||'';
    const pre=it.precursor_smis.join('|');
    csv += [it.k,it.i,it.class,'"'+it.target_smi+'"','"'+pre+'"',
            a.struct||'',a.cond||'',a.reag||'','"'+(c.replace(/"/g,'""'))+'"',
            '"'+((it.cond||'').replace(/"/g,'""'))+'"'].join(',')+'\\n';
  }
  const blob=new Blob([csv],{type:'text/csv'}); const a=document.createElement('a');
  a.href=URL.createObjectURL(blob); a.download='annotation_labels.csv'; a.click();
}
</script></body></html>"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html.replace("__DATA__", data_js), encoding="utf-8")
    print("写出：%s（%.1f MB）" % (OUT, OUT.stat().st_size / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())

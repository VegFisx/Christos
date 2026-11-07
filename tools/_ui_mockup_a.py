# -*- coding: utf-8 -*-
r"""一次性脚本：生成"方案 A 三步页"界面小样（静态 HTML，数字全来自真实台账）。

读 2026-10-15 甘草实跑台账（12 成分 → 552 出处；只读 D:\TCMAI\chemreact\out\）-> 写
reports\界面小样-三步页.html

* 产物行保持台账原顺序（不排序）；表格只放前 10 行做示意
* 数字（产物数 / 方向分布 / 耗时）从台账与 meta 现算，不手写
"""
from __future__ import annotations

import csv
import html
import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_report import _classify_gate          # noqa: E402  口径复用，不重写

CSV = Path(r"D:\TCMAI\chemreact\out\20261015-153500_甘草.csv")
META = Path(r"D:\TCMAI\chemreact\out\20261015-153500_甘草.meta.json")
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\界面小样-三步页.html")


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def short(x, n: int) -> str:
    s = str(x or "")
    return s[:n] + ("…" if len(s) > n else "")


def main() -> int:
    with open(CSV, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("product_smiles")]
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    secs = (meta.get("stats") or {}).get("seconds", "?")
    n_prod = len({r["product_smiles"] for r in rows})
    dirs = Counter(r.get("direction_cn") or "（无）" for r in rows)
    gates = Counter(_classify_gate(r.get("activation_why")) for r in rows)

    h = []
    h.append("<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'>")
    h.append("<title>chemreact 界面小样 · 三步页（静态演示）</title>")
    h.append("<style>body{font-family:system-ui,'Segoe UI','Microsoft YaHei';margin:18px;"
             "background:#f7f8fa;color:#222;max-width:1100px}h1{font-size:20px}"
             ".banner{background:#fff8e1;border:1px solid #e6c96b;border-radius:8px;"
             "padding:10px 14px;font-size:13px;margin:10px 0 16px}"
             ".step{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;"
             "margin:10px 0}.step h2{font-size:15px;margin:0 0 8px}"
             ".chip{display:inline-block;background:#e8f0fe;border:1px solid #b7cdf5;"
             "border-radius:14px;padding:3px 10px;margin:3px}.chip b{color:#1a4f9c}"
             "select,input{padding:5px 8px;font:inherit;border:1px solid #bbb;border-radius:6px}"
             "button{padding:6px 14px;font:inherit;border-radius:8px;border:1px solid #bbb;"
             "background:#fff;cursor:pointer}#go{background:#2b6cb0;color:#fff;border-color:#2b6cb0;"
             "font-size:15px;padding:8px 26px}button[disabled]{opacity:.55;cursor:not-allowed}"
             ".cards{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0}"
             ".card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:8px 14px}"
             "table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}"
             "th,td{border:1px solid #e2e2e2;padding:4px 7px;text-align:left;vertical-align:top}"
             "th{background:#eef1f5}code{font-size:12px;word-break:break-all}"
             ".note{color:#666;font-size:12px;margin:6px 0}details{margin-top:8px}"
             ".prog{display:none;color:#2b6cb0;margin:10px 0;font-size:13px}"
             "#results{display:none}#results .step{border-color:#8ec08e}"
             "h2 .badge{font-size:12px;color:#666;font-weight:400}</style></head><body>")
    h.append("<h1>chemreact · 药材反应预测（界面小样）</h1>")
    h.append("<div class='banner'>⚠ 这是<b>界面小样</b>（方案 A「三步页」）：布局与交互是示意，"
             "点「开始预测」不会真的运行引擎。页面里的分子与数字来自 <b>2026-10-15 甘草实跑的真实台账"
             "（12 个成分全参与 → 552 个出处）</b>。"
             "看完请圈选/提意见，我再把它做成可用的真页面。</div>")

    # 第 1 步
    h.append("<div class='step' id='s1'><h2>第 1 步 · 选药材</h2>")
    h.append("<span class='chip'>甘草 <b>×</b></span>  <span class='chip'>黄芪 <b>×</b></span>  "
             "<input placeholder='继续输入中药名，回车添加' size='22'> "
             "每味取几个成分：<select><option>6</option><option selected>12</option>"
             "<option>24</option><option>全部（较慢）</option></select>")
    h.append("<div class='note'>成分一律从 tcm.db 只读取出（不手填分子）。"
             "取了多少 / 共多少 / 谁没参与，报告里会逐条写明（运行留证）。</div></div>")

    # 第 2 步
    h.append("<div class='step' id='s2'><h2>第 2 步 · 条件与轮数</h2>")
    h.append("条件档案：<select><option selected>煎煮</option><option>室温水</option>"
             "<option>乙醇回流</option><option>自定义…</option></select> 　"
             "轮数：<select><option selected>1</option><option>2</option><option>3</option></select>"
             " <span class='note'>（轮数由你掌握：轮数越多产物越多、也越慢）</span>")
    h.append("<details><summary>更多选项（高级，默认都是保守设置）</summary>"
             "辅助试剂：<input placeholder='如 NaBH4（逗号分隔，可留空）' size='28'>　"
             "<label><input type='checkbox'> 三组分模板（默认关，慢 ~40×）</label>　"
             "<label><input type='checkbox'> 逆模板黑名单（默认关，83 条 never-usable）</label>　"
             "最大对数：<input value='4000' size='6'></details></div>")

    # 第 3 步
    h.append("<div class='step' id='s3'><h2>第 3 步 · 开始预测</h2>")
    h.append("<button id='go' onclick='startRun()'>开始预测</button>")
    h.append("<div class='prog' id='prog'></div></div>")

    # 结果（点击后出现；数字全真实）
    h.append("<div id='results'><div class='step'>")
    h.append("<h2>结果 · 一页报告 <span class='badge'>（小样里只展示前 10 条出处，保持台账顺序、不排序）</span></h2>")
    h.append("<div class='cards'>")
    h.append("<div class='card'>产物分子<br><b>%d</b> 个</div>" % n_prod)
    h.append("<div class='card'>出处路径<br><b>%d</b> 条</div>" % len(rows))
    h.append("<div class='card'>用时<br><b>%s</b> s</div>" % esc(secs))
    h.append("<div class='card'>方向<br>%s</div>"
             % esc(" · ".join("%s %d" % (k, v) for k, v in dirs.most_common())))
    h.append("<div class='card'>条件依据<br>%s</div>"
             % esc(" · ".join("%s %d" % (k, v) for k, v in gates.most_common())))
    h.append("</div>")
    h.append("<div class='bar'>")
    for d in ("全部",) + tuple(k for k, _ in dirs.most_common()):
        h.append("<button onclick=\"filt(this,'%s')\">%s</button>" % (esc(d), esc(d)))
    h.append("<input placeholder='关键词过滤（规则/药材/分子式…）' oninput=\"kw=this.value;apply()\">")
    h.append("</div>")
    h.append("<table id='dt'><thead><tr><th>#</th><th>方向</th><th>规则</th><th>轮</th>"
             "<th>底物</th><th>药材</th><th>条件依据</th><th>产物 SMILES</th></tr></thead><tbody>")
    for i, r in enumerate(rows[:10], 1):
        h.append("<tr data-dir='%s'><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                 "<td>%s</td><td>%s</td><td><code>%s</code></td></tr>"
                 % (esc(r.get("direction_cn") or "（无）"), i,
                    esc(r.get("direction_cn")), esc(r.get("rule_name")), esc(r.get("round")),
                    esc(short(r.get("source_name"), 24)), esc(r.get("source_herb", "").replace("tcm.db:", "")),
                    esc(short(r.get("activation_why"), 46)), esc(short(r.get("product_smiles"), 64))))
    h.append("</tbody></table>")
    h.append("<div class='note'>上面的筛选只影响浏览显示；产物一条不删、不排序。</div>")
    h.append("<p><button disabled>导出 CSV / TSV（小样里不生效）</button>　"
             "<button disabled>在此结果上加一轮（小样里不生效）</button>　"
             "<a href='sample_552_甘草.report.html' target='_blank'>打开完整一页报告 ↗</a>"
             "（真实生成的报告长这样）</p>")
    h.append("</div></div>")

    h.append("<p class='note'>小样说明：这是「报告优先 C + 三步页 A」里的 A 步；C 已可用"
             "（跑完 <code>chemreact.py predict</code> 自动生成一页报告）。界面里每个开关的位置、"
             "默认值，都以你的意见为准。</p>")
    h.append("<script>let kw='',cur='全部';"
             "function apply(){document.querySelectorAll('#dt tbody tr').forEach(tr=>{"
             "const okd=(cur==='全部'||tr.dataset.dir.includes(cur));"
             "const okq=!kw||tr.textContent.includes(kw);"
             "tr.style.display=(okd&&okq)?'':'none';});}"
             "function filt(b,d){cur=d;apply();"
             "document.querySelectorAll('.bar button').forEach(x=>x.style.cssText='');"
             "b.style.background='#2b6cb0';b.style.color='#fff';}"
             "let started=false;"
             "function startRun(){if(started)return;started=true;"
             "const b=document.getElementById('go');b.disabled=true;b.textContent='运行中…';"
             "const p=document.getElementById('prog');p.style.display='block';"
             "const st=['编译模板库…','枚举第 1 轮…','去重与标注…','渲染报告…'];let i=0;"
             "const t=setInterval(()=>{p.textContent='运行中：'+st[i]+'（'+(i+1)+'/4）';i++;"
             "if(i>=4){clearInterval(t);"
             "document.getElementById('results').style.display='block';"
             "b.textContent='已完成（小样）';"
             "document.getElementById('results').scrollIntoView({behavior:'smooth'});}},420);}"
             "</script></body></html>")

    OUT.write_text("\n".join(h), encoding="utf-8")
    print("小样已生成：%s（%d 产物 / %d 出处 / %.0f KB）"
          % (OUT, n_prod, len(rows), OUT.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())

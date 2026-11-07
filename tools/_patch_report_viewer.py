# -*- coding: utf-8 -*-
# One-shot: remove per-row structures, append a SMILES viewer block.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\tools\make_report.py")

VIEWER_LINES = [
    '    h.append("<h2 style=\'font-size:16px\'>%s</h2>"',
    '             % L("结构查看器（输入 SMILES 自行渲染）",',
    '                 "Structure viewer (enter a SMILES)"))',
    '    h.append("<div class=\'card\' style=\'padding:12px\'>"',
    '             "<div style=\'display:flex;gap:8px;flex-wrap:wrap\'>"',
    '             "<input id=\'svIn\' placeholder=\'CC(=O)Oc1ccccc1C(=O)O\' "',
    '             "style=\'flex:1;min-width:280px;padding:8px 10px;border:1px solid #cbd5e0;border-radius:6px\'>"',
    '             "<button onclick=\'svDraw()\' style=\'padding:8px 18px;border-radius:6px;'
    'border:1px solid #2b6cb0;background:#2b6cb0;color:#fff;cursor:pointer\'>"',
    '             + L("渲染", "Draw") + "</button></div>"',
    '             "<div id=\'svOut\' style=\'margin-top:10px;min-height:120px\'></div>"',
    '             "<div class=\'note\' style=\'font-size:12px;color:#666\'>"',
    '             + L("结构由本地服务用 RDKit 现场绘制；请通过 http://127.0.0.1:8765/ 打开本页。",',
    '                 "Rendered locally with RDKit; open this page via http://127.0.0.1:8765/.")',
    '             + "</div></div>")',
    '    h.append("<script>"',
    '             "function svDraw(){"',
    '             "var v=document.getElementById(\'svIn\').value.trim();"',
    '             "var o=document.getElementById(\'svOut\');"',
    '             "if(!v){o.textContent=\'请输入 SMILES\';return;}"',
    '             "o.textContent=\'渲染中…\';"',
    '             "fetch(\'/render?smiles=\'+encodeURIComponent(v))"',
    '             ".then(function(r){if(!r.ok)throw new Error(\'HTTP \'+r.status);return r.text();})"',
    '             ".then(function(t){o.innerHTML=t;})"',
    '             ".catch(function(e){o.textContent=\'渲染失败：\'+e.message;});}"',
    '             "</script>")',
    "",
]


def main() -> int:
    s = P.read_text(encoding="utf-8")
    s = s.replace(
        '             + (("<th>%s</th>" % L("结构", "Structure")) if draw_ok else "")\n',
        "")
    s = s.replace(
        '        svg_cell = ""\n'
        '        if draw_ok:\n'
        '            if i <= MAXDRAW:\n'
        '                svg_cell = _mol_svg(p["smiles"]) or L("（画失败）", "(draw failed)")\n'
        '            else:\n'
        '                svg_cell = L("（略）", "(omitted)")\n',
        "")
    s = s.replace(
        '                    ("<td>%s</td>" % svg_cell) if draw_ok else "",\n',
        "")
    s = s.replace(
        '                 "<td>%s</td><td>%d</td><td>%d</td><td>%s</td><td>%s</td>"\n'
        '                 "<td><code>%s</code></td></tr>"',
        '                 "<td>%d</td><td>%d</td><td>%s</td><td>%s</td>"\n'
        '                 "<td><code>%s</code></td></tr>"')
    s = s.replace(
        '             % (esc(",".join(p["dirs"].keys())), (1 if p["ev_any"] else 0),\n'
        '                esc("、".join(sorted(p["herbs"]))), i,\n',
        '             % (esc(",".join(p["dirs"].keys())), (1 if p["ev_any"] else 0),\n'
        '                esc("、".join(sorted(p["herbs"]))), i,\n')

    if "svDraw" not in s and "    # 明细表" in s:
        s = s.replace("    # 明细表", "\n".join(VIEWER_LINES) + "    # 明细表", 1)

    P.write_text(s, encoding="utf-8", newline="\n")
    print("svDraw=%s chars=%d" % ("svDraw" in s, len(s)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

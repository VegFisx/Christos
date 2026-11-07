# -*- coding: utf-8 -*-
# One-shot: drop the per-row structure images and add a SMILES viewer.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\tools\make_report.py")

EDITS = [
    ('    h.append("<div class=\'wrap\'><table id=\'pt\'><thead><tr><th>#</th>"\n'
     '             + (("<th>%s</th>" % L("结构", "Structure")) if draw_ok else "")\n'
     '             + "<th>%s</th>',
     '    h.append("<div class=\'wrap\'><table id=\'pt\'><thead><tr><th>#</th>"\n'
     '             + "<th>%s</th>'),
    ('        svg_cell = ""\n'
     '        if draw_ok:\n'
     '            if i <= MAXDRAW:\n'
     '                svg_cell = _mol_svg(p["smiles"]) or L("（画失败）", "(draw failed)")\n'
     '            else:\n'
     '                svg_cell = L("（略）", "(omitted)")\n',
     ''),
    ('                 "<td>%s</td><td>%d</td><td>%d</td><td>%s</td><td>%s</td>"',
     '                 "<td>%d</td><td>%d</td><td>%s</td><td>%s</td>"'),
    ('                    ("<td>%s</td>" % svg_cell) if draw_ok else "",\n'
     '                    esc(p["formula"])',
     '                    esc(p["formula"])'),
]

VIEWER = "\n".join([
    "    h.append(\"<h2 style='font-size:16px'>%s</h2>\"",
    "             % L(\"结构查看器（输入 SMILES 自行渲染）\",",
    "                 \"Structure viewer (enter a SMILES)\"))",
    "    h.append(\"<div class='card'>\"",
    "             \"<div class='row' style='display:flex;gap:8px;flex-wrap:wrap'>\"",
    "             \"<input id='svIn' placeholder='CC(=O)Oc1ccccc1C(=O)O' \"",
    "             \"style='flex:1;min-width:280px;padding:8px 10px;border:1px solid #cbd5e0;",
    "border-radius:6px'>\"",
    "             \"<button onclick='svDraw()' style='padding:8px 16px;border-radius:6px;",
    "border:1px solid #2b6cb0;background:#2b6cb0;color:#fff'>\"",
    "             \"%s</button></div>\"",
    "             \"<div id='svOut' style='margin-top:10px;min-height:120px'></div>\"",
    "             \"<div class='note' style='font-size:12px;color:#666'>%s</div></div>\"",
    "             % (L(\"渲染\", \"Draw\"),",
    "                L(\"结构由本地服务用 RDKit 现场绘制；需要通过 http://127.0.0.1:8765/ \"",
    "                  \"打开本页，直接双击文件不行。\",",
    "                  \"Rendered by the local service with RDKit; open this page through \"",
    "                  \"http://127.0.0.1:8765/ rather than the file directly.\")))",
    "",
])

JS = "\n".join([
    "    h.append(\"<script>\"",
    "             \"function svDraw(){var v=document.getElementById('svIn').value.trim();\"",
    "             \"var o=document.getElementById('svOut');\"",
    "             \"if(!v){o.textContent='请输入 SMILES';return;}\"",
    "             \"o.textContent='渲染中…';\"",
    "             \"fetch('/render?smiles='+encodeURIComponent(v))\"",
    "             \".then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.text();})\"",
    "             \".then(function(t){o.innerHTML=t;})\"",
    "             \".catch(function(e){o.textContent='渲染失败：'+e.message+\"",
    "             \"（如果本页是双击打开的，请改用 http://127.0.0.1:8765/ ）';});}\"",
    "             \"</script>\")",
    "",
])


def main() -> int:
    s = P.read_text(encoding="utf-8")
    for i, (old, new) in enumerate(EDITS, 1):
        n = s.count(old)
        print("edit %d hits=%d" % (i, n))
        if n:
            s = s.replace(old, new, 1)

    anchor = '    # 明细表'
    if anchor in s and "svDraw" not in s:
        s = s.replace(anchor, VIEWER + JS + anchor, 1)
        print("viewer inserted")

    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())

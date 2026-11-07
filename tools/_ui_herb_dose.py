# -*- coding: utf-8 -*-
# One-shot: give each herb row a dose multiplier.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

OLD_ROW = ("  box.innerHTML=\"<div class='inputWrap'><input class='herbInput' "
           "placeholder='中药材：甘草 ｜ 物种学名：Glycyrrhiza uralensis' "
           "autocomplete='off'><div class='acBox' hidden></div></div>\"")
NEW_ROW = ("  box.innerHTML=\"<div class='inputWrap'><input class='herbInput' "
           "placeholder='中药材：甘草 ｜ 物种学名：Glycyrrhiza uralensis' "
           "autocomplete='off'><div class='acBox' hidden></div></div>\""
           "\n    +\"<label class='doseWrap' title='份数：同一味药按剂量折算的份数，"
           "默认 1'>份数<input class='herbDose' type='number' min='1' step='1' value='1'></label>\"")

OLD_LIST = ("function herbList(){\n"
            "  return Array.prototype.map.call(document.querySelectorAll('.herbInput'),"
            "function(x){return x.value.trim();}).filter(function(x){return x;});\n"
            "}")
NEW_LIST = "\n".join([
    "function herbList(){",
    "  const out=[];",
    "  document.querySelectorAll('.herbRow').forEach(function(box){",
    "    const v=box.querySelector('.herbInput').value.trim();",
    "    if(!v)return;",
    "    const de=box.querySelector('.herbDose');",
    "    const k=de?Math.max(1,parseInt(de.value||'1',10)||1):1;",
    "    for(let i=0;i<k;i++)out.push(v);",
    "  });",
    "  return out;",
    "}",
])

CSS_ANCHOR = ".acItem .name{font-weight:600}"
CSS_ADD = ("\n.doseWrap{display:flex;align-items:center;gap:6px;font-size:12px;"
           "color:var(--muted);flex:0 0 96px}\n"
           ".doseWrap input{width:56px;padding:6px 8px;border-radius:8px;"
           "border:1px solid var(--input-border);background:var(--panel)}")

HINT_OLD = ("<span class='hint'>一味一行；输入时边打边出候选，「查找相似」用于多选。</span>")
HINT_NEW = ("<span class='hint'>一味一行；份数按剂量折算（默认 1，重复输入同名等价）。"
            "输入时边打边出候选，「查找相似」用于多选。</span>")


def main() -> int:
    s = P.read_text(encoding="utf-8")
    for i, (old, new) in enumerate([
        (OLD_ROW, NEW_ROW),
        (OLD_LIST, NEW_LIST),
        (HINT_OLD, HINT_NEW),
        (CSS_ANCHOR, CSS_ANCHOR + CSS_ADD),
    ], 1):
        n = s.count(old)
        print("edit %d hits=%d" % (i, n))
        if n:
            s = s.replace(old, new, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())

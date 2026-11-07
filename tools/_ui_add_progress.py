# -*- coding: utf-8 -*-
# One-shot: add an indeterminate progress bar shown while a run is active.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

PILL = "<div id='statusPill' class='pill idle'>空闲</div>"
PILL_NEW = (PILL + "\n    <div id='runBar' class='runbar' hidden>"
            "<div class='runbarIn'></div></div>")

CSS = ("\n.runbar{height:4px;border-radius:2px;background:var(--panel2);"
       "border:1px solid var(--line);overflow:hidden;margin:6px 0 0;width:100%}\n"
       ".runbarIn{height:100%;width:35%;background:var(--accent);"
       "animation:runslide 1.2s ease-in-out infinite}\n"
       "@keyframes runslide{0%{transform:translateX(-100%)}"
       "100%{transform:translateX(300%)}}\n")

OLD_JS = ("function setStatus(cls,text){const p=q('statusPill');"
          "p.className='pill '+cls;p.textContent=trText(text);}")
NEW_JS = ("function setStatus(cls,text){const p=q('statusPill');"
          "p.className='pill '+cls;p.textContent=trText(text);"
          "const b=q('runBar');if(b)b.hidden=(cls!=='running');}")


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n1 = s.count(PILL)
    n2 = s.count(OLD_JS)
    print("pill hits=%d  js hits=%d" % (n1, n2))
    s = s.replace(PILL, PILL_NEW, 1)
    s = s.replace(OLD_JS, NEW_JS, 1)
    anchor = "body{margin:0;"
    if anchor in s and ".runbar{" not in s:
        idx = s.index(anchor)
        end = s.index("\n", idx)
        s = s[:end + 1] + CSS + s[end + 1:]
        print("css inserted")
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())

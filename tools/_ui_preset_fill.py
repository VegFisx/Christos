# -*- coding: utf-8 -*-
# One-shot: fill the six condition fields whenever a preset is chosen.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

JS = """
document.addEventListener('DOMContentLoaded',function(){
  const PRESETS={
    '煎煮':      ['water',100,'60','6.5','none','air'],
    '室温浸泡':  ['water',25,'1440','7','none','air'],
    '水提':      ['water',60,'120','7','none','air'],
    '醇提':      ['ethanol',78,'120','7','none','air'],
    '酸水解':    ['water',100,'120','1.5','acid','air'],
    '碱水解':    ['water',100,'120','12','base','air'],
    '酶催化':    ['water',37,'1440','6','enzyme','air'],
    '还原':      ['water',60,'240','7','metal','H2'],
    '氧化':      ['water',100,'240','7','none','O2'],
    '无氧煎煮':  ['water',100,'60','6.5','none','N2']
  };
  const sel=q('cond'),box=q('condCustom');
  if(!sel||!box)return;
  const fill=function(){
    const v=PRESETS[sel.value];
    if(!v)return;
    const ids=['c_solvent','c_temperature','c_time_min','c_ph','c_catalyst','c_atmosphere'];
    ids.forEach(function(id,i){const el=q(id);if(el)el.value=v[i];});
  };
  sel.addEventListener('change',fill);
  fill();
});
"""

OLD_HOOK = "document.addEventListener('DOMContentLoaded',function(){\n  const c=q('cond'),box=q('condCustom');"


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(OLD_HOOK)
    print("hook hits=%d" % n)
    if n:
        s = s.replace(OLD_HOOK, JS + "\n" + OLD_HOOK, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("inserted, %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())

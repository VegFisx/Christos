# -*- coding: utf-8 -*-
# One-shot: insert the six-field block after the formula condition grid.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

ANCHOR = "<label class='field' style='display:none'>辅助试剂<input id='f_reagents'"

BLOCK = "\n".join([
    "    </div>",
    "    <div id='f_condCustom' class='grid3' style='margin-top:6px'>",
    "      <label class='field'>溶剂<input id='fc_solvent' placeholder='water / ethanol'></label>",
    "      <label class='field'>温度 °C<input id='fc_temperature' placeholder='如 80'></label>",
    "      <label class='field'>时长 min<input id='fc_time_min' placeholder='如 60'></label>",
    "      <label class='field'>pH<input id='fc_ph' placeholder='如 6.5'></label>",
    "      <label class='field'>催化剂<input id='fc_catalyst' placeholder='none / acid / base / metal / enzyme'></label>",
    "      <label class='field'>气氛<input id='fc_atmosphere' placeholder='air / O2 / H2 / N2'></label>",
    "    </div>",
    "    <div class='row' style='font-size:12px;color:var(--muted)'>",
    "      <span class='hint'>选预设会自动填入示例值，可逐项覆盖；留空的项用预设值。"
    "预设是工程代表值，不是药典标准。</span>",
    "    </div>",
    "    <div class='grid3' style='margin-top:6px'>",
])


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(ANCHOR)
    print("anchor hits=%d" % n)
    if n and "f_condCustom" not in s:
        s = s.replace(ANCHOR, BLOCK + ANCHOR, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("inserted, %d chars" % len(s))
    print("div open=%d close=%d" % (s.count("<div"), s.count("</div>")))
    return 0


if __name__ == "__main__":
    sys.exit(main())

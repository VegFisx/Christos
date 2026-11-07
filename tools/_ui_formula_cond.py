# -*- coding: utf-8 -*-
# One-shot: give the formula page the same six-field condition editor.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

OLD = "<label class='field'>条件档案<select id='f_cond'>"
NEW = ("<label class='field' title='预设为工程代表值，不是药典标准'>"
       "基准预设（示例值）<select id='f_cond'>")

COND_SEL = ("<select id='f_cond'><option value='煎煮' selected>煎煮</option>"
            "<option value='室温浸泡'>室温浸泡</option>"
            "<option value='水提'>水提</option>"
            "<option value='醇提'>醇提</option>"
            "<option value='酸水解'>酸水解</option>"
            "<option value='碱水解'>碱水解</option>"
            "<option value='酶催化'>酶催化</option>"
            "<option value='还原'>还原</option>"
            "<option value='氧化'>氧化</option>"
            "<option value='无氧煎煮'>无氧煎煮</option></select>")

BLOCK = "\n".join([
    "</div>",
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
])

OLD_BODY = ("const body=new URLSearchParams({kind:'predict',herb:names.join(','),"
            "smiles:'',limit:q('f_limit').value,cond:q('f_cond').value,")
NEW_BODY = ("const _fx=function(id){const el=q(id);return el?el.value:'';};\n"
            "  const body=new URLSearchParams({kind:'predict',herb:names.join(','),"
            "smiles:'',limit:q('f_limit').value,cond:q('f_cond').value,"
            "solvent:_fx('fc_solvent'),temperature:_fx('fc_temperature'),"
            "time_min:_fx('fc_time_min'),ph:_fx('fc_ph'),"
            "catalyst:_fx('fc_catalyst'),atmosphere:_fx('fc_atmosphere'),")

JS_ANCHOR = "document.addEventListener('DOMContentLoaded',function(){\n  const c=q('cond'),box=q('condCustom');"
JS_ADD = """
document.addEventListener('DOMContentLoaded',function(){
  const sel=q('f_cond');
  if(!sel)return;
  const MAP={
    '煎煮':['water',100,'60','6.5','none','air'],
    '室温浸泡':['water',25,'1440','7','none','air'],
    '水提':['water',60,'120','7','none','air'],
    '醇提':['ethanol',78,'120','7','none','air'],
    '酸水解':['water',100,'120','1.5','acid','air'],
    '碱水解':['water',100,'120','12','base','air'],
    '酶催化':['water',37,'1440','6','enzyme','air'],
    '还原':['water',60,'240','7','metal','H2'],
    '氧化':['water',100,'240','7','none','O2'],
    '无氧煎煮':['water',100,'60','6.5','none','N2']
  };
  const fill=function(){
    const v=MAP[sel.value];if(!v)return;
    const ids=['fc_solvent','fc_temperature','fc_time_min','fc_ph','fc_catalyst','fc_atmosphere'];
    ids.forEach(function(id,i){const el=q(id);if(el)el.value=v[i];});
  };
  sel.addEventListener('change',fill);fill();
});
"""


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n1 = s.count(OLD)
    print("label hits=%d" % n1)
    s = s.replace(OLD, NEW, 1)

    # 在方剂条件 grid3 之后插入六参数块
    idx = s.find("<select id='f_cond'>")
    if idx > 0:
        close = s.find("</label></div>", idx)
        grid_end = s.find("</div>", close) if close > 0 else -1
        if grid_end > 0:
            s = s[:grid_end] + BLOCK + s[grid_end + len("</div>"):]
            print("block inserted")

    n2 = s.count(OLD_BODY)
    print("body hits=%d" % n2)
    s = s.replace(OLD_BODY, NEW_BODY, 1)

    if JS_ANCHOR in s:
        s = s.replace(JS_ANCHOR, JS_ADD + "\n" + JS_ANCHOR, 1)
        print("js inserted")

    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())

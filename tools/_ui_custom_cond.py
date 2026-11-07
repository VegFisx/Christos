# -*- coding: utf-8 -*-
# One-shot: add a "custom conditions" option to the predict form.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

COND_SEL = ("<select id='cond'><option value='煎煮' selected>煎煮</option>"
            "<option value='室温浸泡'>室温浸泡</option>"
            "<option value='水提'>水提</option>"
            "<option value='醇提'>醇提</option>"
            "<option value='酸水解'>酸水解</option>"
            "<option value='碱水解'>碱水解</option>"
            "<option value='酶催化'>酶催化</option>"
            "<option value='还原'>还原</option>"
            "<option value='氧化'>氧化</option>"
            "<option value='无氧煎煮'>无氧煎煮</option></select>")

COND_SEL_NEW = COND_SEL.replace(
    "</select>", "<option value='自定义'>自定义…</option></select>")

CUSTOM_BLOCK = """
    <div id='condCustom' class='grid3'>
      <label class='field' title='留空则沿用所选条件档案'>溶剂<input id='c_solvent' placeholder='water / ethanol'></label>
      <label class='field'>温度 °C<input id='c_temperature' placeholder='如 80'></label>
      <label class='field'>时长 min<input id='c_time_min' placeholder='如 60'></label>
      <label class='field'>pH<input id='c_ph' placeholder='如 6.5'></label>
      <label class='field'>催化剂<input id='c_catalyst' placeholder='none / acid / base / metal / enzyme'></label>
      <label class='field'>气氛<input id='c_atmosphere' placeholder='air / O2 / H2 / N2'></label>
    </div>
    <div class='row' style='font-size:12px;color:var(--muted)'>
      <span class='hint'>直接填参数；留空的项沿用下方预设的值。预设只是快捷模板，可随时改。</span>
    </div>
"""

ANCHOR = "<details class='adv'><summary>高级选项</summary>"

OLD_BODY = ("const body=new URLSearchParams({herb:herb,smiles:smi,"
            "limit:q('limit').value,cond:q('cond').value,"
            "rounds:q('rounds').value,max_pairs:q('max_pairs').value,"
            "reagents:q('reagents').value,")

NEW_BODY = ("const _cx=function(id){const el=q(id);return el?el.value:'';};\n"
            "  const body=new URLSearchParams({herb:herb,smiles:smi,"
            "limit:q('limit').value,cond:q('cond').value,"
            "rounds:q('rounds').value,max_pairs:q('max_pairs').value,"
            "reagents:q('reagents').value,"
            "solvent:_cx('c_solvent'),temperature:_cx('c_temperature'),"
            "time_min:_cx('c_time_min'),ph:_cx('c_ph'),"
            "catalyst:_cx('c_catalyst'),atmosphere:_cx('c_atmosphere'),")

JS_HOOK_ANCHOR = "function setStatus(cls,text){"
JS_HOOK = """
document.addEventListener('DOMContentLoaded',function(){
  const c=q('cond'),box=q('condCustom');
  if(c&&box){
    const sync=function(){box.hidden=(c.value!=='自定义');};
    c.addEventListener('change',sync);sync();
  }
});
"""


def main() -> int:
    s = P.read_text(encoding="utf-8")
    print("cond select hits=%d" % s.count(COND_SEL))
    s = s.replace(COND_SEL, COND_SEL_NEW, 1)
    print("anchor hits=%d" % s.count(ANCHOR))
    s = s.replace(ANCHOR, CUSTOM_BLOCK.strip() + "\n    " + ANCHOR, 1)
    print("body hits=%d" % s.count(OLD_BODY))
    s = s.replace(OLD_BODY, NEW_BODY, 1)
    if JS_HOOK_ANCHOR in s and "condCustom" in s and "DOMContentLoaded" not in s:
        s = s.replace(JS_HOOK_ANCHOR, JS_HOOK + JS_HOOK_ANCHOR, 1)
        print("js hook inserted")
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())

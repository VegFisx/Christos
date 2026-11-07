# -*- coding: utf-8 -*-
# One-shot: add a "how to read the ledger" panel under the results card.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

ANCHOR = ("  <div id='meta'></div>\n</div>")

GUIDE = "\n".join([
    "  <div id='meta'></div>",
    "  <details class='adv' style='margin-top:10px'>",
    "    <summary>怎么看这份台账</summary>",
    "    <div style='font-size:13px;line-height:1.7;padding:6px 2px'>",
    "      <p><b>先看四列，回答「这是什么」</b></p>",
    "      <ul>",
    "        <li><code>product_smiles</code> / <code>formula</code> / <code>mw</code>"
    " —— 产物结构、分子式、分子量</li>",
    "        <li><code>source_herb</code> + <code>source_name</code>"
    " —— 来自哪味药、哪个成分</li>",
    "        <li><code>rule_name</code> —— 触发它的反应规则</li>",
    "        <li><code>round</code> —— 第几轮出现（1 = 直接由原料成分生成）</li>",
    "      </ul>",
    "      <p><b>再看两列，判断「有没有依据」</b></p>",
    "      <ul>",
    "        <li><code>activation_why</code> —— 条件依据。写「无 ORD 条件数据，放行」"
    "表示条件层没查到匹配记录，不是「已证实能发生」</li>",
    "        <li><code>template_support</code> —— 这条模板在来源数据库里出现过的次数。0 表示没有先例</li>",
    "      </ul>",
    "      <p><b>方向标记</b>：<code>direction</code> 为 <code>suspect</code> 表示该产物与当前介质"
    "的方向相反（例如水相里出现缩合），只是提醒，候选仍保留。</p>",
    "      <p><b>可以忽略的列</b>：<code>product_inchikey</code>（机器标识）、"
    "<code>score</code>（系统不打分，恒为 0）、<code>co_products</code>（配平用的伴生产物）。</p>",
    "      <p style='color:var(--muted)'>台账是枚举结果，不是结论。查不到不等于不存在，"
    "查到也不等于已被实验证实。</p>",
    "    </div>",
    "  </details>",
    "</div>",
])


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(ANCHOR)
    print("anchor hits=%d" % n)
    if n:
        s = s.replace(ANCHOR, GUIDE, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("inserted, %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())

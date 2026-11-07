# -*- coding: utf-8 -*-
r"""人工核对 gold_check 的失败样例：是数据错，还是我的匹配太严？"""
import sys, zipfile, re
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
Z = r"D:/ProgramData/DSHNS/chemreact-staging/reports/_probe_net/indkb.zip"
zf = zipfile.ZipFile(Z)
idx = {}
for n in zf.namelist():
    if n.lower().endswith(".md"):
        idx.setdefault(n.rsplit("/", 1)[-1][:-3], n)
CASES = [("炙甘草", "甘草酸"), ("干姜", "6-姜辣素"), ("功劳木", "盐酸小檗碱"), ("乳康丸", "〔规格〕")]
for herb, kw in CASES:
    print("=" * 70)
    p = idx.get(herb)
    print("样例:", herb, "/", kw, "->", p)
    if not p:
        continue
    text = zf.read(p).decode("utf-8", errors="replace")
    print("  md 长度:", len(text))
    hit = [m.start() for m in re.finditer(re.escape(kw), text)]
    print("  关键词命中次数:", len(hit))
    # 松散找：把数字/符号都去掉，只看中文字符串包含关系
    if not hit:
        core = re.sub(r"[^\u4e00-\u9fff]", "", kw)
        loose = [m.start() for m in re.finditer(re.escape(core), text)] if core else []
        print("  去符号后", core, "命中:", len(loose))
        for s in loose[:1]:
            print("   ...上下文:", text[max(0, s-60):s+60].replace(chr(10), " "))
    else:
        s = hit[0]
        print("  ...上下文:", text[max(0, s-80):s+80].replace(chr(10), " "))
    for pat in (r"[0-9.]+\s*%", r"不得少于", r"〔规格〕"):
        mm = re.findall(pat, text)
        if mm:
            print("  文本里出现的", pat, "->", mm[:6])

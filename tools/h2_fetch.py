# -*- coding: utf-8 -*-
r"""H2 · 联网取证的**抓取器**（只读网页，不写入任何外部站点）。

对 `data\h2_sample.json` 里的每一条，去公开搜索引擎查「方名 + 组成」，
把**原始结果**（标题 / 链接 / 摘要）存到 `reports\_h2_net\`，作为逐条判定的证据。

用法：
    python tools\h2_fetch.py --engine ddg  --limit 100
    python tools\h2_fetch.py --engine bing --limit 100
    python tools\h2_fetch.py --engine ddg  --start 21 --limit 20     # 续抓

纪律（照 AGENTS.md）：
  * **失败必须打印并计数**，不许静默跳过；
  * 每次请求间隔 `--sleep` 秒（默认 2.0），不连续轰站点；
  * 只存证据文件，不改任何外部数据；抓不到就写明抓不到。
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
SAMPLE = STAGE / "data" / "h2_sample.json"
OUTDIR = STAGE / "reports" / "_h2_net"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch(url: str, timeout: int = 25) -> str:
    # URL 里可能混着中文（有些站点直接给中文路径）——先按规范转义，避免 ascii 编码错
    url = urllib.parse.quote(url, safe=":/?&=#%[]@!$'()*+,;~-")
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        ctype = resp.headers.get("Content-Type", "") or ""
    m = re.search(r"charset=([\w\-]+)", ctype, re.I)
    enc = (m.group(1) if m else "").lower()
    if not enc:
        head = raw[:4000].decode("latin-1", errors="replace")
        m2 = re.search(r'charset=["\']?([\w\-]+)', head, re.I)
        enc = (m2.group(1) if m2 else "utf-8").lower()
    if enc in ("gb2312", "gbk", "gb18030"):
        enc = "gb18030"
    try:
        return raw.decode(enc, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


TAG = re.compile(r"<[^>]+>")


def strip_tags(s: str) -> str:
    s = TAG.sub("", s)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'"), ("&hellip;", "…")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def parse_ddg(html: str) -> list:
    out = []
    for m in re.finditer(
            r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        out.append({"url": urllib.parse.unquote(m.group(1)), "title": strip_tags(m.group(2)),
                    "snippet": ""})
    for i, m in enumerate(re.finditer(
            r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)):
        if i < len(out):
            out[i]["snippet"] = strip_tags(m.group(1))
    if not out:                                    # 新版页面结构兜底
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.S):
            t = strip_tags(m.group(2))
            if len(t) > 8:
                out.append({"url": m.group(1), "title": t, "snippet": ""})
    return out[:10]


def parse_bing(html: str) -> list:
    out = []
    for m in re.finditer(r'<li class="b_algo".*?</li>', html, re.S):
        blk = m.group(0)
        # 标题锚点：Bing 现在不一定是 <h2><a>，直接取块里**第一个外链**（最稳）
        a = re.search(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not a:
            continue
        title = strip_tags(a.group(2))
        title = re.sub(r"^[\w.\-]+\.\w{2,}https?://\S*\s*", "", title).strip()   # 去掉"域名https://…"前缀
        # ★ 摘要直接取**整个结果块**去掉标签后的文本（比挑 <p> 稳；块里就是标题+描述+日期）
        blob = strip_tags(blk)
        blob = re.sub(r"^[\w.\-]+\.\w{2,}https?://\S*", "", blob).strip()
        if title and blob.startswith(title):
            blob = blob[len(title):].strip()
        out.append({"url": a.group(1), "title": title, "snippet": blob[:400]})
    return out[:10]


ENGINES = {
    "ddg": ("https://html.duckduckgo.com/html/?q=%s", parse_ddg),
    "bing": ("https://www.bing.com/search?setlang=zh-CN&q=%s", parse_bing),
}


def parse_360(html: str) -> list:
    out = []
    for m in re.finditer(r'<li class="res-list[^"]*".*?</li>', html, re.S):
        blk = m.group(0)
        a = re.search(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not a:
            continue
        sn = re.search(r'<p[^>]*class="res-desc"[^>]*>(.*?)</p>', blk, re.S)
        if not sn:
            sn = re.search(r'<p[^>]*>(.*?)</p>', blk, re.S)
        out.append({"url": a.group(1), "title": strip_tags(a.group(2)),
                    "snippet": strip_tags(sn.group(1)) if sn else ""})
    return out[:10]


def parse_sogou(html: str) -> list:
    out = []
    for m in re.finditer(r'<div class="(?:vrwrap|rb)"[^>]*>.*?(?=<div class="(?:vrwrap|rb)"|</body>)',
                         html, re.S):
        blk = m.group(0)
        a = re.search(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not a:
            continue
        sn = re.search(r'class="(?:text-layout|space-txt|str-text|fz-mid)[^"]*"[^>]*>(.*?)</',
                       blk, re.S)
        out.append({"url": a.group(1), "title": strip_tags(a.group(2)),
                    "snippet": strip_tags(sn.group(1)) if sn else ""})
    return out[:10]


ROTATION = [
    ("360", "https://www.so.com/s?q=%s", parse_360),
    ("sogou", "https://www.sogou.com/web?query=%s", parse_sogou),
    ("bing", "https://cn.bing.com/search?mkt=zh-CN&setlang=zh-CN&q=%s", parse_bing),
]

# 补抓用：优先 360（命中率最高），被封时退 Bing（本轮实测 Bing+新解析可用）
RECHECK = [
    ("360", "https://www.so.com/s?q=%s", parse_360),
    ("bing", "https://cn.bing.com/search?mkt=zh-CN&setlang=zh-CN&q=%s", parse_bing),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="rotate", choices=sorted(ENGINES) + ["rotate"])
    ap.add_argument("--recheck", action="store_true",
                    help="只补抓 data\\h2_refetch.json 里列出的序号，用 360/Bing(cn)")
    ap.add_argument("--refetch-file", default=str(STAGE / "data" / "h2_refetch.json"))
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--start", type=int, default=1, help="从清单第几条开始（1 起）")
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--outdir", default=str(OUTDIR))
    ap.add_argument("--sample", default=str(SAMPLE), help="抽样文件（第二批用 h2_sample2.json）")
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    items = json.loads(Path(a.sample).read_text(encoding="utf-8"))["items"]
    if a.recheck:
        want = set(json.loads(Path(a.refetch_file).read_text(encoding="utf-8"))["weak"])
        todo = [x for x in items if x["序号"] in want]
        a.engine = "rotate"
    else:
        todo = [x for x in items if x["序号"] >= a.start][:a.limit]
    print("=" * 100)
    print("H2 取证抓取：引擎 %s ｜ 本次 %d 条（#%d 起）→ %s"
          % (a.engine, len(todo), a.start, outdir))
    print("=" * 100)

    n_ok = n_fail = n_empty = 0
    fails = []
    for k, x in enumerate(todo):
        if a.engine == "rotate":
            pool = RECHECK if a.recheck else ROTATION
            name, tmpl, parser = pool[k % len(pool)]
        else:
            name, (tmpl, parser) = a.engine, ENGINES[a.engine]
        q = "%s 组成" % x["方名"]
        url = tmpl % urllib.parse.quote(q, safe="")
        fp = outdir / ("%03d_%s.json" % (x["序号"], re.sub(r"[^\w\u4e00-\u9fff]", "_", x["方名"])))
        try:
            html = fetch(url)
            res = parser(html)
            if not res:
                n_empty += 1
            else:
                n_ok += 1
            fp.write_text(json.dumps({"序号": x["序号"], "方名": x["方名"], "出处": x["出处"],
                                      "组成": x["组成"], "query": q, "engine": a.engine,
                                      "engine_used": name, "url": url,
                                      "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                      "results": res}, ensure_ascii=False, indent=1),
                          encoding="utf-8")
            print("  #%03d %-14s %-6s → %d 条结果 %s"
                  % (x["序号"], x["方名"][:14], name, len(res),
                     res[0]["title"][:34] if res else "（空）"))
        except Exception as ex:                                  # noqa: BLE001 —— 打印+计数
            n_fail += 1
            fails.append((x["序号"], x["方名"], "%s: %s" % (type(ex).__name__, ex)))
            print("  #%03d %-14s → ★失败：%s: %s" % (x["序号"], x["方名"], type(ex).__name__, ex))
        if k < len(todo) - 1:
            time.sleep(a.sleep + random.random() * 0.8)
    print()
    print("  成功 %d ｜ 结果为空 %d ｜ 失败 %d" % (n_ok, n_empty, n_fail))
    if fails:
        print("  ★ 失败清单（不许静默）：")
        for i, nm, why in fails[:20]:
            print("      #%03d %-14s %s" % (i, nm, why))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

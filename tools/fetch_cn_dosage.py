# -*- coding: utf-8 -*-
"""Fetch Chinese reference pages and print only dosage/fire/time sentences.

Usage:
  python -I tools/fetch_cn_dosage.py <url> [<url> ...]

Pages are saved under reports/_paozhi_src/cn/ (own directory). This script only
reads them back and prints matched snippets.
"""
import hashlib
import html
import re
import sys
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

OUT = Path("D:/ProgramData/DSHNS/chemreact-staging/reports/_paozhi_src/cn")
KEYS = re.compile(r"盐炙|姜炙|姜汁|食盐|生姜|文火|中火|温度|分钟|min|100kg|100 kg|2kg|10kg|2%|10%")


def decode(data: bytes) -> str:
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def clean(fragment: str) -> str:
    fragment = re.sub(r"(?is)<(script|style).*?</\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = html.unescape(fragment)
    return re.sub(r"\s+", " ", fragment).strip()


def main(urls):
    OUT.mkdir(parents=True, exist_ok=True)
    for url in urls:
        print("=" * 100)
        print(url)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            data = urllib.request.urlopen(req, timeout=40).read()
        except Exception as ex:
            print(f"  !! fetch failed: {type(ex).__name__}: {ex}")
            continue
        text = decode(data)
        slug = hashlib.md5(url.encode()).hexdigest()[:10]
        dest = OUT / f"{slug}.html"
        dest.write_text(text, encoding="utf-8")
        title = re.search(r"(?is)<title>(.*?)</title>", text)
        print(f"  title={clean(title.group(1)) if title else ''}")
        body = clean(text)
        hits = 0
        for sent in re.split(r"(?<=[。！？；])\s*", body):
            if KEYS.search(sent) and 8 <= len(sent) <= 300:
                hits += 1
                if hits <= 40:
                    print(f"  - {sent}")
        print(f"  -- {hits} hit(s); file={dest}")


if __name__ == "__main__":
    main(sys.argv[1:])

# -*- coding: utf-8 -*-
"""Extract Chinese UI strings from ui_page.html into reports/i18n_zh_strings.txt."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "integration" / "tcmai_bridge" / "ui_page.html"
OUT = ROOT / "reports" / "i18n_zh_strings.txt"


def main() -> int:
    s = SRC.read_text(encoding="utf-8")
    html = re.sub(r"(?s)<script>.*?</script>", "", s)
    html = re.sub(r"(?s)<style>.*?</style>", "", html)
    texts: list[str] = []
    for m in re.finditer(r">([^<>]*[\u4e00-\u9fff][^<>]*)<", html):
        t = re.sub(r"\s+", " ", m.group(1)).strip()
        if t:
            texts.append(t)
    for m in re.finditer(
        r"(?:placeholder|title|aria-label)=['\"]([^'\"]*[\u4e00-\u9fff][^'\"]*)['\"]",
        html,
    ):
        texts.append(m.group(1).strip())
    js = "\n".join(re.findall(r"(?s)<script>(.*?)</script>", s))
    for m in re.finditer(
        r"(['\"`])((?:\\.|(?!\1).)*[\u4e00-\u9fff](?:\\.|(?!\1).)*)\1", js
    ):
        t = re.sub(r"\s+", " ", m.group(2)).strip()
        if t:
            texts.append(t)
    uniq = sorted(set(texts), key=lambda x: (len(x), x))
    OUT.write_text("\n".join(uniq), encoding="utf-8")
    print("count", len(uniq), "->", OUT)
    for i, t in enumerate(uniq, 1):
        print(f"{i:03d}\t{t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
r"""一次性：从 PPRC 的"2020 药典一部.docx"里抽取某味药的【含量测定】段落（可行性验证）。

用法: python tools\_probe_chp_extract.py [药材名] [zip路径] [docx名]
只读 zip；文本就地解析（stdlib，无需 python-docx）。
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ZIP = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\_probe_net\pprc.zip")
DOCX = "PPRC-main/docx/2020年药典一部.docx"


def docx_paragraphs(blob: bytes) -> list:
    """docx 字节 -> 段落文本列表（stdlib：解析 word/document.xml）。"""
    import io
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    # 段落切分 + 去标签；w:tab/换行占位
    xml = xml.replace("</w:p>", "\n").replace("<w:tab/>", "\t").replace("<w:br/>", "\n")
    text = re.sub(r"<[^>]+>", "", xml)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return [ln.strip() for ln in text.split("\n")]


def main() -> int:
    herb = sys.argv[1] if len(sys.argv) > 1 else "甘草"
    zpath = Path(sys.argv[2]) if len(sys.argv) > 2 else ZIP
    docx = sys.argv[3] if len(sys.argv) > 3 else DOCX
    with zipfile.ZipFile(zpath) as z:
        blob = z.read(docx)
    paras = docx_paragraphs(blob)
    print("段落总数 %d" % len(paras))
    # 找标题段（归一化去空格后与药材名相等；药典排版里两字标题常带空格，如「甘 草」）
    hits = []
    for i, p in enumerate(paras):
        if p.replace(" ", "").replace("\u3000", "") == herb:
            window = [q for q in paras[i + 1:i + 8] if q][:6]
            if any("本品" in q[:24] for q in window):
                hits.append(i)
    print("标题段候选（后随'本品…'）：", [(i, paras[i + 1][:36]) for i in hits[:6]])
    if not hits:
        print("没找到 %s 的标题段" % herb)
        return 1
    i0 = hits[0]
    # 收集到下一味药的标题（用启发式：到下一个完全等于某段【…】之外 —— 简化：取 800 段以内直到再遇到"本品为"且前面是短标题）
    body = []
    for j in range(i0, min(i0 + 900, len(paras))):
        body.append(paras[j])
        if j > i0 + 3 and paras[j].startswith("本品") and len(paras[j - 1]) < 12 and paras[j - 1] != herb:
            break
    text = "\n".join(body)
    print("正文长度 %d 字符" % len(text))
    # 抽【含量测定】
    m = re.search(r"【含量测定】(.{0,2200}?)(?:【|$)", text, re.S)
    if not m:
        print("没找到【含量测定】段")
        return 1
    sec = m.group(1).strip()
    print("---- %s · 含量测定（前 1200 字） ----" % herb)
    print(sec[:1200])
    return 0


if __name__ == "__main__":
    sys.exit(main())

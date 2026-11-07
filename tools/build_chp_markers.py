# -*- coding: utf-8 -*-
r"""从 PPRC 版《2020 药典一部.docx》抽取"药材 → 含量测定/鉴别成分"表（30 味试点）。

用法:
  python tools\build_chp_markers.py                 # 默认 30 味
  python tools\build_chp_markers.py 甘草 黄芪 ...    # 指定药材

输出:
  reports\chp_markers\chp2020_markers.jsonl   每行一条：药材/段落/成分原文/限量/出处段号
  reports\chp_markers\summary.json            每味：找到与否 / 含量测定条数 / 鉴别条数

口径与限制（写清楚，不装）：
* docx 为 OCR 转排文本，存在少量字形噪声（苷→昔、铵→铉 等），**原文与清洗名都保留**；
* 「含量测定」里的聚合指标（总黄酮/挥发油/浸出物…）如实收录并标 kind=aggregate；
* 抽取是**候选表**：每条都带原文上下文，供人工抽查后再作为判据使用。
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
ZIP = STAGE / "reports" / "_probe_net" / "pprc.zip"
DOCX = "PPRC-main/docx/2020年药典一部.docx"
OUT_DIR = STAGE / "reports" / "chp_markers"

HERBS_30 = ["甘草", "黄芪", "人参", "当归", "柴胡", "白芍", "白术", "茯苓", "川芎", "丹参",
            "黄芩", "黄连", "金银花", "连翘", "陈皮", "枳实", "薄荷", "桔梗", "半夏", "麻黄",
            "桂枝", "生姜", "大枣", "枸杞", "菊花", "山楂", "五味子", "大黄", "葛根", "牡丹皮"]

AGG = ("挥发油", "总黄酮", "总皂苷", "总多糖", "多糖", "浸出物", "总生物碱", "总酚",
       "总蒽醌", "水溶性浸出物", "醇溶性浸出物", "总灰分", "酸不溶性灰分")

# 拼音锚点：标题被 OCR 咬字时（如 川芎->「川 B」、黄芪->「黄芷」）用拼音行反推标题
PINYIN = {"甘草": "gancao", "黄芪": "huangqi", "人参": "renshen", "当归": "danggui",
          "柴胡": "chaihu", "白芍": "baishao", "白术": "baizhu", "茯苓": "fuling",
          "川芎": "chuanxiong", "丹参": "danshen", "黄芩": "huangqin", "黄连": "huanglian",
          "金银花": "jinyinhua", "连翘": "lianqiao", "陈皮": "chenpi", "枳实": "zhishi",
          "薄荷": "bohe", "桔梗": "jiegeng", "半夏": "banxia", "麻黄": "mahuang",
          "桂枝": "guizhi", "生姜": "shengjiang", "大枣": "dazao", "枸杞": "gouqizi",
          "菊花": "juhua", "山楂": "shanzha", "五味子": "wuweizi", "大黄": "dahuang",
          "葛根": "gegen", "牡丹皮": "mudanpi"}


def norm(x: str) -> str:
    x = unicodedata.normalize("NFKC", x or "")
    return x.replace(" ", "").replace("\u3000", "").replace("\t", "").strip()


def docx_paragraphs(blob: bytes):
    import io
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = xml.replace("</w:p>", "\n").replace("<w:tab/>", "\t").replace("<w:br/>", "\n")
    text = re.sub(r"<[^>]+>", "", xml)
    text = (text.replace("&amp;", "&").replace("&lt;", "<")
            .replace("&gt;", ">").replace("&quot;", '"'))
    return [ln.strip() for ln in text.split("\n")]


def looks_like_title(paras, i: int) -> bool:
    p = norm(paras[i])
    if not re.fullmatch(r"[\u4e00-\u9fffA-Za-z]{2,14}", p or ""):
        return False
    if len(re.findall(r"[\u4e00-\u9fff]", p)) < 2:     # 纯拉丁行（如 RADIX ET RHIZOMA 分行）不算标题
        return False
    # ★ 硬规则：正文标题的前几段必须出现过【贮藏】（上一位药材的结尾）——否则是表格断句等假标题
    if not any("【贮藏" in paras[j] for j in range(max(0, i - 8), i)):
        return False
    window = [q for q in paras[i + 1:i + 8] if q][:6]
    return any(norm(q).startswith("本品") for q in window)   # 必须是"本品…"开头（防表格/子标题误判）


def find_monograph(paras, herb: str):
    """返回该药材正文条目的起始段号（先精确标题；不成则用拼音行反推，OCR 咬字也能救）。"""
    for i, p in enumerate(paras):
        if norm(p) == herb and looks_like_title(paras, i):
            return i
    py = PINYIN.get(herb, "")
    if py:
        for i, p in enumerate(paras):
            if norm(p).lower() == py:
                window = [q for q in paras[i:i + 7] if q][:5]
                if any("本品" in q[:28] for q in window):
                    j = i - 1
                    while j > 1 and not paras[j]:
                        j -= 1
                    return j
    return None


def sections_of(body):
    secs, cur = {}, None
    for p in body:
        m = re.match(r"^【([^】]{1,12})】(.*)$", p)
        if m:
            cur = m.group(1)
            secs.setdefault(cur, []).append(m.group(2))
        elif cur:
            secs[cur].append(p)
    return secs


NUM_FIX = str.maketrans("０１２３４５６７８９", "0123456789")


def tidy(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(NUM_FIX)
    s = re.sub(r"(?<=[\u4e00-\u9fff])[\s]+(?=[\u4e00-\u9fff])", "", s)   # "不得少 于" -> "不得少于"
    s = re.sub(r"(?<=\d)\s*[。.]\s*(?=\d)", ".", s)        # "0。50" / "0. 50" -> "0.50"
    s = re.sub(r"(?<=\d)\s*[,，]\s*(?=\d)", ".", s)        # "2, 0" -> "2.0"（含 OCR 逗号当小数点；逐条人工复核）
    s = re.sub(r"(?<=\d)\s+(?=\d)", "", s)                 # 其余数字间空格
    return s


def grab_formula(ctx: str) -> str:
    """从上下文括号里抓分子式，并做保守清洗（首字母大写；OCR 的 Z->2）。

    返回清洗后的式子；形状不像分子式时原样返回（≤24 字符），交由人工复核。
    """
    # 注意：tidy() 走了 NFKC，全角（）会变半角()，两种都要认
    ms = re.findall(r"[（(]([^）)]{1,40})[）)]", ctx)
    if not ms:
        return ""
    raw = ms[-1]
    f = raw.replace(" ", "").replace("\u3000", "")
    f = re.sub(r"[.。](?=\d)", "O", f)         # OCR：H22.9 -> H22O9
    f = f[0].upper() + f[1:]                    # c21 -> C21
    f = f.replace("Z", "2").replace("z", "2")   # OCR：C4Z -> C42
    if re.fullmatch(r"(?:Cl|Br|[CHONSPI][a-z]?[0-9]*)+", f):
        return f
    return f[:24] or raw[:24]


def parse_limit_rows(herb: str, sec_text: str, pi: int):
    rows = []
    t = tidy(sec_text)
    for m in re.finditer(r"不得(少于|过)\s*([0-9]+(?:\.[0-9]+)?)\s*(%|mg|ml|g)", t):
        rel, val, unit = m.group(1), m.group(2), m.group(3)
        ctx = t[max(0, m.start() - 90):m.start()]
        seg = re.split(r"[，,。；;]", ctx.strip())[-1]      # 取"数字前最后一段"（避免把上一个数字的尾巴带进来）
        if "含" in seg:
            seg = seg.split("含")[-1]
        seg = re.sub(r"^[^，,；;]{0,24}?计[，,]?\s*", "", seg)
        seg = re.sub(r"（[^）]{0,40}）|\([^)]{0,40}\)", "", seg)
        name = seg.strip(" ，,；;。:：@*")
        name = re.sub(r"^(本品)?(按干燥品计算|按干燥品|以[^，,]{1,16}计)?[，,]?", "", name)
        name = name.strip(" ，,；;。:：")
        ref = ""
        mref = re.search(r"以([\u4e00-\u9fffA-Za-z0-9]{2,16})计", ctx)
        if mref:
            ref = mref.group(1)
        kind = "aggregate" if name in AGG else "compound"
        if "总量计" in ctx:
            kind = "aggregate_total"                      # 如"以X、Y…的总量计，不得少于"（多成分合计）
        flag = ""
        if re.search(r"[^\u4e00-\u9fff]", name) or name == herb:
            flag = "ocr_suspect"                          # OCR 咬字（苷-># 等）；复核时用分子式校正
        formula = grab_formula(ctx)
        rows.append({"herb": herb, "section": "含量测定", "para": pi,
                     "name_raw": name, "ref": ref, "relation": "不得" + rel,
                     "value": float(val), "unit": unit, "kind": kind, "formula": formula,
                     "flag": flag, "pos": m.start(),
                     "context": t[max(0, m.start() - 110):m.end() + 10]})
    seen, out = set(), []
    for r in rows:
        k = (r["name_raw"], r["relation"], r["value"], r["unit"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def parse_identify_rows(herb: str, sec_text: str, pi: int):
    rows, seen = [], set()
    for m in re.finditer(r"取([\u4e00-\u9fff]{2,12})对照品", tidy(sec_text)):
        n = m.group(1)
        if n not in seen:
            seen.add(n)
            rows.append({"herb": herb, "section": "鉴别", "para": pi,
                         "name_raw": n, "ref": "", "relation": "对照品",
                         "value": None, "unit": "", "kind": "compound",
                         "context": sec_text[max(0, m.start() - 30):m.end() + 10]})
    return rows


def main() -> int:
    herbs = sys.argv[1:] or HERBS_30
    if not ZIP.exists():
        print("缺 PPRC zip：%s（先跑 _probe_dl_repos.py）" % ZIP)
        return 2
    with zipfile.ZipFile(ZIP) as z:
        paras = docx_paragraphs(z.read(DOCX))
    mode_all = not sys.argv[1:]
    print("段落 %d · 模式 %s" % (len(paras), "全量扫描" if mode_all else "指定 %d 味" % len(herbs)))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jobs = []      # (herb, i0, body)
    if mode_all:
        cands = []
        for i, p in enumerate(paras):
            np_ = norm(p)
            if not re.fullmatch(r"[\u4e00-\u9fffA-Za-z（）]{2,20}", np_ or ""):
                continue
            if len(re.findall(r"[\u4e00-\u9fff]", np_)) < 1:
                continue
            if not any("【贮藏" in paras[j] for j in range(max(0, i - 8), i)):
                continue
            window = [q for q in paras[i + 1:i + 8] if q][:6]
            if not any(norm(q).startswith("本品") for q in window):
                continue
            cands.append((i, re.sub(r"[A-Za-z]", "", np_)))
        print("候选条目 %d 个" % len(cands))
        for k, (i0, name) in enumerate(cands):
            i_end = cands[k + 1][0] if k + 1 < len(cands) else len(paras)
            jobs.append((name, i0, paras[i0:i_end]))
    else:
        for herb in herbs:
            i0 = find_monograph(paras, herb)
            if i0 is None:
                print("  x %s：没找到正文条目" % herb)
                continue
            body, i = [], i0
            while i < len(paras) and len(body) < 1500:
                if i > i0 + 2 and looks_like_title(paras, i):
                    break
                body.append(paras[i])
                i += 1
            jobs.append((herb, i0, body))
    rows, summary = [], {}
    for herb, i0, body in jobs:
        secs = sections_of(body)
        in_pian_para = next((i0 + k for k, q in enumerate(body) if norm(q) == "饮片"), None)
        n_c = n_i = 0
        if "含量测定" in secs:
            sec_txt = " ".join(secs["含量测定"])
            rr = parse_limit_rows(herb, sec_txt, i0)
            rows += rr
            n_c = len(rr)
            summ_ip = tidy(sec_txt).find("饮片")   # 与行的 pos 同坐标系（都取 tidy 后的文本）
        else:
            summ_ip = -1
        if "鉴别" in secs:
            rr = parse_identify_rows(herb, " ".join(secs["鉴别"]), i0)
            rows += rr
            n_i = len(rr)
        summary[herb] = {"found": True, "para": i0, "n_content": n_c, "n_identify": n_i,
                         "has_content_section": "含量测定" in secs, "body_paras": len(body),
                         "in_pian_para": in_pian_para, "in_pian_pos": summ_ip}
        if not mode_all:
            print("  ok %-4s 段%-6d 含量%d 鉴别%d" % (herb, i0, n_c, n_i))
    with open(OUT_DIR / "chp2020_markers.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("—— 合计 %d 条（含量测定 %d · 鉴别 %d）-> %s"
          % (len(rows), sum(1 for r in rows if r["section"] == "含量测定"),
             sum(1 for r in rows if r["section"] == "鉴别"), OUT_DIR))
    for r in rows:
        if r["herb"] == "甘草" and r["section"] == "含量测定":
            print("   [示例] %s：%s %s %s%%（ref=%s）"
                  % (r["herb"], r["name_raw"], r["relation"], r["value"], r["ref"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

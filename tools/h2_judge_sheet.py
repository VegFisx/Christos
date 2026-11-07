# -*- coding: utf-8 -*-
r"""H2 · 判定表（可复现的筛选信号 + 逐条证据）。

对每一条抽中的记录：
  1. 把库里的「组成」拆成药材名（去剂量 / 去炮制前缀 / 去注记）；
  2. 在**公开来源**的标题+摘要（以及抓到的页面节选）里找这些药材名，算**覆盖率**；
  3. 输出一张判定表：覆盖率 + 命中的来源条目（URL + 片段）。

覆盖率只是**筛选信号**（自动算、口径写死），最终三档由逐条阅读定：
  命中 / 部分命中 / 查无  —— 判定结果写在 data\h2_verdicts.json。

用法：``python tools\h2_judge_sheet.py --start 1 --limit 25``
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
NET = STAGE / "reports" / "_h2_net"
SAMPLE = STAGE / "data" / "h2_sample.json"

# 炮制/修治前缀（去掉后再比）—— 只用于**匹配**，不改数据
PREP = ("炙", "炒", "制", "焦", "煅", "煨", "醋", "酒", "盐", "蜜", "姜", "清", "麸",
        "土", "米", "生", "熟", "炮", "焙", "蒸", "煮", "鲜", "干", "酥",
        "炒炭", "炭", "霜", "曲", "去皮", "去心")
# 剂量单位（中文数字 + 单位）—— 拆名字时必须去掉，否则「乌药1两」会拆成「乌药两」
UNIT = ("钱五分", "钱", "两", "分", "厘", "斤", "升", "合", "勺", "枚", "片", "只",
        "条", "粒", "个", "块", "寸", "尺", "把", "握", "克", "毫克", "毫升", "茎",
        "朵", "对", "双", "具", "团", "撮", "字")
JUNK = "。．.、；;：:，,（）()【】[]《》<>\"'“”‘’　 \t\r\n"
LENIENT = ("赤", "白", "生", "熟", "鲜", "干", "炙", "炒", "制", "酒", "醋", "盐",
           "蜜", "姜", "焦", "煅", "麸", "土", "米", "清", "炮", "酥")


def ingredients(peifang: str) -> list:
    """库里的组成 → 药材名列表（去剂量 / 炮制前缀 / 注记）。"""
    out = []
    for tok in re.split(r"[，,、；;]", str(peifang or "")):
        t = re.sub(r"[\d.]+", "", tok)
        t = re.sub(r"[（(][^）)]*[）)]", "", t)
        for u in UNIT:                                  # 去中文单位（长的先）
            t = t.replace(u, "")
        t = t.strip(JUNK)
        t = re.sub(r"(各等分|等分|少许|适量|为末|研末|各半|等份)$", "", t).strip(JUNK)
        for p in PREP:
            if t.startswith(p) and len(t) > len(p) + 1:
                t = t[len(p):]
        t = t.strip(JUNK)
        if 1 <= len(t) <= 6 and not t.isdigit():
            out.append(t)
    return out


def coverage(names: list, blob: str) -> tuple:
    """(命中数, 总数, 命中的名字)。

    两级匹配：**严格**（名字原样出现）优先；不中再试**宽松**
    （去掉 赤/白/生/熟/炙… 这类同物不同炮制的字，且剩下 ≥2 字 ——
    所以「白术」不会宽松匹配成「苍术」，但「赤茯苓」能匹配上「茯苓」）。
    """
    hit = []
    for n in names:
        if not n:
            continue
        if n in blob:
            hit.append(n)
            continue
        for p in LENIENT:
            if n.startswith(p) and len(n) - len(p) >= 2 and n[len(p):] in blob:
                hit.append(n + "~")
                break
    return len(hit), len(names), hit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--min-cov", type=float, default=0.6,
                    help="覆盖率 >= 这个数 → 建议「命中」")
    ap.add_argument("--json-out", default=str(STAGE / "data" / "h2_screen.json"))
    ap.add_argument("--net", default=str(NET), help="证据目录（第二批用 _h2_net2）")
    ap.add_argument("--sample", default=str(SAMPLE))
    ap.add_argument("--compact", action="store_true",
                    help="紧凑版：每条 5 行（给人逐条阅读定档用）")
    a = ap.parse_args()

    net = Path(a.net)
    items = json.loads(Path(a.sample).read_text(encoding="utf-8"))["items"]
    sheet = []
    for x in items:
        if not (a.start <= x["序号"] < a.start + a.limit):
            continue
        names = ingredients(x["组成"])
        srcs = []
        for fp in sorted(net.glob("%03d_*.json" % x["序号"])):
            d = json.loads(fp.read_text(encoding="utf-8"))
            if "page" in fp.name:
                pg = d.get("page") or {}
                if pg:
                    srcs.append({"site": pg.get("site"), "url": pg.get("url"),
                                 "text": pg.get("excerpt") or ""})
            else:
                for r in (d.get("results") or []):
                    blob = (r.get("title") or "") + " " + (r.get("snippet") or "")
                    if x["方名"] in blob:
                        srcs.append({"site": d.get("engine_used"), "url": r.get("url"),
                                     "text": blob})
        best, best_src = 0, None
        for s in srcs:
            c, _n, _h = coverage(names, s["text"])
            if c > best:
                best, best_src = c, s
        top = sorted(srcs, key=lambda s: -coverage(names, s["text"])[0])[:3]
        cov = round(best / max(1, len(names)), 3)
        rec = {"序号": x["序号"], "方名": x["方名"], "出处": x["出处"],
               "库里组成": x["组成"], "药材数": len(names), "药材": names,
               "最佳命中": best, "覆盖率": cov,
               "最佳来源": (best_src or {}).get("url"), "候选来源数": len(srcs),
               "建议": ("命中" if cov >= a.min_cov else
                        "部分命中" if best > 0 else "查无")}
        sheet.append(rec)
        if a.compact:
            print("─" * 96)
            print("#%03d %s ｜ %s" % (rec["序号"], rec["方名"], rec["出处"]))
            print("  库：%s" % re.sub(r"\s+", "", rec["库里组成"])[:78])
            print("  材(%d)：%s ｜ 覆盖 %.2f（%s）"
                  % (rec["药材数"], "、".join(rec["药材"])[:64], rec["覆盖率"], rec["建议"]))
            for s in top[:2]:
                c, _n, h = coverage(names, s["text"])
                print("  [%s] %d/%d %s" % (s["site"], c, len(names), (s["url"] or "")[:64]))
                print("     %s" % re.sub(r"\s+", " ", s["text"])[:132])
            continue
        print("=" * 100)
        print("#%03d %s ｜ 出处 %s" % (rec["序号"], rec["方名"], rec["出处"]))
        print("  库里组成：%s" % rec["库里组成"][:110])
        print("  拆出药材（%d）：%s" % (len(names), "、".join(names)))
        print("  覆盖率 %.2f（建议 %s）｜ 候选来源 %d 条"
              % (rec["覆盖率"], rec["建议"], len(srcs)))
        for s in top:
            c, _n, _h = coverage(names, s["text"])
            print("     [%s] 命中 %d/%d ｜ %s" % (s["site"], c, len(names), (s["url"] or "")[:70]))
            print("        %s" % re.sub(r"\s+", " ", s["text"])[:150])
    Path(a.json_out).write_text(json.dumps(sheet, ensure_ascii=False, indent=1),
                                encoding="utf-8")
    print()
    print("  本批 %d 条，判定表 -> %s" % (len(sheet), a.json_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

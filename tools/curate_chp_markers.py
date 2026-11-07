# -*- coding: utf-8 -*-
r"""把 build_chp_markers.py 的候选行校对本：OCR 定名 / 空名补全 / 药材-饮片分段 / 去重。

用法: python tools\curate_chp_markers.py
输出: reports\chp_markers\chp2020_curated.csv（每行带 para 出处，可回溯）
规则全部写明在代码里（依据=该行原文上下文，见 chp2020_markers.jsonl）。
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

D = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\chp_markers")

GEN_FIX = [("皂昔", "皂苷"), ("Rgi", "Rg1"), ("Rgl", "Rg1"), ("Rbj", "Rb1"), ("Rb]", "Rb1"),
           ("木犀草 ^", "木犀草苷"), ("木犀草^", "木犀草苷"), ("木犀草#", "木犀草苷"),
           ("甘草#", "甘草苷"), ("甘草^", "甘草苷"), ("黄苗甲#", "黄芪甲苷"),
           ("芍药#", "芍药苷"), ("芍药^", "芍药苷"), ("芍药昔", "芍药苷"),
           ("黄苓昔", "黄芩苷"), ("黄苓^", "黄芩苷"),
           ("表小槩碱", "表小檗碱"), ("表小案碱", "表小檗碱"),
           ("小槩碱", "小檗碱"), ("小棄碱", "小檗碱"), ("小案碱", "小檗碱"), ("小樂碱", "小檗碱"),
           ("橙皮#", "橙皮苷"), ("橙皮昔", "橙皮苷"),
           ("薄荷W", "薄荷脑"), ("桔梗皂昔D", "桔梗皂苷D"),
           ("丹参酮nA", "丹参酮ⅡA"), ("丹参酮口A", "丹参酮ⅡA"), ("丹参酮Ha", "丹参酮ⅡA"),
           ("枸椽酸", "枸橼酸"), ("蔥", "蒽"), ("醍", "醌"), ("醞", "醌"), ("醵", "醚")]

GEN_FIX += [("-二咖啡酰基奎宁酸", "3,5-O-二咖啡酰基奎宁酸")]
GEN_FIX += [("昔", "苷")]        # 通用 OCR：金丝桃昔→金丝桃苷、柚皮昔→柚皮苷…（放最后，不覆盖专名规则）
GEN_FIX += [("毛蕊花糖<", "毛蕊花糖苷"), ("红景天首", "红景天苷"), ("苦杏仁^", "苦杏仁苷"),
            ("橙皮<", "橙皮苷"), ("紫丁香#", "紫丁香苷"), ("柳穿鱼叶^", "柳穿鱼叶苷"),
            ("皂甘", "皂苷")]
GEN_FIX += [
    ("特女贞#", "特女贞苷"), ("松果菊#", "松果菊苷"), ("毛蕊花糖^", "毛蕊花糖苷"),
    ("柚皮#", "柚皮苷"), ("栀子^", "栀子苷"), ("梔子^", "栀子苷"),
    ("黄蔑甲^", "黄芪甲苷"), ("黄蔑", "黄芪"), ("龙胆苦#", "龙胆苦苷"),
    ("竹节参皂#", "竹节参皂苷"), ("积雪草甘", "积雪草苷"), ("水晶兰#", "水晶兰苷"),
    ("腺^", "腺苷"), ("乙酰哈巴<", "乙酰哈巴苷"), ("巴豆#", "巴豆苷"),
    ("金丝桃杳", "金丝桃苷"), ("紫莞酮", "紫菀酮"), ("紫苑酮", "紫菀酮"),
    ("斑螯素", "斑蝥素"), ("远志", "远志"),
    ("芨着碱", "莨菪碱"), ("苣着碱", "莨菪碱"), ("东芨蒼内酯", "东莨菪内酯"),
    ("东芨着内酯", "东莨菪内酯"), ("木香炷内酯", "木香烃内酯"), ("木香姪内酯", "木香烃内酯"),
    ("乌药醜内酯", "乌药醚内酯"), ("蜕皮螢酮", "蜕皮甾酮"), ("核油精", "桉油精"),
    ("桜油精", "桉油精"), ("麦角當醇", "麦角甾醇"), ("麦角街醇", "麦角甾醇"),
    ("异嗪皮噬", "异嗪皮啶"), ("异嗪皮呢", "异嗪皮啶"), ("异嗪皮啜", "异嗪皮啶"),
    ("朝蕾定C", "朝藿定C"), ("次野莺尾黄素", "次野鸢尾黄素"),
    ("概皮素", "槲皮素"), ("榊皮素", "槲皮素"), ("撕皮苷", "槲皮苷"), ("糊皮苷", "槲皮苷"),
    ("芦丁槐花", "芦丁"), ("芦丁槐米", "芦丁"), ("-亚麻酸", "亚麻酸"),
    ("苣若内酯", "莨菪内酯"), ("撇皮苷", "槲皮苷"), ("撤皮苷", "槲皮苷"), ("鄙皮素", "槲皮素"),
    ("牛莠", "牛蒡"), ("0-蜕皮甾酮", "蜕皮甾酮"), ("由蜕皮甾酮", "蜕皮甾酮"),
    ("Rg].", "Rg1、"), ("Rg]", "Rg1"), ("Rb].", "Rb1、"),
    ("杯苑螢酮", "杯苋甾酮"), ("薯領皂苷元", "薯蓣皂苷元"), ("殺皂苷", "蓣皂苷"),
    ("殖皂苷", "蓣皂苷"), ("山梔", "山栀"), ("櫛皮素", "槲皮素"),
    ("柚皮苜14)", "柚皮苷"), ("芦荟苷库拉索芦荟", "芦荟苷"), ("芦荟苷好望角芦荟", "芦荟苷"),
    ("2.3.5.4'-四羟基二苯乙烯2O-B", "四羟基二苯乙烯"), ("苦玄参#", "苦玄参苷"),
    ("山柰", "山奈"), ("β-蜕皮甾酮", "蜕皮甾酮"),
    ("2.3.5.4′-四羟基二苯乙烯-2-O-β-D", "四羟基二苯乙烯"),
    ("3.6′-二芥子酰基蔗糖", "二芥子酰基蔗糖"),
]
JUNK = {"4）", "技）", "）", "H1o OQ", "", "4)", "技)", ")", "4", "技", "H1oOQ"}
DOSAGE = ("丸", "散", "片", "胶囊", "颗粒", "软膏", "膏", "液", "浆", "露", "油",
          "气雾剂", "喷雾剂", "栓", "酊", "酒", "茶", "锭", "贴", "膜", "丹",
          "滴丸", "合剂", "洗剂", "搽剂", "糖浆")


def entry_type(herb: str) -> str:
    if herb.endswith(DOSAGE):
        return "制剂"
    if herb.endswith(("浸膏", "流浸膏", "干浸膏", "提取物")):
        return "提取物"
    return "药材"
EMPTY_FILL = {
    ("当归", 0.05): ("阿魏酸", "compound"),
    ("川芎", 0.1): ("阿魏酸", "compound"),
    ("丹参", 3.0): ("丹酚酸B", "compound"),
    ("枸杞", 1.8): ("枸杞多糖（以葡萄糖计）", "aggregate_total"),
    ("山楂", 5.0): ("有机酸（以枸橼酸计）", "aggregate_total"),
    ("山楂", 4.0): ("有机酸（以枸橼酸计）", "aggregate_total"),
    ("黄连", 4.5): ("小檗碱（雅连）", "compound"),
    ("陈皮", 0.42): ("川陈皮素与橘皮素的总量", "aggregate_total"),
    ("陈皮", 0.4): ("川陈皮素与橘皮素的总量（广陈皮）", "aggregate_total"),
    ("大黄", 1.5): ("总蒽醌（5 项总量计）", "aggregate_total"),
    ("大黄", 0.2): ("游离蒽醌（5 项总量计）", "aggregate_total"),
    ("大黄", 0.35): ("游离蒽醌（饮片）", "aggregate_total"),
    ("大黄", 0.5): ("游离蒽醌（饮片）", "aggregate_total"),
    ("大黄", 0.9): ("总蒽醌（饮片）", "aggregate_total"),
    ("金银花", 3.8): ("酚酸类（3 项总量计）", "aggregate_total"),
    ("菊花", 0.7): ("3,5-O-二咖啡酰基奎宁酸", "compound"),
    ("生姜", 0.04): ("8-姜酚与10-姜酚总量", "aggregate_total"),
}


def fix_name(s: str) -> str:
    for a, b in GEN_FIX:
        s = s.replace(a, b)
    s = re.sub(r"^(?:[SRM]\)|[A-Za-z]{1,2}\))", "", s)   # 去 S)- / R)- 之类前缀
    s = re.sub(r"[（(][^）)]*$", "", s)                   # 去掉没收全的括号残渣（含分子式）
    return re.sub(r"\s+", "", s)


def _clean_total_item(x: str) -> str:
    """总量句里的单个成分名：迭代剥括号（混用全/半角），去前导式残渣。"""
    for _ in range(2):
        x = re.sub(r"[（(][^）)]{0,60}[）)]", "", x)
    # 前导式残渣（含字母/右括号的碎公式，如 "20H30O5)、"；不误伤 "6-姜辣素" / "14-去氧…"）
    x = re.sub(r"^(?:\d*[A-Za-z\)\]]+[0-9A-Za-z\)\]]*)[、,，]?", "", x)
    return x.strip(" 　+、,，。；;:：\"'")


def rebuild_total_name(ctx: str) -> str:
    """从"含A、B、C和D的总量，不得少于X"式上下文重建干净成分清单。"""
    seg = str(ctx or "").split("不得")[0]
    for kw in ("含", "以"):
        i = seg.rfind(kw)
        if i >= 0:
            seg = seg[i + 1:]
            break
    seg = seg.split("的总量")[0]
    out = []
    for part in re.split(r"[、，,和与及]", seg):
        p = _clean_total_item(part)
        if len(p) >= 2 and re.search(r"[\u4e00-\u9fff]", p) and p not in out:
            out.append(p)
    return "、".join(out[:8])


def main() -> int:
    src = next(iter(sorted(D.glob("chp*_markers.jsonl"))), None)
    if src is None:
        print("目录里没有 chp*_markers.jsonl：%s" % D)
        return 2
    stem = src.stem.replace("_markers", "")
    rows = [json.loads(l) for l in open(src, encoding="utf-8")]
    summ = json.loads((D / "summary.json").read_text(encoding="utf-8"))
    out, seen = [], set()
    n_fix = n_fill = 0
    n_sec_skip = 0
    for r in rows:
        if r["section"] not in ("含量测定", "鉴别"):
            continue
        is_id = r["section"] == "鉴别"
        name, kind = fix_name(r["name_raw"]), r["kind"]
        # ★ 第七十二轮：小节名（〔规格〕/【性状】这类）不是标记物——整行丢弃并计数
        if re.match(r"^[〔【（(][^〕】）)]{0,10}[〕】）)]$", name):
            n_sec_skip += 1
            continue
        if is_id:
            kind = "identify"                    # Tier-1：鉴别对照品（排在含量测定之后）
        if name in JUNK or name != r["name_raw"]:
            n_fix += 1
        if name in JUNK and not is_id:
            got = EMPTY_FILL.get((r["herb"], r["value"]))
            if got:
                name, kind = got
                n_fill += 1
        # ★ 第七十三轮：总量句重建（多成分"…的总量"——穿心莲式），提升可连库性
        if ("总量" in (name or "")) or ("的总量" in (r.get("context") or "")):
            fixed = rebuild_total_name(r.get("context") or "")
            if fixed:
                name, kind = fixed + "（总量）", "aggregate_total"
        ip = (summ.get(r["herb"]) or {}).get("in_pian_pos", -1)
        part = r.get("part") or ("饮片" if (ip is not None and ip >= 0
                                            and r.get("pos", -1) > ip) else "药材")
        key = (r["herb"], part, name, r["relation"], r["value"])
        if key in seen:
            continue
        seen.add(key)
        need = bool(re.search(r"[^\u4e00-\u9fffA-Za-z0-9（）()、,，\-\.\s]", name)) or name in JUNK
        out.append({"herb": r["herb"], "part": part, "name": name, "relation": r["relation"],
                    "value": (r["value"] if r["value"] is not None else ""),
                    "unit": r["unit"], "basis": r["ref"], "kind": kind,
                    "formula_raw": r.get("formula", ""), "para": r["para"],
                    "review": ("needs_review" if need else ("auto_fixed" if name != r["name_raw"] else "ok")),
                    "entry_type": r.get("entry_type") or entry_type(r["herb"]),
                    "url": r.get("url", "")})
    out_csv = D / (stem + "_curated.csv")
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    nr = sum(1 for o in out if o["review"] == "needs_review")
    print("校对本：%d 行（改名 %d · 空名补全 %d · 待人工复核 %d · 弃小节名 %d）-> %s"
          % (len(out), n_fix, n_fill, nr, n_sec_skip, out_csv.name))
    for o in out:
        if o["review"] != "ok":
            print("   [%s] %-4s %-6s %-26s %s%%" % (o["review"], o["herb"], o["part"],
                                                    o["name"][:26], o["value"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
r"""把药典校对本对到 tcm.db（只读）。两条路线：

* 路线 A：中文名 → 英文名（EN 表，30 味试点规模）→ DB 精确/模糊匹配；
* 路线 B：**分子式**匹配（抽取时括号里的 C…H…O…；在该药材自己的化合物集合内查，
  公式唯一命中才算，多异构体记 ambiguous 不硬指）。

输出: reports\chp_markers\chp2020_linked.csv（带 link_via 列）+ 未映射热榜（Top 20）。
"""
from __future__ import annotations

import collections
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tcm_ro import open_db          # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

D = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\chp_markers")

EN = {"甘草苷": "Liquiritin", "甘草酸": "Glycyrrhizic", "黄芪甲苷": "Astragaloside",
      "人参皂苷Rg1": "Ginsenoside rg1", "人参皂苷Re": "Ginsenoside re",
      "人参皂苷Rb1": "Ginsenoside rb1",
      "阿魏酸": "Ferulic", "芍药苷": "Paeoniflorin", "柴胡皂苷a": "Saikosaponin",
      "柴胡皂苷d": "Saikosaponin", "黄芩苷": "Baicalin", "小檗碱": "Berberine",
      "表小檗碱": "Epiberberine", "黄连碱": "Coptisine", "巴马汀": "Palmatine",
      "绿原酸": "Chlorogenic", "木犀草苷": "Luteolin", "橙皮苷": "Hesperidin",
      "川陈皮素": "Nobiletin", "橘皮素": "Tangeretin", "辛弗林": "Synephrine",
      "薄荷脑": "Menthol", "桔梗皂苷D": "Platycodin", "盐酸麻黄碱": "Ephedrine",
      "盐酸伪麻黄碱": "Pseudoephedrine", "桂皮醛": "Cinnamaldehyde",
      "6-姜辣素": "Gingerol", "8-姜酚": "Gingerol", "10-姜酚": "Gingerol",
      "甜菜碱": "Betaine", "五味子醇甲": "Schisandrin", "葛根素": "Puerarin",
      "丹皮酚": "Paeonol", "丹酚酸B": "Salvianolic", "丹参酮ⅡA": "Tanshinone",
      "隐丹参酮": "Cryptotanshinone", "丹参酮I": "Tanshinone",
      "大黄素": "Emodin", "大黄酸": "Rhein", "芦荟大黄素": "Aloeemodin",
      "大黄酚": "Chrysophanol", "大黄素甲醚": "Physcion", "枸橼酸": "Citric",
      "3,5-O-二咖啡酰基奎宁酸": "caffeoyl"}
EN.update({
    "没食子酸": "Gallic", "苦参碱": "Matrine", "氧化苦参碱": "Oxymatrine",
    "水苏碱": "Stachydrine", "盐酸水苏碱": "Stachydrine", "迷迭香酸": "Rosmarinic",
    "茴香脑": "Anethole", "反式茴香脑": "Anethole", "胆红素": "Bilirubin",
    "金丝桃苷": "Hyperoside", "蒙花苷": "Linarin", "柚皮苷": "Naringin",
    "獐牙菜苦苷": "Swertiamarin", "芒果苷": "Mangiferin", "苦杏仁苷": "Amygdalin",
    "厚朴酚": "Magnolol", "和厚朴酚": "Honokiol", "胆酸": "Cholic",
    "靛玉红": "Indirubin", "百秋李醇": "Patchoulol", "齐墩果酸": "Oleanolic",
    "熊果酸": "Ursolic", "山奈酚": "Kaempferol", "木通苯乙醇苷B": "Calceolarioside",
    "毛蕊花糖苷": "Verbascoside", "龙脑": "Borneol", "仙茅苷": "Curculigoside",
    "野黄芩苷": "Scutellarin", "岩白菜素": "Bergenin", "延胡索乙素": "Tetrahydropalmatine",
    "盐酸巴马汀": "Palmatine", "粉防己碱": "Tetrandrine", "防己诺林碱": "Fangchinoline",
    "L-羟脯氨酸": "Hydroxyproline", "羟脯氨酸": "Hydroxyproline",
    "告依春": "Goitrin", "知母皂苷": "Timosaponin", "表儿茶素": "Epicatechin",
    "胡椒碱": "Piperine", "络石苷": "Tracheloside", "盐酸益母草碱": "Leonurine",
    "益母草碱": "Leonurine", "紫丁香苷": "Syringin", "菊苣酸": "Chicoric",
    "槟榔碱": "Arecoline", "蝙蝠葛碱": "Dauricine", "橙皮苷": "Hesperidin"})
EN.update({"毛蕊花糖苷": "Acteoside", "丁香酚": "Eugenol", "三白草酮": "Sauchinone",
           "大蒜素": "Allicin", "落新妇苷": "Astilbin", "野漆树苷": "Rhoifolin",
           "柳穿鱼叶苷": "Pectolinarin", "红景天苷": "Salidroside",
           "大豆苷": "Daidzin", "染料木苷": "Genistin",
           "土荆皮乙酸": "Pseudolaric acid b"})
EN.update({"龙胆苦苷": "Gentiopicroside", "连翘苷": "Forsythin", "连翘酯苷A": "Forsythoside",
           "羟基红花黄色素A": "Hydroxysafflor", "芍药内酯苷": "Albiflorin",
           "秦皮甲素": "Esculin", "秦皮乙素": "Esculetin", "五味子酯甲": "Schisantherin",
           "甘草次酸": "Glycyrrhetinic", "穿心莲内酯": "Andrographolide",
           "梓醇": "Catalpol", "松果菊苷": "Echinacoside", "特女贞苷": "Specnuezhenide"})
EN.update({
    "百秋李醇": "Patchouli", "三七皂苷R1": "Notoginsenoside r1", "射干苷": "Tectoridin",
    "马钱子碱": "Strychnine", "东莨菪碱": "Scopolamine", "莨菪碱": "Hyoscyamine",
    "右旋龙脑": "Borneol", "无水芦丁": "Rutin", "木香烃内酯": "Costunolide",
    "去氢木香内酯": "Dehydrocostuslactone", "京尼平苷酸": "Geniposidic",
    "大车前苷": "Plantamajoside", "蜕皮甾酮": "Ecdysterone", "异阿魏酸": "Isoferulic",
    "乌药醚内酯": "Linderane", "去甲异波尔定": "Norisoboldine", "巴豆苷": "Crotonoside",
    "花旗松素": "Taxifolin", "甘松新酮": "Nardosinone", "大戟二烯醇": "Euphadienol",
    "桉油精": "Eucalyptol", "石吊兰素": "Lysionotin", "白头翁皂苷B4": "Anemoside",
    "欧前胡素": "Imperatorin", "白屈菜红碱": "Chelerythrine", "黄柏酮": "Obacunone",
    "腺苷": "Adenosine", "冬凌草甲素": "Oridonin", "哈巴苷": "Harpagide",
    "哈巴俄苷": "Harpagoside", "当药苷": "Sweroside", "去氢二异丁香酚": "Dehydrodiisoeugenol",
    "人参皂苷Ro": "Ginsenoside ro", "竹节参皂苷": "Chikusetsusaponin",
    "东莨菪内酯": "Scopoletin", "西贝母碱": "Sipeimine", "橙黄决明素": "Aurantio",
    "二芥子酰基蔗糖": "disinapoyl", "苍术素": "Atractylodin", "芦荟苷": "Barbaloin",
    "松脂醇": "Pinoresinol", "朝藿定C": "Epimedin", "氯化两面针碱": "Nitidine",
    "柠檬苦素": "Limonin", "四羟基二苯乙烯": "stilbene", "羌活醇": "Notopterol",
    "异鼠李素": "Isorhamnetin", "沉香四醇": "Agarotetrol", "补骨脂素": "Psoralen",
    "异补骨脂素": "Angelicin", "甘氨酸": "Glycine", "丙氨酸": "Alanine",
    "脯氨酸": "Proline", "靛蓝": "Indigo", "紫堇灵": "Corynoline", "虎杖苷": "Polydatin",
    "罗汉果皂": "Mogroside", "异嗪皮啶": "Isofraxidin", "原儿茶酸": "Protocatechuic",
    "细辛脂素": "Asarinin", "胡薄荷酮": "Pulegone", "大叶茜草素": "Rubimaillin",
    "山姜素": "Alpinetin", "乔松素": "Pinocembrin", "小豆蔻明": "Cardamonin",
    "滨蒿内酯": "Scoparone", "胡黄连苷": "Picroside", "新橙皮苷": "Neohesperidin",
    "栀子苷": "Geniposide", "乙酸龙脑酯": "Bornyl acetate", "油酸": "Oleic",
    "麝香草酚": "Thymol", "香荆芥酚": "Carvacrol", "重楼皂苷": "Polyphyllin",
    "山栀苷甲酯": "Shanzhiside", "姜黄素": "Curcumin", "白花前胡": "Praeruptorin",
    "马钱苷酸": "Loganic", "甲基莲心碱": "Neferine", "荷叶碱": "Nuciferine",
    "原阿片碱": "Protopine", "积雪草苷": "Asiaticoside", "洋艾素": "Absinthin",
    "次野鸢尾黄素": "Irisflorentin", "七叶皂苷A": "Escin", "蛇床子素": "Osthole",
    "麦角甾醇": "Ergosterol", "牛磺猪去氧胆酸": "Taurohyodeoxycholic",
    "商陆皂苷甲": "Esculentoside", "川续断皂苷VI": "Asperosaponin", "斑蝥素": "Cantharidin",
    "款冬酮": "Tussilagone", "贝母素乙": "Peiminine", "杜鹃素": "Farrerol",
    "酸枣仁皂苷": "Jujuboside", "奇壬醇": "Kirenol", "辣椒素": "Capsaicin",
    "二氢辣椒素": "Dihydrocapsaicin", "甘油三油酸酯": "Triolein", "蟾毒灵": "Bufalin",
    "华蟾酥毒基": "Cinobufagin", "脂蟾毒配基": "Resibufogenin", "麝香酮": "Muscone",
    "牡荆素": "Vitexin", "环维黄杨星D": "Cyclovirobuxine", "对羟基苯乙酮": "hydroxyacetophenone",
    "水杨酸甲酯": "Methyl salicylate", "盐酸苯海拉明": "Diphenhydramine",
    "刺五加苷E": "Eleutheroside e", "毛蕊异黄酮葡萄糖": "Calycosin"})
EN.update({"异土木香内酯": "Isoalantolactone", "土木香内酯": "Alantolactone",
           "柳穿鱼黄素": "Pectolinarigenin", "川楝素": "Toosendanin",
           "夏佛塔苷": "Schaftoside", "鬼臼毒素": "Podophyllotoxin",
           "瓜氨酸": "Citrulline", "亮氨酸": "Leucine", "精氨酸": "Arginine",
           "赖氨酸": "Lysine", "谷氨酸": "Glutamic", "咖啡酸": "Caffeic",
           "异贝壳杉烯酸": "kaurenoic", "牛蒡苷": "Arctiin", "水飞蓟宾": "Silybin",
           "盐酸小檗碱": "Berberine", "石斛碱": "Dendrobine", "瓜子金皂苷": "Senegin",
           "地肤子皂苷": "Momordin", "亚麻酸": "Linolenic", "苦番红花素": "Picrocrocin",
           "苯甲酰乌头原碱": "Benzoylaconine"})
EN.update({"木犀草素": "Luteolin", "胆固醇": "Cholesterol", "青蒿素": "Artemisinin",
           "相思子碱": "Abrine", "儿茶素": "Catechin", "异钩藤碱": "Isorhynchophylline",
           "二氢欧山芹醇当归酸酯": "Columbianadin", "通关藤苷": "Tenacissoside",
           "伪原薯蓣皂苷": "Pseudoprotodioscin", "薯蓣皂苷元": "Diosgenin",
           "原儿茶醛": "Protocatechualdehyde", "杨梅苷": "Myricitrin", "古伦宾": "Columbin",
           "苦玄参苷": "Picfeltarraenin", "去氧胆酸": "Deoxycholic",
           "杯苋甾酮": "Cyasterone", "槲皮苷": "Quercetin-3-rhamnoside"})
EN["芦荟苷"] = "Aloin"
EN.update({"牻牛儿酮": "Germacrone", "α-蒎烯": "pinene", "藁本内酯": "Ligustilide",
           "槐角苷": "Sophoricoside", "紫菀酮": "Shionone", "高良姜素": "Galangin",
           "莫诺苷": "Morroniside", "马钱苷": "Loganin", "穗花杉双黄酮": "Amentoflavone",
           "芳樟醇": "Linalool", "甘氨胆酸": "Glycocholic", "猪去氧胆酸": "Hyodeoxycholic",
           "木蝴蝶苷B": "Oroxin", "松脂醇二葡萄糖苷": "Pinoresinol", "莪术二酮": "Curdione",
           "宝藿苷I": "Baohuoside", "凤仙萜四醇皂苷": "Hosenkoside",
           "灰毡毛忍冬皂苷": "Macranthoside", "连翘酯苷B": "Forsythoside",
           "β-丁香烯": "Caryophyllene", "呋喃二烯": "Furanodiene",
           "蟛蜞菊内酯": "Wedelolactone", "女贞苷": "Ligustroflavone",
           "耐斯糖": "Nystose", "牡荆苷": "Vitexin"})

NOISE_KEYS = ("每丸", "每ml", "每lg", "每1", "规格", "总氮", "脂肪油", "水分", "灰分",
              "糖衣片", "薄膜衣片", "分别")
MINERALS = {"铁", "碘", "碳酸钙", "硫酸钠", "硫化汞", "氟化钙", "氧化锌", "钙", "镁", "锌",
            "氧化汞", "氯化亚汞", "氯化钠", "氮量", "钙量"}


def is_noise(name: str) -> bool:
    if not name or len(name) < 2:
        return True
    if name in MINERALS:
        return True
    if any(k in name for k in NOISE_KEYS):
        return True
    return bool(re.fullmatch(r"[）)、）\]（(《》\s%0-9.]+", name))


def base_names(s: str):
    s = re.sub(r"（[^）]*）|\([^)]*\)", "", s)
    s = s.replace("的总量", "").replace("总量", "").replace("（饮片）", "")
    parts = re.split(r"[、，和与及\\/]", s)
    out = []
    for p in parts:
        p = re.sub(r"\s+", "", p)
        if not p:
            continue
        p = re.sub(r"^(含|游离|总)", "", p).strip()
        if p and p not in out:
            out.append(p)
    return out


def norm_formula(f: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", f or "")


def main() -> int:
    csrc = next(iter(sorted(D.glob("chp*_curated.csv"))), None)
    if csrc is None:
        print("目录里没有 chp*_curated.csv：%s（先跑 curate）" % D)
        return 2
    stem = csrc.stem.replace("_curated", "")
    rows = list(csv.DictReader(open(csrc, encoding="utf-8-sig")))
    with open_db() as conn:
        markers = {}
        for herb_cn, iid in conn.execute(
                "SELECT h.name_cn, hc.ingredient_id FROM herb_compound hc "
                "JOIN herbs h ON hc.herb_id = h.herb_id WHERE hc.match_level='marker'"):
            markers.setdefault(herb_cn, set()).add(iid)
        fmap = {}
        for herb_cn, formula, iid in conn.execute(
                "SELECT h.name_cn, c.formula, c.ingredient_id FROM herb_compound hc "
                "JOIN compounds c ON hc.ingredient_id = c.ingredient_id "
                "JOIN herbs h ON hc.herb_id = h.herb_id "
                "WHERE c.formula IS NOT NULL AND c.formula != ''"):
            f = norm_formula(formula)
            if f:
                fmap.setdefault(herb_cn, {}).setdefault(f, []).append(iid)
        unmatched = collections.Counter()
        out, n_en, n_fml, n_amb = [], 0, 0, 0
        for r in rows:
            if r["kind"] == "aggregate":
                # 纯聚合指标（挥发油/多糖…）不连库；aggregate_total（多成分总量）
                # 的成分清单是可连的——第七十三轮放开。★
                out.append({**r, "db_hits": "", "link_via": "aggregate(不连库)"})
                continue
            if is_noise(r["name"]):
                out.append({**r, "db_hits": "", "link_via": "skip-noise"})
                continue
            hits, via = [], ""
            for b in base_names(r["name"]):
                en = None
                # 前缀容忍（最多裁 4 个尾字符）：知母皂苷Bn -> 知母皂苷；
                # 不能无限裁——防止长糖苷名塌缩到苷元名造成误配
                for cut in range(len(b), max(1, len(b) - 4), -1):
                    en = EN.get(b[:cut])
                    if en:
                        break
                if en:
                    got = conn.execute(
                        "SELECT ingredient_id, name_en FROM compounds "
                        "WHERE name_en = ? COLLATE NOCASE AND smiles IS NOT NULL LIMIT 3",
                        (en,)).fetchall()
                    if not got:
                        got = conn.execute(
                            "SELECT ingredient_id, name_en FROM compounds "
                            "WHERE name_en LIKE ? AND smiles IS NOT NULL LIMIT 3",
                            ("%" + en + "%",)).fetchall()
                    if not got and en == "caffeoyl":
                        got = conn.execute(
                            "SELECT ingredient_id, name_en FROM compounds "
                            "WHERE name_en LIKE '%quinic%' AND smiles IS NOT NULL LIMIT 3").fetchall()
                    if got:
                        via = "en"
                    hits += ["%s(%s)" % (n, i) for i, n in got]
            if not hits:
                f = norm_formula(r.get("formula_raw", ""))
                if len(f) >= 6:
                    ids = (fmap.get(r["herb"]) or {}).get(f) or []
                    ids = list(dict.fromkeys(ids))
                    if len(ids) == 1:
                        hits = ["%s(%s)" % (f, ids[0])]
                        via = "formula"
                    elif len(ids) > 1:
                        pick = [i for i in ids if i in (markers.get(r["herb"]) or set())]
                        if len(pick) == 1:          # 二次判据：是该药材的 marker 才采用
                            hits = ["%s(%s,marker)" % (f, pick[0])]
                            via = "formula+marker"
                        else:
                            via = "ambiguous(%d)" % len(ids)
                            n_amb += 1
            if via == "en":
                n_en += 1
            elif via == "formula":
                n_fml += 1
            if not hits:
                unmatched[(r["herb"], r["name"])] += 1
            out.append({**r, "db_hits": " | ".join(hits[:4]), "link_via": via or "none"})
    with open(D / (stem + "_linked.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    hit = sum(1 for o in out if o["db_hits"])
    print("连接：%d 行 · 命中 %d（%.0f%%）· en %d · formula %d · 多义 %d"
          % (len(out), hit, 100.0 * hit / max(1, len(out)), n_en, n_fml, n_amb))
    print("未映射热榜（前 20）：")
    for (h, n), c0 in unmatched.most_common(20):
        print("   %-6s %s" % (h, n[:26]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

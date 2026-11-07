# -*- coding: utf-8 -*-
r"""从药典 2025 知识库（``indkb.zip``）**扒出成方制剂** —— 名字 + 处方组成 + 剂量。

用户 2026-10-16 问：「能不能直接从药典里扒出来方剂数据？」——能。实测 zip 里
``一部/成方制剂和单味制剂/*.md`` 共 1,618 条，1,550 条正文含【处方】，且**带法定剂量**。

输出 ``chemreact-staging/data/chp_formulas.json``::

    {"一捻金": {"source": "中国药典2025版一部", "url": "https://…",
                "组成": [{"herb": "大黄", "dose": 100.0, "unit": "g", "raw": "大黄 100g"},
                         {"herb": "牵牛子", "dose": 200.0, "unit": "g", "raw": "炒牵牛子 200g",
                          "prep": "炒"}],
                "功能主治": "…", "处方原文": "…"}, …}

用法：``python tools/build_chp_formulas.py``（只读 zip，写我们自己的工作区）
      ``python tools/build_chp_formulas.py --check``（只跑质量统计，不写文件）
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
Z = STAGE / "reports" / "_probe_net" / "indkb.zip"
SUB = "一部/成方制剂和单味制剂/"
OUT = STAGE / "data" / "chp_formulas.json"

_RX = re.compile(r"【\s*处方\s*】")
_NEXT_SEC = re.compile(r"【\s*[^】]{1,12}\s*】")
_DOSE = re.compile(r"(\d+(?:\.\d+)?)\s*(g|kg|mg|ml|mL|μg|ug|％|%)?")
_PREP = ("炒", "炙", "制", "生", "熟", "醋", "酒", "盐", "蜜", "焦", "煅", "姜", "麸炒")


def unwrap_links(s: str) -> str:
    """把 ``[[[[滑石]]粉]]`` 这类嵌套 wikilink 剥成纯文本（反复剥最内层）。"""
    for _ in range(6):
        new = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", s)
        if new == s:
            break
        s = new
    return s


def parse_prescription(raw: str):
    """从【处方】原文里抽 ``[(herb, dose, unit, prep)]``。

    做法：先剥 wikilink，再按「名字 + 数字单位」成对切；抓不到剂量的（"适量"）也留下。
    """
    txt = unwrap_links(raw)
    txt = txt.replace("、", " ").replace("，", " ").replace(",", " ")
    out = []
    # 主匹配：名字（中英文数字括号）紧跟数字+单位
    pat = re.compile(r"([\u4e00-\u9fffA-Za-z()（）·]{2,20}?)\s*"
                     r"(\d+(?:\.\d+)?)\s*(g|kg|mg|ml|mL|μg|ug)?")
    for m in pat.finditer(txt):
        name = m.group(1).strip()
        # 名字里如果粘了上一个剂量的尾巴（如 "g 大黄"）→ 取最后一个片段
        name = re.split(r"[gG]\s*", name)[-1].strip()
        dose = float(m.group(2))
        unit = m.group(3) or "g"
        prep = next((p for p in _PREP if name.startswith(p) and len(name) > len(p) + 1), "")
        # ★ 保留**完整名字**（熟地黄 不能砍成 地黄 —— 第 74 轮实测踩过）。
        #   prep 只作信息；到底要不要剥，交给解析层按药材库决定（配方.py 的 _resolve_one）。
        out.append({"herb": name, "prep": prep,
                    "dose": dose, "unit": unit, "raw": m.group(0).strip()})
    return out


def extract(check_only: bool = False) -> int:
    z = zipfile.ZipFile(Z)
    names = [i.filename for i in z.infolist()
             if i.filename.endswith(".md") and SUB in i.filename]
    res = {}
    n_fail = n_no_rx = n_ok = 0
    for n in names:
        t = z.read(n).decode("utf-8", "replace")
        title = Path(n).stem
        if "内容获取失败" in t:
            n_fail += 1
            continue
        m = _RX.search(t)
        if not m:
            n_no_rx += 1
            continue
        tail = t[m.end():]
        nx = _NEXT_SEC.search(tail)
        rx_raw = tail[:nx.start()] if nx else tail[:400]
        comp = parse_prescription(rx_raw)
        if not comp:
            n_no_rx += 1
            continue
        fm = re.search(r'url:\s*"([^"]*)"', t)
        gj = re.search(r"【\s*功能与主治\s*】(.*?)(?:【|$)", t, re.S)
        res[title] = {
            "source": "中国药典2025版一部",
            "url": fm.group(1) if fm else "",
            "组成": comp,
            "功能主治": re.sub(r"\s+", "", gj.group(1))[:120] if gj else "",
            "处方原文": re.sub(r"\s+", " ", rx_raw).strip()[:400],
        }
        n_ok += 1

    print("候选 %d 条 ｜ 解析成功 %d ｜ 内容获取失败 %d ｜ 无处方/解析不出 %d"
          % (len(names), n_ok, n_fail, n_no_rx))
    dist = {}
    for v in res.values():
        k = len(v["组成"])
        dist[k] = dist.get(k, 0) + 1
    print("每方味数分布：", sorted(dist.items())[:14], "…最大",
          max(dist) if dist else 0)
    if not check_only:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已写出 -> %s（%.2f MB）" % (OUT, OUT.stat().st_size / 1048576))
        # ★ 与用户现有方剂库对齐（只读）
        try:
            fj = Path(r"D:\TCMAI\data\formula_db.json")
            if fj.is_file():
                user = json.loads(fj.read_text(encoding="utf-8"))
                zn = {re.sub(r"[（(].*?[)）]", "", k) for k in res}
                un = {re.sub(r"[（(].*?[)）]", "", k) for k in user}
                print("  与用户方剂库：药典独有 %d ｜ 用户独有 %d ｜ 名字交集 %d"
                      % (len(zn - un), len(un - zn), len(zn & un)))
                print("  药典独有样例：", sorted(zn - un)[:10])
        except Exception as ex:                            # noqa: BLE001
            print("  [warn] 与用户库对比失败：%s: %s" % (type(ex).__name__, ex))
    print("\n样例 3 条：")
    for k in list(res)[:3]:
        v = res[k]
        print("  【%s】%d 味：%s" % (k, len(v["组成"]),
                                    " ".join("%s%s%s" % (c["prep"], c["herb"],
                                                         c["dose"]) for c in v["组成"][:6])))
    return 0


if __name__ == "__main__":
    raise SystemExit(extract(check_only="--check" in sys.argv))

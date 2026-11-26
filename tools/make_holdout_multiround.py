# -*- coding: utf-8 -*-
"""生成 multi-round 留出集：复制全部案例，只按固定规则改两条预期。

固定规则（运行前写死）：
  · 单轮期望 miss、且失败原因是「单轮协议到不了」的案例：
      - dahuang_sennoside（单糖苷中间体，第二轮再水解）
      - huangqi_acetylastragaloside_astragaloside_iv（单轮只脱一个乙酰，第三轮到）
    -> multi-round（rounds=3）预期改为 consistent；
  · 规则缺口（maqianzi 重排、nvzhenzi 多步、tianma 苄醇氧化）保持 miss；
  · 其余案例预期不变。

2026-11-22 第二轮新增的槐米、地黄两例沿用单轮预期，不改写。
2026-11-22 第三轮新增的柴胡、黄柏是缺口探针，单轮预期 miss，多轮也保持 miss
（五元环醚开环/异构化与芳香 O-去甲基都不是「多跑几轮就能闭合」的多步反应）。
2026-11-22 第四轮新增的甘遂两条是二酯→单酯→苷元，单轮 miss、多轮 r3 预期 consistent；
地黄 5-HMF 与吴茱萸两条两模式均 miss。

这是**开发协议**，不是独立留出集；独立证据仍是单轮 strong 集。
"""
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
SRC = ROOT / "data" / "holdout_paozhi.json"
DST = ROOT / "data" / "holdout_paozhi_multiround.json"


def main() -> int:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    d["protocol_version"] = "multiround_v5_rounds3"
    d["rounds"] = 3
    d["created_at"] = "2026-11-22"
    d["frozen_git_rev"] = "multiround-v5 pre-registered 2026-11-22"
    d["purpose"] = (
        "多轮开发协议：现有规则 + rounds=3。不是独立留出集；独立证据仍是单轮 strong 集。")
    d["pre_registered_note"] = (
        "预期改写规则先于运行写死：单轮因协议限制失败的 dahuang、huangqi 改判 consistent；"
        "规则缺口 maqianzi、nvzhenzi、tianma 保持 miss；其余不变。"
        "2026-11-22 第二轮新增的槐米、地黄沿用单轮预期。"
        "2026-11-22 第三轮新增的柴胡、黄柏是缺口探针，单轮与多轮均保持 miss。"
        "2026-11-22 第四轮新增的甘遂两条改判多轮 consistent；地黄5-HMF、吴茱萸保持 miss。")

    changed = 0
    for c in d.get("cases", []):
        if c["id"] == "dahuang_sennoside":
            c["expected"] = {
                "status": "consistent",
                "rule": "hydrolysis_glycoside_001",
                "confidence": "medium",
                "reason": "单轮只到单糖苷；第 2 轮再水解到番泻苷元 A（探针实测）",
            }
            changed += 1
        elif c["id"] == "huangqi_acetylastragaloside_astragaloside_iv":
            c["expected"] = {
                "status": "consistent",
                "rule": "hydrolysis_ester_001",
                "confidence": "medium",
                "reason": "单轮只脱一个乙酰；第 3 轮由酯水解到黄芪甲苷 IV（探针实测）",
            }
            changed += 1
        elif c["id"] in ("gansui_diester_ingenol", "gansui_kpc_deoxyingenol"):
            c["expected"] = {
                "status": "consistent",
                "rule": "hydrolysis_ester_001",
                "confidence": "medium",
                "reason": "单轮只到单酯；第 2 轮再水解到苷元（文献路径，探针待测）",
            }
            changed += 1
    DST.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("写出 %s；%d 例，改写 %d 条预期" % (DST, len(d.get("cases", [])), changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

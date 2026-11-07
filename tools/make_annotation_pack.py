# -*- coding: utf-8 -*-
r"""打一个**专家盲标包**（论文 §6 待办 #1 的材料，可直接发给化学家）。

包里放：
  * `annotation.html` —— 标注页（离线可用，双击打开；每条给"可用/不可用/说不清"三选 + 备注）
  * `标注说明.md`     —— 给专家的一页说明（盲标口径、怎么导出、预计耗时）
  * `导出模板.csv`    —— 导出后的 CSV 表头（与网页导出列一致）
  * 题目清单 JSON     —— 题目原文（便于复核，不参与标注）

用法：``python tools\make_annotation_pack.py``（输出到 `reports\paper\annotation\pack\`）
"""
from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
ANN = STAGE / "reports" / "paper" / "annotation"
PACK = ANN / "pack"
SRC_HTML = ANN / "annotation.html"
SRC_JSONL = STAGE / "reports" / "paper" / "results" / "annotation_candidates.jsonl"


def main() -> int:
    if not SRC_HTML.exists():
        print("★ 缺少 annotation.html —— 先跑 tools\\paper_build_annotation.py")
        return 1
    PACK.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_HTML, PACK / "annotation.html")
    n = 0
    if SRC_JSONL.exists():
        rows = []
        for ln in SRC_JSONL.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except Exception:                                # noqa: BLE001
                continue
        (PACK / "题目清单.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        n = len(rows)
    (PACK / "导出模板.csv").write_text(
        "id,target_smiles,precursor_smiles,verdict,reason,annotator,minutes\n",
        encoding="utf-8-sig")
    eta = "1–2 小时" if n > 150 else "30–60 分钟"
    readme = "\n".join([
        "# 盲标任务说明（模板式逆合成 · 可用性判据外部校验）",
        "",
        "## 你要做什么",
        "",
        "打开 `annotation.html`（双击即可，离线可用）。页面会逐条给出一个**切断**：",
        "目标分子（target）与一组前体（precursors）。请判断：",
        "",
        "> **三件事分开判**（★ 结构可行 ≠ 条件可行）：",
        "",
        "> ① **结构**：这条切断在化学上说得通吗？（合理 / 不合理 / 不确定）",
        "> ② **条件**：要做成它，条件是否常规？（常规 / 极端：高温高压、无水无氧等 / 不确定）",
        "> ③ **试剂**：所需试剂是否常见可得？（常见 / 稀有或昂贵（如特殊配体、稀有金属、酶）/ 不确定）",
        "",
        "页面里会给出**文献条件样例**（来自 ORD 原始记录：催化剂/试剂/溶剂/温度），仅供参考；",
        "样例不存在时页面会标「无（该模板无 ORD 溯源反应）」。",
        "",
        "每一轴都是三选一；三轴都标了才算完成。可在备注里写理由（尤其\"为什么需要稀有试剂\"）。",
        "",
        "## 纪律（很重要）",
        "",
        "1. **盲标**：页面不显示机器的判定，也不要参考任何自动结论；",
        "2. **只判化学**：不看分子是不是天然产物，不看商业可得性（那是另一层判据）；",
        "3. 拿不准就选「说不清」—— 它比瞎猜有用；",
        "4. 每题预计 20–40 秒，全做完约 %s。" % eta,
        "",
        "## 怎么交回",
        "",
        "1. 页面右上角点 **导出 CSV**（或按页面提示）；",
        "2. 把导出的 CSV 与你的姓名（或代号）、耗时一并回传；",
        "3. 若中途休息，浏览器里的进度不会丢（本地存储）。",
        "",
        "## 我们怎么用",
        "",
        "* 只用于**外部效度**：与我们的启发式判据逐条对比（一致率 / 分歧类型）；",
        "* 你的标注会匿名汇总进论文 Limitations 一节（「无人工盲评」因此改为「小样本专家校验」）；",
        "* 原始标注文件我们会原样留档，不删不改。",
        "",
    ])
    (PACK / "标注说明.md").write_text(readme, encoding="utf-8")
    z = PACK / "专家盲标包.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in ("annotation.html", "标注说明.md", "导出模板.csv", "题目清单.json"):
            p = PACK / f
            if p.exists():
                zf.write(p, f)
    print("=" * 90)
    print("专家盲标包 -> %s" % z)
    print("  含：annotation.html（%.1f MB）｜ 标注说明.md ｜ 导出模板.csv ｜ 题目清单.json（%d 条）"
          % ((PACK / "annotation.html").stat().st_size / 1e6, n))
    print("  ★ 直接把这个 zip 发给化学家即可（离线可用；页面不含机器判定）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

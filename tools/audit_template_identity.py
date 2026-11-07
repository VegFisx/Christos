# -*- coding: utf-8 -*-
r"""质检员（2026-10-14）：模板库"全等 / 原样穿过"检查 —— 只按【完全相同】判定，近似的不管。

用户拍板的口径（两条）：
  * 全等（no-op）：一条反应的两侧，每个分子都能在另一侧找到**完全相同**的对应物
    （判据 = 映射号集合一致 —— 映射号在一条反应里唯一，所以这等价于"同一批原子原样穿过"）
    -> 这种"反应"不可能是真反应（只会把目标自己当产物/前体还回来）-> 交给黑名单（小黑屋）。
  * 部分相同（有分子原样穿过 + 另有新分子）：把穿过的分子标注【疑似催化剂】
    （进得来、出得去，是催化剂/盐/缓冲组分的典型特征）。
  * 不是完全相同的 -> 一律不管（近似的假路线问题另行处理，不在本工具范围）。

扫描对象（三个库）：
  reports/retro_templates_clustered.jsonl  逆模板 3,228 条
  reports/mined_forward_templates_3c.jsonl 挖矿 3 组分正向 2,443 条
  libs/smartreact/data/templates.txt       SmartReact 正向 9,770 条（对照）

输出：
  reports/template_identity_audit.json —— 全等清单 + 疑似催化剂标注 + 条件组分候选表
  （其中 noop 清单会被 tools/build_retro_blacklist.py 并入小黑屋）

用法: python tools/audit_template_identity.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
RETRO = STAGE / "reports" / "retro_templates_clustered.jsonl"
MINED3C = STAGE / "reports" / "mined_forward_templates_3c.jsonl"
SMARTREACT = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
OUT = STAGE / "reports" / "template_identity_audit.json"


def _split(side: str):
    out, depth, cur = [], 0, []
    for ch in side:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "." and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur).strip())
    return [x for x in out if x]


def _key(frag: str) -> str:
    """抹掉映射号后的规范化结构键（M| = 能按分子解析；S|/X| = 只能是模式/原文）。"""
    s = re.sub(r":\d+", "", frag)
    m = Chem.MolFromSmiles(s)
    if m is not None:
        return "M|" + Chem.MolToSmiles(m)
    m = Chem.MolFromSmarts(s)
    return ("S|" + Chem.MolToSmarts(m)) if m is not None else "X|" + s


def _maps(frag: str):
    return frozenset(int(x) for x in re.findall(r":(\d+)", frag))


def scan(name: str, items):
    """items: (line_tag, smarts)。返回 (n, noops, passthrough, loose_noop_only)。"""
    n = 0
    noops, passthrough = [], []
    loose_noop_only = 0
    for tag, smarts in items:
        if not smarts or ">>" not in smarts:
            continue
        n += 1
        l, r = smarts.split(">>", 1)
        lf, rf = _split(l), _split(r)
        lu = [(frozenset(_maps(f)), _key(f)) for f in lf]
        ru = [(frozenset(_maps(f)), _key(f)) for f in rf]
        strict_noop = (len(lu) == len(ru) and sorted(lu) == sorted(ru))
        if strict_noop:
            noops.append({"lib": name, "line": tag, "smarts": smarts})
            continue
        common = [u for u in sorted(set(lu) & set(ru))]
        if common:
            disp = {}
            for f in lf:
                disp.setdefault((frozenset(_maps(f)), _key(f)), f)
            for u in common:
                passthrough.append({"lib": name, "line": tag, "smarts": smarts,
                                    "spectator_key": u[1], "spectator_raw": disp.get(u, "")})
        else:
            # 宽松（抹映射号后）全等但严格不等：记录数量，不当作 no-op（保守）
            if sorted(_key(f) for f in lf) == sorted(_key(f) for f in rf):
                loose_noop_only += 1
    return n, noops, passthrough, loose_noop_only


def main() -> int:
    t0 = time.time()
    print("=" * 78)
    print("质检员：模板库全等 / 原样穿过检查（只判完全相同）")
    print("=" * 78)

    retro_items = []
    for i, line in enumerate(open(RETRO, encoding="utf-8")):
        line = line.strip()
        if line:
            retro_items.append((i, json.loads(line).get("template", "")))
    mined_items = []
    for i, line in enumerate(open(MINED3C, encoding="utf-8")):
        line = line.strip()
        if line:
            r = json.loads(line)
            mined_items.append((i, r.get("template") or r.get("smarts") or ""))
    sr_items = []
    for i, line in enumerate(open(SMARTREACT, encoding="utf-8", errors="replace")):
        f = line.rstrip("\n").split("\t")
        if len(f) >= 4:
            sr_items.append((i, f[3]))

    n1, noop1, pass1, loose1 = scan("retro", retro_items)
    n2, noop2, pass2, loose2 = scan("mined_3c", mined_items)
    n3, noop3, pass3, loose3 = scan("smartreact", sr_items)

    # 逆库的 no-op 是否还在编译集里（编译集内才需要进小黑屋；其余本来就被编译器扔了）
    for x in noop1:
        x["in_compiled"] = False
    try:
        sys.path.insert(0, str(STAGE / "tools"))
        sys.path.insert(0, str(STAGE / "libs"))
        import retro_search as rs
        compiled = {t.smarts for t in rs.load_rdchiral_templates()}
        for x in noop1:
            x["in_compiled"] = x["smarts"] in compiled
    except Exception as ex:                      # noqa: BLE001 —— 打印，不静默
        print("   [warn] 无法核对编译集（retro_search 加载失败）：%s" % ex)

    # 条件组分候选：按"穿过分子"聚合
    cand = Counter()
    for x in pass1 + pass2 + pass3:
        cand[(x["lib"], x["spectator_key"])] += 1
    top = cand.most_common(12)

    out = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "criterion": "完全相同（映射号集合一致）才判；近似一律不管（用户口径 2026-10-14）",
        "checked": {"retro_templates_clustered": n1, "mined_forward_templates_3c": n2,
                    "smartreact_templates_txt": n3},
        "noop": noop1 + noop2 + noop3,
        "pass_through": pass1 + pass2 + pass3,
        "condition_component_candidates": [
            {"lib": k[0], "key": k[1], "display": k[1][2:], "n_templates": c}
            for k, c in cand.most_common()],
        "loose_only_noop_counts": {"retro": loose1, "mined_3c": loose2, "smartreact": loose3},
        "notes": ["no-op 只会把目标自己当产物/前体还回来，结构上不可能贡献有效路线",
                  "pass_through 的分子 = 进得来出得去 -> 标注疑似催化剂（催化剂/盐/缓冲组分）",
                  "近似的（只差 H2/小基团）不属于本工具口径，未处理"],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("库                  条数    全等no-op   部分相同(有原样穿过)   宽松-noop(保守不计)")
    print("retro(逆)        %6d %8d %12d %14d" % (n1, len(noop1), len(pass1), loose1))
    print("mined_3c(正向)   %6d %8d %12d %14d" % (n2, len(noop2), len(pass2), loose2))
    print("smartreact(正向) %6d %8d %12d %14d" % (n3, len(noop3), len(pass3), loose3))
    print("-" * 78)
    for x in noop1:
        print("no-op(逆) 行%4s 编译集内=%s  %s" % (
            x["line"], "是" if x.get("in_compiled") else "否(已被编译器扔)", x["smarts"][:70]))
    for x in noop2:
        print("no-op(挖) 行%4s  %s" % (x["line"], x["smarts"][:70]))
    print("疑似催化剂（按分子聚合，top）：")
    for k, c in top:
        print("   %3d 条模板  [%s] %s" % (c, k[0], k[1][2:][:70]))
    print("写出：%s（%.1fs）" % (OUT.name, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

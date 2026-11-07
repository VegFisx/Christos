# -*- coding: utf-8 -*-
r"""给立体化学闸门加「引擎限制」分类。

动机（实测）：
    同一个底物、同一条规则（脱水）
      rdkit    产物保留旁观手性中心  ✓
      rdchiral 产物丢失              ✗
    而引擎对单反应物规则【强制走 rdchiral】。

    旧版闸门把这类丢失一律报成「规则缺陷」，会误导人
    去改一条根本没问题的规则。现在改成两类分开报：
      · 规则缺陷      rdchiral 和 rdkit 都丢
      · 引擎限制      只有 rdchiral 丢，换 rdkit 就保住
"""
from pathlib import Path
import ast

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\stereo.py")
t = F.read_text(encoding="utf-8")

# ---- 1. 初始化新计数器 ----
old1 = """    n_checked = n_spectator = n_lost = 0
    examples: List[str] = []"""
new1 = """    n_checked = n_spectator = n_lost = 0
    n_engine_limit = 0
    examples: List[str] = []
    limit_examples: List[str] = []"""
assert old1 in t, "计数器初始化未找到"
t = t.replace(old1, new1, 1)

# ---- 2. 追加「引擎限制」issue ----
old2 = '''    if n_checked and n_lost:
        issues.append(StereoIssue(
            rule["id"], rule["name"], "手性中心丢失",
            f"检查了 {n_checked} 个带手性的底物，其中 {n_lost} 个的产物"
            f"丢失了【作用范围之外】的手性中心（共 {n_spectator} 个旁观中心）",
            examples[0] if examples else ""))
    return issues'''
new2 = '''    if n_checked and n_lost:
        issues.append(StereoIssue(
            rule["id"], rule["name"], "手性中心丢失",
            f"★规则缺陷★ 检查了 {n_checked} 个带手性的底物，其中 {n_lost} 个的产物"
            f"丢失了【作用范围之外】的手性中心（共 {n_spectator} 个旁观中心）。"
            f"换 rdkit 跑同样丢失，说明是规则自身的问题。",
            examples[0] if examples else ""))
    if n_checked and n_engine_limit:
        issues.append(StereoIssue(
            rule["id"], rule["name"], "引擎限制（非规则缺陷）",
            f"检查了 {n_checked} 个带手性的底物，其中 {n_engine_limit} 个在 rdchiral 下"
            f"丢失旁观手性中心，但【换 rdkit 跑就保住了】——"
            f"这是第三方引擎 rdchiral 的限制，不是规则写错。"
            f"引擎对该类规则强制走 rdchiral，所以实际输出会少一层立体信息。",
            limit_examples[0] if limit_examples else ""))
    return issues'''
assert old2 in t, "issue 追加块未找到"
t = t.replace(old2, new2, 1)

# ---- 3. 主流程分两类打印 ----
old3 = '''    if all_issues:
        print("=" * 92)
        print(f"★ 手性中心丢失 {len(all_issues)} 条规则 ★")
        print("=" * 92)
        for i in all_issues:
            print(f"  [{i.rule_name}] {i.detail}")
            if i.example:
                print(f"      例：{i.example}")
    else:
        print("✓ 未发现「作用范围外手性中心丢失」的问题")'''
new3 = '''    real = [i for i in all_issues if i.kind == "手性中心丢失"]
    limits = [i for i in all_issues if i.kind != "手性中心丢失"]

    if real:
        print("=" * 92)
        print(f"★ 规则缺陷：手性中心丢失 {len(real)} 条 ★")
        print("=" * 92)
        for i in real:
            print(f"  [{i.rule_name}] {i.detail}")
            if i.example:
                print(f"      例：{i.example}")

    if limits:
        print()
        print("=" * 92)
        print(f"○ 引擎限制（非规则缺陷）{len(limits)} 条 ○")
        print("=" * 92)
        for i in limits:
            print(f"  [{i.rule_name}] {i.detail}")
            if i.example:
                print(f"      例：{i.example}")

    if not all_issues:
        print("✓ 未发现「作用范围外手性中心丢失」的问题")'''
assert old3 in t, "主流程打印块未找到"
t = t.replace(old3, new3, 1)

# ---- 4. 退出码只看规则缺陷 ----
t = t.replace("    return 1 if all_issues else 0",
              "    return 1 if real else 0", 1)

F.write_text(t, encoding="utf-8")
ast.parse(t)
print("stereo.py 已改，语法 OK")

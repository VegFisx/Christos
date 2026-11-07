# -*- coding: utf-8 -*-
r"""永久防护：找出「在全部工艺下都激活不了」的规则。

★ 为什么需要它

  这类规则是**静默失效**：不报错、不告警、校验也能过，
  只是在你跑任何一个方剂时都不会出现。

  实测事故：3 条规则因为 priority=0.1 < 激活阈值 0.15，
  在全部 10 种工艺下都激活不了。规则库看起来是 56 条 active，
  实际上只有 53 条能被触发 —— 少了 5%，而且没有任何提示。

用法：
    python check_never_active.py
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("rules", "conditions", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from schema import load_rules
import templates as T
from activator import active_rules


def main() -> int:
    profiles, rules = load_rules(str(STAGE / "rules" / "rules.json"))
    conds = list(T.TEMPLATES.keys()) if hasattr(T, "TEMPLATES") else [
        "煎煮", "水提", "醇提", "酸水解", "碱水解",
        "氧化", "还原", "酶催化", "室温浸泡", "无氧煎煮"]

    ever = set()
    per_rule = {}
    for label in conds:
        try:
            cond = T.get_template(label)
        except Exception:
            continue
        act = {rr["id"] for rr, _s, _w in active_rules(rules, profiles, cond)}
        ever |= act
        for rid in act:
            per_rule.setdefault(rid, []).append(label)

    enabled = [r for r in rules if r.get("status") != "disabled"]
    never = [r for r in enabled if r["id"] not in ever]

    print(f"工艺模板 {len(conds)} 个: {conds}")
    print(f"启用中规则 {len(enabled)} 条")
    print(f"至少激活过一次: {len(ever)} 条")
    print()

    if never:
        print("=" * 88)
        print(f"★ 永远激活不了的规则 {len(never)} 条（静默失效）★")
        print("=" * 88)
        for r in never:
            print(f"  {r['name']:<22} priority={r.get('priority')}  "
                  f"profile={r.get('condition_profile')}")
        print()
        print("  常见原因：")
        print("    · priority 低于激活阈值（阈值默认 0.15）")
        print("    · condition_profile 的窗口没有任何模板能满足")
        rc = 1
    else:
        print("✓ 所有启用中的规则在至少一种工艺下可激活")
        rc = 0

    # 顺带报一下"只在单一工艺下激活"的规则（条件覆盖过窄，不一定是错）
    one = {k: v for k, v in per_rule.items() if len(v) == 1}
    if one:
        print()
        print(f"提示：{len(one)} 条规则只在单一工艺下激活（可能是有意设计，也可能覆盖过窄）")
        for rid, labels in sorted(one.items(), key=lambda x: x[1]):
            n = next((r["name"] for r in rules if r["id"] == rid), rid)
            print(f"    {n:<22} 只在「{labels[0]}」")

    # 阈值敏感性：如果把阈值调高，会掉多少
    print()
    print("附：激活阈值的敏感性（以「煎煮」为例）")
    cond = T.get_template("煎煮")
    for th in (0.10, 0.15, 0.20, 0.30, 0.40, 0.50):
        n = len(active_rules(rules, profiles, cond, th))
        print(f"    阈值 {th:.2f} → 激活 {n:>2} 条")

    return rc


if __name__ == "__main__":
    raise SystemExit(main())

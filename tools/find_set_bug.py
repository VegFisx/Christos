# -*- coding: utf-8 -*-
"""定位：finalize 脚本运行时到底把哪个字段变成了 set。"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}


def find_bad(o, path="root"):
    bad = []
    if isinstance(o, set):
        bad.append((path, "set", sorted(o)[:5]))
    elif isinstance(o, dict):
        for k, v in o.items():
            bad += find_bad(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            bad += find_bad(v, f"{path}[{i}]")
    elif not isinstance(o, (str, int, float, bool, type(None))):
        bad.append((path, type(o).__name__, repr(o)[:60]))
    return bad


print("① 载入后立刻检查：", find_bad(data) or "干净")

MANUAL = {
    "elimination_amide_to_nitrile_001": {
        "co_reagents": {}, "byproducts": {"H2O": 1},
        "why": "脱水",
    },
    "reduction_sulfoxide_001": {
        "co_reagents": {"H2": 1}, "byproducts": {"H2O": 1},
        "why": "还原",
    },
}

for rid, patch in MANUAL.items():
    if rid not in by_id:
        print(f"  找不到 {rid}")
        continue
    by_id[rid]["co_reagents"] = patch["co_reagents"]
    by_id[rid]["byproducts"] = patch["byproducts"]
    by_id[rid]["notes"] = str(by_id[rid].get("notes", "")) + f" 【手工配平】{patch['why']}"

print("② 补配平后检查：", find_bad(data) or "干净")

# 逐条规则单独试序列化，定位是哪一条
for r in data["rules"]:
    try:
        json.dumps(r, ensure_ascii=False)
    except TypeError as e:
        print(f"③ ★问题规则★ {r['id']}: {e}")
        for k, v in r.items():
            try:
                json.dumps(v, ensure_ascii=False)
            except TypeError as e2:
                print(f"      字段 {k!r} 不可序列化: {type(v).__name__}  {e2}")

print("④ 全量序列化测试：", end=" ")
try:
    json.dumps(data, ensure_ascii=False)
    print("通过")
except TypeError as e:
    print(f"失败 -> {e}")

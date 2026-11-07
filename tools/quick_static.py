import sys
sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\rules")
from schema import load_rules, static_checks
profiles, rules = load_rules(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
print(f"JSON OK  rules={len(rules)}  profiles={len(profiles)}")
bad = 0
for r in rules:
    p = static_checks(r, profiles)
    if p:
        bad += 1
        print(f"\n[{r['name']}] {r['id']}")
        for x in p:
            print(f"    - {x}")
print(f"\n静态检查: {len(rules)-bad}/{len(rules)} 通过")

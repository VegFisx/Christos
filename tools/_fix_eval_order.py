# -*- coding: utf-8 -*-
"""一次性：把 retro_cluster_eval.py 的评估段重排（定义在前、调用在后）。"""
import re
from pathlib import Path
p = Path(r"D:\ProgramData\DSHNS\chemreact-staging\tools\retro_cluster_eval.py")
src = p.read_text(encoding="utf-8")

start = src.index("    compiled, bad = [], 0")
end = src.index("    hit = n_eval = 0")
old_block = src[start:end]

new_block = '''    def norm(smi):
        m = Chem.MolFromSmiles(smi)
        if m is None:
            return None
        for a in m.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(m)

    def make_matcher(templates_compiled):
        """返回 match(product_smiles, want_set) -> (是否命中, 命中模板)。"""
        def match(prod_smi, want):
            m = Chem.MolFromSmiles(prod_smi)
            if m is None:
                return False, None
            for tpl, rx, q in templates_compiled:
                try:
                    if q is not None and not m.HasSubstructMatch(q):
                        continue
                except Exception:
                    continue
                try:
                    res = rx.RunReactants((m,))
                except Exception:
                    continue
                for tup in res[:20]:
                    try:
                        got = set()
                        good = True
                        for pm in tup:
                            Chem.SanitizeMol(pm)
                            c = norm(Chem.MolToSmiles(pm))
                            if not c:
                                good = False
                                break
                            got.add(c)
                    except Exception:
                        good = False
                    if good and got == want:
                        return True, tpl
            return False, None
        return match

    compiled, bad = [], 0
    for r in clustered:
        try:
            rx = rdChemReactions.ReactionFromSmarts(r["template"])
            if rx is None or rx.GetNumReactantTemplates() != 1:
                bad += 1
                continue
            compiled.append((r["template"], rx, rx.GetReactantTemplate(0)))
        except Exception:
            bad += 1
    print(f"   可编译模板 {len(compiled):,}（失败 {bad}）")
    match_new = make_matcher(compiled)

    match_base = None
    if args.baseline:
        print("   [对照] 载入 SmartReact 反转模板...", flush=True)
        tpl_path = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
        base = []
        for line in tpl_path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
            f = line.split("\\t")
            if len(f) != 5 or ">>" not in f[3]:
                continue
            lhs, rhs = f[3].split(">>", 1)
            try:
                rx = rdChemReactions.ReactionFromSmarts(f"{rhs}>>{lhs}")
            except Exception:
                continue
            if rx is None or rx.GetNumReactantTemplates() != 1:
                continue
            base.append((f[0], rx, None))
        print(f"   [对照] SmartReact 反转模板 {len(base):,} 条")
        match_base = make_matcher(base)

    base_hit = 0
'''
src = src[:start] + new_block + src[end:]
p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("重排完成，语法 OK")

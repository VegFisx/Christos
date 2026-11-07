# -*- coding: utf-8 -*-
r"""打印 ord_schema 关键 message 的真实字段名（问描述符，不猜）。"""
import sys
from pathlib import Path

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\libs")

from ord_schema.proto import reaction_pb2  # noqa: E402

TARGETS = [
    "ReactionOutcome",
    "Product",
    "CompoundIdentifier",
    "InputsEntry",
    "Amount",
    "ReactionRole",
]

for name in TARGETS:
    d = getattr(reaction_pb2, name, None)
    if d is None:
        print(f"✗ 没有 {name}")
        continue
    desc = d.DESCRIPTOR
    print("=" * 78)
    print(f"{name}")
    print("=" * 78)
    for f in desc.fields:
        if getattr(f, "is_repeated", False):
            label = "repeated"
        elif getattr(f, "is_required", False):
            label = "required"
        elif hasattr(f, "label"):
            label = {1: "optional", 2: "required", 3: "repeated"}.get(f.label, str(f.label))
        else:
            label = "optional"
        tn = f.message_type.name if f.message_type else f.type
        print(f"   {f.number:>3}  {f.name:<28} {label:<9} {tn}")
    print()

# 枚举值
print("=" * 78)
print("ReactionIdentifierType 枚举")
print("=" * 78)
for v in reaction_pb2.ReactionIdentifier.ReactionIdentifierType.DESCRIPTOR.values:
    print(f"   {v.number:>3}  {v.name}")

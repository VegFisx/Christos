import zipfile, sys
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
zf=zipfile.ZipFile(r'D:/ProgramData/DSHNS/chemreact-staging/reports/_probe_net/indkb.zip')
p='Independent-KBs-master/药典2025知识库_最终版/一部/药材和饮片/炙甘草.md'
print(zf.read(p).decode('utf-8','replace'))

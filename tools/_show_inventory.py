import json
p=r"D:\ProgramData\DSHNS\chemreact-staging\reports\data_assets_20261019.json"
d=json.load(open(p,encoding='utf-8'))
for a in d['assets']:
    print(a['id'], a['status'], a.get('size_bytes'), a.get('mtime'), a.get('sha256'))
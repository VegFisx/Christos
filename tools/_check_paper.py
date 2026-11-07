import re, pathlib
p=pathlib.Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\论文-初稿-20261019.md")
t=p.read_text(encoding='utf-8')
lines=t.splitlines()
print('chars',len(t),'lines',len(lines))
print('h2:',[l for l in lines if l.startswith('## ')])
imgs=re.findall(r'!\[[^\]]*\]\(([^)]+)\)',t)
base=p.parent
for i in imgs: print('img',i, (base/i).exists())
pcts=re.findall(r'\d+\.\d+%',t)
print('pct tokens',len(pcts))
print('tables',sum(1 for l in lines if l.startswith('|---')))
print('backticks',t.count('`'))
import json, sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
D = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\references")
rows = [
 ('c2019_rdchiral','Coley CW, Green WH, Jensen KF (2019) RDChiral','10.1021/acs.jcim.9b00286','JCIM 59(6):2529-2537','CC BY-NC-ND (MIT DSpace copy)','blocked'),
 ('chen2020_retrostar','Chen B, Li C, Dai H, Song L (2020) Retro*','PMLR 119:1608-1616 (no DOI)','ICML 2020','arXiv preprint','ok'),
 ('genheden2020_aizynth','Genheden S et al. (2020) AiZynthFinder','10.1186/s13321-020-00472-1','J Cheminform 12:70','CC BY 4.0','ok'),
 ('genheden2022_paroutes','Genheden S, Bjerrum EJ (2022) PaRoutes','10.1039/d2dd00015f','Digital Discovery 1(4):527-539','CC BY-NC','blocked'),
 ('kearnes2021_ord','Kearnes SM et al. (2021) The Open Reaction Database','10.1021/jacs.1c09820','JACS 143(45):18820-18826','CC BY-NC-ND (Caltech copy)','ok'),
 ('maziarz2025_syntheseus','Maziarz K et al. (2025) Syntheseus','10.1039/d4fd00093e','Faraday Discuss 256:568-586','arXiv preprint','ok'),
 ('schneider2016_whatswhat','Schneider N, Stiefl N, Landrum GA (2016) What is What','10.1021/acs.jcim.6b00564','JCIM 56(12):2336-2346','closed access','none'),
 ('sorokina2021_coconut','Sorokina M et al. (2021) COCONUT','10.1186/s13321-020-00478-9','J Cheminform 13:2','CC BY 4.0','ok'),
 ('torrenperaire2024_modelsmatter','Torren-Peraire P et al. (2024) Models Matter','10.1039/d3dd00252g','Digital Discovery 3(3):558-572','CC BY (arXiv 2308.05522)','ok'),
]
lines = ['# Reference PDFs','' ,'所有 DOI 于 2026-10-19 用 Crossref/PMLR 核过；下列 PDF 仅作写作与核对用，**不随投稿包分发**。','',
 '| key | 文献 | DOI | 卷期 | 许可 | 本地文件 |','|---|---|---|---|---|---|']
have = {p.stem: p.stat().st_size for p in D.glob('*.pdf')}
for key, name, doi, where, lic, state in rows:
    f = (key + '.pdf')
    cell = ('`%s` (%.1f MB)' % (f, have[key]/1048576.0)) if key in have else ('— (%s)' % state)
    lines.append('| %s | %s | %s | %s | %s | %s |' % (key, name, doi, where, lic, cell))
lines += ['', '## 未取到全文的三篇', '',
 '- **RDChiral** (10.1021/acs.jcim.9b00286): ACS 正文付费；MIT DSpace 有接收稿，但 DSpace 限流（429），多次重试未成功。',
 '- **PaRoutes** (10.1039/d2dd00015f): RSC 与 ChemRxiv 均对脚本返回 403（反爬），可在浏览器中直接打开 DOI 下载。',
 '- **Schneider 2016** (10.1021/acs.jcim.6b00564): 无 OA 版本，正文需 ACS 订阅。',
 '', '其余 6 篇已落盘，来源均为开放获取（含 arXiv 与机构库副本）。']
(D/'README.md').write_text(chr(10).join(lines)+chr(10), encoding='utf-8')
print('pdfs', len(have), sorted(have))
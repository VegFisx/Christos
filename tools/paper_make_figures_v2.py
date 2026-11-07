# -*- coding: utf-8 -*-
"""Publication figures (v2): 300 dpi, single/double column widths, no in-figure titles.

Data sources (all frozen, see reports/paper/论文-v1.0.0-主线与消融统计总表.md):
  fig1  reports/retro_template_audit.jsonl
  fig2  reports/retro_template_audit_summary_r41.json + results/usability_summary.json
  fig3  results/coverage_summary.json (50,016 targets / 3,065 templates)
  fig4  same as fig2 (verdict composition)
  fig5  results/instability.json + results/usability_summary.json (ustat)
  fig6  results/forward_50k.json (baseline default configuration)
  fig7  frozen table #3/#54 (cap 8/32/64; depth<=2/3 with Wilson CI)
"""
import json, sys
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
RES = STAGE / 'reports' / 'paper' / 'results'
FIG = STAGE / 'reports' / 'paper' / 'figures-v2'

plt.rcParams.update({
  'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.labelsize': 8.5,
  'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5, 'legend.fontsize': 7,
  'axes.spines.top': False, 'axes.spines.right': False,
  'axes.linewidth': 0.7, 'xtick.major.width': 0.7, 'ytick.major.width': 0.7,
  'savefig.dpi': 300, 'figure.dpi': 300, 'pdf.fonttype': 42,
})

C_MAIN, C_ALT, C_BAD, C_WARN = '#3d6fa8', '#8fb3d9', '#c0504d', '#e0a33a'

def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in ('png', 'pdf'):
        fig.savefig(FIG / (name + '.' + ext), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('  wrote', name)

def fig1():
    src = STAGE / 'reports' / 'retro_template_audit.jsonl'
    rows = [json.loads(l) for l in open(src, encoding='utf-8') if l.strip()]
    rows = [r for r in rows if int(r.get('n_try', 0)) > 0]
    rows.sort(key=lambda r: -int(r.get('n_try', 0)))
    tot = sum(int(r.get('n_try', 0)) - int(r.get('n_usable', 0)) for r in rows)
    cum, xs = 0, []
    for r in rows:
        cum += int(r.get('n_try', 0)) - int(r.get('n_usable', 0))
        xs.append(100.0 * cum / max(1, tot))
    fig, ax = plt.subplots(figsize=(3.35, 2.5))
    ax.plot(range(1, len(xs) + 1), xs, lw=1.3, color=C_MAIN)
    ax.plot([54], [83.8], 'o', ms=4, color=C_BAD)
    ax.annotate('54 templates\n83.8% of wasted cuts', xy=(54, 83.8), xytext=(120, 62),
                fontsize=7, color=C_BAD,
                arrowprops=dict(arrowstyle='-', lw=0.7, color=C_BAD))
    ax.set_xlabel('Templates, ranked by wasted cut attempts')
    ax.set_ylabel('Cumulative share of wasted cuts (%)')
    ax.set_ylim(0, 102); ax.set_xlim(0, len(xs) + 5)
    save(fig, 'fig1_concentration')

def _verdicts():
    a = STAGE / 'reports' / 'retro_template_audit.jsonl'
    groups = []
    tot = Counter()
    for l in open(a, encoding='utf-8'):
        if not l.strip(): continue
        r = json.loads(l)
        tot['usable'] += int(r.get('n_usable', 0))
        for k, v in r.items():
            if k.startswith('R') and k[1:2].isdigit():
                tot[k.split('_')[0]] += int(v)
    n = sum(tot.values())
    groups.append(('56-target set', {k: 100.0 * v / max(1, n) for k, v in tot.items()}))
    s = json.loads((RES / 'usability_summary.json').read_text(encoding='utf-8'))
    tot2 = Counter()
    for k, v in s['verdicts'].items():
        tot2['usable' if k == 'ok' else k.split('_')[0]] += v
    n2 = sum(tot2.values())
    groups.append(('USPTO-50k sample', {k: 100.0 * v / max(1, n2) for k, v in tot2.items()}))
    return groups

def fig2():
    bars = []
    s = json.loads((STAGE / 'reports' / 'retro_template_audit_summary_r41.json').read_text(encoding='utf-8'))
    bars.append(('56-target set', 100.0 * s['totals']['n_usable'] / s['totals']['n_try'],
                 100.0 * s['before_after']['after']['n_usable'] / s['before_after']['after']['n_try']))
    u = json.loads((RES / 'usability_summary.json').read_text(encoding='utf-8'))
    bars.append(('USPTO-50k sample', 100.0 * u['usable_rate'], 100.0 * u['usable_rate_after_blacklist']))
    x = np.arange(len(bars)); w = 0.34
    fig, ax = plt.subplots(figsize=(3.35, 2.5))
    ax.bar(x - w/2, [b[1] for b in bars], w, color=C_ALT, label='Before blacklist')
    ax.bar(x + w/2, [b[2] for b in bars], w, color=C_MAIN, label='After blacklist')
    for i, b in enumerate(bars):
        ax.text(i - w/2, b[1] + 0.4, '%.2f' % b[1], ha='center', fontsize=6.5)
        ax.text(i + w/2, b[2] + 0.4, '%.2f' % b[2], ha='center', fontsize=6.5)
    ax.set_xticks(x, [b[0] for b in bars])
    ax.set_ylabel('Chemically usable cuts (%)')
    ax.legend(frameon=False, loc='upper left')
    save(fig, 'fig2_blacklist')

def fig3():
    s = json.loads((RES / 'coverage_summary.json').read_text(encoding='utf-8'))
    ks = ['top1', 'top3', 'top5', 'top10', 'top50']
    labels = ['any', 'top-1', 'top-3', 'top-5', 'top-10', 'top-50']
    vals = [100.0 * s['any_hit_rate']] + [100.0 * s['topk'][k]['rate'] for k in ks]
    fig, ax = plt.subplots(figsize=(3.35, 2.5))
    ax.bar(range(len(vals)), vals, color=[C_BAD] + [C_MAIN] * 5, width=0.65)
    for i, v in enumerate(vals):
        ax.text(i, v + 1.0, '%.1f' % v, ha='center', fontsize=6.8)
    ax.set_xticks(range(len(labels)), labels)
    ax.set_ylim(0, 100); ax.set_ylabel('Reactant-set match rate (%)')
    save(fig, 'fig3_coverage_topk')

def fig4():
    groups = _verdicts()
    keys = ['usable', 'R1', 'R2', 'R3', 'R4']
    colors = {'usable': '#4f8a4f', 'R1': '#c0504d', 'R2': '#e0a33a', 'R3': '#8064a2', 'R4': '#8c7a6b'}
    x = np.arange(len(groups)); bottom = np.zeros(len(groups))
    fig, ax = plt.subplots(figsize=(3.35, 2.6))
    for k in keys:
        v = np.array([g[1].get(k, 0.0) for g in groups])
        ax.bar(x, v, 0.45, bottom=bottom, label=k, color=colors[k], edgecolor='white', linewidth=0.4)
        for i, (vv, bb) in enumerate(zip(v, bottom)):
            if vv > 4: ax.text(i, bb + vv/2, '%.0f%%' % vv, ha='center', va='center', fontsize=6.5, color='white')
        bottom += v
    ax.set_xticks(x, [g[0] for g in groups]); ax.set_ylim(0, 100)
    ax.set_ylabel('Share of single-step cuts (%)')
    ax.legend(ncol=5, frameon=False, loc='upper center', bbox_to_anchor=(0.5, 1.12), fontsize=6.5)
    save(fig, 'fig4_composition')

def fig5():
    labels, vals, notes = [], [], []
    # 56-target audit: reports/retro_template_audit_summary_r41.json (88 calls, 68 timeouts)
    s41 = json.loads((STAGE / 'reports' / 'retro_template_audit_summary_r41.json').read_text(encoding='utf-8'))
    u = s41['usability_stats']
    labels.append('56-target audit\n(88 MCS calls)'); vals.append(100.0 * u['mcs_timeout'] / u['mcs_calls'])
    notes.append('second run of the\nsame audit: 66/87')
    us = json.loads((RES / 'usability_summary.json').read_text(encoding='utf-8'))['ustat']
    labels.append('USPTO-50k sample\n(74,968 calls)'); vals.append(100.0 * us['mcs_timeout'] / us['mcs_calls'])
    notes.append('historical replication\ndifference: 3/414 cuts')
    fig, ax = plt.subplots(figsize=(3.35, 2.6))
    ax.bar(labels, vals, color=C_BAD, width=0.45)
    for i, v in enumerate(vals):
        ax.text(i, v + 2.0, '%.1f%%' % v, ha='center', fontsize=7.5)
    ax.set_ylim(0, 115); ax.set_ylabel('MCS time-out share (%)')
    for i, t in enumerate(notes):
        ax.text(i, 104, t, ha='center', va='top', fontsize=6.2, color='#555555')
    save(fig, 'fig5_timeout')

def fig6():
    s = json.loads((RES / 'forward_50k.json').read_text(encoding='utf-8'))
    d = s['by_class_recall']; ks = sorted(d, key=lambda k: int(k))
    vals = [100.0 * d[k]['rate'] for k in ks]
    fig, ax = plt.subplots(figsize=(3.6, 2.5))
    ax.bar(range(len(ks)), vals, color=C_MAIN, width=0.65)
    for i, v in enumerate(vals):
        ax.text(i, v + 1.2, '%.0f' % v, ha='center', fontsize=6.2)
    over = 100.0 * s['recall_1step']
    ax.axhline(over, ls='--', lw=0.8, color=C_BAD)
    ax.text(len(ks) - 0.4, over + 1.5, 'overall %.1f%%' % over, ha='right', fontsize=6.8, color=C_BAD)
    ax.set_xticks(range(len(ks)), ['%s' % k for k in ks])
    ax.set_xlabel('Reaction class'); ax.set_ylim(0, 100)
    ax.set_ylabel('Recorded product found (%)')
    save(fig, 'fig6_forward_class')

def fig7():
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6))
    ax = axes[0]
    caps = [8, 32, 64]
    ax.plot(caps, [60.0, 64.6, 64.6], 'o-', ms=4, lw=1.1, color=C_ALT, label='sweet-spot pool (3k/1.5k)')
    ax.plot(caps, [59.4, 75.8, 75.8], 's-', ms=4, lw=1.3, color=C_MAIN, label='full pool (20k/6k)')
    for x, y in zip(caps, [60.0, 64.6, 64.6]):
        ax.annotate('%.1f' % y, (x, y), textcoords='offset points', xytext=(0, 6), fontsize=6.5, ha='center')
    for x, y in zip(caps, [59.4, 75.8, 75.8]):
        ax.annotate('%.1f' % y, (x, y), textcoords='offset points', xytext=(0, -11), fontsize=6.5, ha='center')
    ax.set_xticks(caps); ax.set_xlabel('Candidates kept per substrate-template pair')
    ax.set_ylabel('Single-step any-hit (%)'); ax.set_ylim(55, 82)
    ax.legend(frameon=False, loc='lower right')
    ax.text(-0.18, 1.04, 'A', transform=ax.transAxes, fontsize=10, fontweight='bold')

    ax = axes[1]
    xs = [2, 3]; ys = [47.67, 72.33]
    err = [[47.67 - 42.08, 72.33 - 67.01], [53.31 - 47.67, 77.09 - 72.33]]
    ax.errorbar(xs, ys, yerr=err, fmt='o-', ms=4, lw=1.3, capsize=3, color=C_MAIN)
    ax.scatter([2], [46.0], marker='x', s=18, color='#777777', label='n=100 pilot')
    for x, y in zip(xs, ys):
        ax.annotate('%.1f%%' % y, (x, y), textcoords='offset points', xytext=(8, 4), fontsize=7)
    ax.set_xticks(xs); ax.set_xlim(1.7, 3.3)
    ax.set_xlabel('Search depth (beam = 4)'); ax.set_ylabel('End-to-end success (%)')
    ax.set_ylim(35, 85); ax.legend(frameon=False, loc='upper left')
    ax.text(-0.18, 1.04, 'B', transform=ax.transAxes, fontsize=10, fontweight='bold')
    fig.tight_layout()
    save(fig, 'fig7_truncation_multistep')

for f in (fig1, fig2, fig3, fig4, fig5, fig6, fig7):
    try:
        f()
    except Exception as e:
        print('  FAILED', f.__name__, type(e).__name__, e)
print('done ->', FIG)

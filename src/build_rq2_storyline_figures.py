#!/usr/bin/env python3
'Draw Figures 3 and 4: reliability minus ranking recovery, and stopping.\n\nThe data columns use B2 for the simpler Bayesian model and B1 for the full model. Figure labels follow the manuscript. F1 uses the exploratory comparison window from 6 to 16 comparisons per essay.'
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

from build_results_figures import (
    BUDGETS, ESTIMATORS, STRATEGIES, STYLE,
    load_inputs, number, require, style, plt,
)




MANUSCRIPT_PANELS = (('B2', 'B1'), ('B1', 'B2'), ('F1', 'F1'))


def discrepancy_figure(data):
    'Plot reliability minus recovery; show the exploratory F1 window from 6 to 16 comparisons per essay.'
    fig, axes = plt.subplots(1, 3, figsize=(7.35, 3.35), sharey=True)
    fig.subplots_adjust(left=.085, right=.987, bottom=.20, top=.78, wspace=.18)
    audited = []
    for ax, (estimator, manuscript_label) in zip(axes, MANUSCRIPT_PANELS):
        budgets = BUDGETS if estimator != 'F1' else BUDGETS[2:]
        ax.axhline(0, color='.45', lw=.7, zorder=0)
        for strategy in STRATEGIES:
            color, marker, linestyle, label = STYLE[strategy]
            rows = [data['curves'][('RQ2', estimator, strategy, str(b))] for b in budgets]
            y = np.array([number(r, 'estimate') for r in rows])
            lo = np.array([number(r, 'ci95_low') for r in rows])
            hi = np.array([number(r, 'ci95_high') for r in rows])
            assert np.all(lo <= y) and np.all(y <= hi)
            
            
            line, = ax.plot(
                budgets, y, color=color, ls=linestyle, lw=1.6,
                label=label, zorder=3)
            np.testing.assert_array_equal(line.get_xdata(), budgets)
            np.testing.assert_array_equal(line.get_ydata(), y)
            for b, r in zip(budgets, rows):
                audited.append((estimator, strategy, b, r['estimate'], r['ci95_low'], r['ci95_high']))
        ax.set_title(f'{manuscript_label} ({"SSR" if estimator == "F1" else "EAP"} $- R^2$)', loc='left', pad=9)
        ax.set_xticks(budgets)
        ax.set_xlim(min(budgets)-.6, 16.6)
        ax.set_ylim(-.385, .052)
        ax.set_yticks((-.3, -.2, -.1, 0.))
        ax.set_xlabel('Comparisons per essay ($B$)')
        ax.tick_params(axis='both', length=3)
    axes[0].set_ylabel('Internal reliability $- R^2$')
    handles = [Line2D([], [], color=STYLE[s][0], ls=STYLE[s][2], lw=1.6,
                      label={'random':'Random','p50':'p50','pollitt':'Pollitt','hybrid':'Hybrid'}[s])
               for s in STRATEGIES]
    fig.legend(handles=handles, ncol=4, loc='upper center', bbox_to_anchor=(.53,.985),
               frameon=False, fontsize=7.7, handlelength=2.7, columnspacing=1.6)
    require(len(audited) == 88, 'RQ2 discrepancy must show 88 preverified curve rows')
    return fig, audited


def stopping_figure(data):
    'Plot premature stopping and recovery before stopping at both reliability thresholds, using only defined rates.'
    fig, axes = plt.subplots(2, 2, figsize=(7.35, 6.05),
                            gridspec_kw={'height_ratios': [1.0, 2.5]})
    fig.subplots_adjust(left=.205, right=.965, bottom=.115, top=.94,
                        wspace=.18, hspace=.42)
    audited = []
    strategy_names = {'random':'Random', 'p50':'p50', 'pollitt':'Pollitt', 'hybrid':'Hybrid'}
    for j, threshold in enumerate(('0.9', '0.7')):
        ax = axes[0, j]
        for i, strategy in enumerate(STRATEGIES):
            row = data['stopping'][(threshold, 'premature_stop', 'F1', strategy)]
            require(row['rate'] != '' and int(row['n_observed']) > 0,
                    'All plotted F1 premature rates must be defined')
            rate = number(row, 'rate')
            ax.plot(rate, i, marker=STYLE[strategy][1], color=STYLE[strategy][0],
                    markersize=5.0, linestyle='none')
            audited.append((threshold, 'premature_stop', 'F1', strategy, row['rate'], row['n_observed']))
        ax.set_yticks(range(4), [strategy_names[s] for s in STRATEGIES] if j==0 else [])
        ax.set_ylim(3.55, -.55)
        ax.set_xlim(-.012, .405)
        ax.set_xticks((0,.1,.2,.3,.4))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v,pos:f'{v*100:.0f}%'))
        ax.set_title(('A.' if j==0 else 'B.') + f' Premature stops ({float(threshold):.2f})', loc='left')
        ax.tick_params(axis='both', length=3)
        ax.axvline(0, lw=.55, color='.8', zorder=0)
        ax.set_xlabel('Among observed F1 stops', fontsize=7.5)
        if j==0:ax.set_ylabel('Pair selection')

        ax = axes[1, j]
        labels = []
        ys = []
        for e_idx, (estimator, manuscript_label) in enumerate(MANUSCRIPT_PANELS):
            for s_idx, strategy in enumerate(STRATEGIES):
                y = e_idx*5 + s_idx
                row = data['stopping'][(threshold, 'readiness_without_stopping', estimator, strategy)]
                require(row['rate'] != '' and int(row['n_observed']) > 0,
                        'All plotted readiness-before-stop rates must be defined')
                ax.plot(number(row,'rate'), y, marker=STYLE[strategy][1],
                        color=STYLE[strategy][0], markersize=4.5, linestyle='none')
                labels.append(manuscript_label + ' ' + strategy_names[strategy])
                ys.append(y)
                audited.append((threshold, 'readiness_without_stopping', estimator, strategy,
                                row['rate'], row['n_observed']))
        ax.set_yticks(ys, labels if j==0 else [])
        ax.set_ylim(13.55,-.55)
        ax.set_xlim(-.02,1.05)
        ax.set_xticks((0,.25,.5,.75,1))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v,pos:f'{v*100:.0f}%'))
        for y in (3.5,8.5):ax.axhline(y, lw=.5, color='.8')
        ax.set_title(('C.' if j==0 else 'D.') + f' Recovery before stop ({float(threshold):.2f})', loc='left')
        ax.tick_params(axis='both', length=3)
        ax.axvline(0, lw=.55, color='.8', zorder=0)
        ax.set_xlabel('Among trajectories attaining recovery', fontsize=7.5)
    require(len(audited) == 32,'RQ2 stopping must display 32 defined conditional rates')
    return fig,audited


def output_figure(fig, stem, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    for ext in ('pdf','svg','png'):
        path=output_dir/(stem+'.'+ext)
        if ext=='pdf':metadata={'Creator':'D153 verified RQ2 display','CreationDate':None,'ModDate':None}
        elif ext=='svg':metadata={'Creator':'D153 verified RQ2 display','Date':None}
        else:metadata={'Software':'D153 verified RQ2 display'}
        fig.savefig(path,dpi=300,metadata=metadata)
        if ext=='svg':path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,default=Path('data/primary'))
    parser.add_argument('--posthoc-dir',type=Path,default=Path('data/ssr'))
    parser.add_argument('--output-dir',type=Path,default=Path('output/figures'))
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    data=load_inputs(args.input_dir,args.posthoc_dir)
    style()
    plt.rcParams['svg.hashsalt']='JEM-RQ2-storyline-2026-10-26'
    gap,gap_records=discrepancy_figure(data)
    stop,stop_records=stopping_figure(data)
    if not args.verify_only:
        output_figure(gap,'figure_rq2_gap_main',args.output_dir)
        output_figure(stop,'figure_rq2_timing_main',args.output_dir)
    else:
        plt.close(gap);plt.close(stop)
    print(f'PASS: {len(gap_records)} RQ2 gap rows (F1 B6-B16), '
          f'{len(stop_records)} conditional stopping rates (both thresholds).')


if __name__=='__main__':
    main()

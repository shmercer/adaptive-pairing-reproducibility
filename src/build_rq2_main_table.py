#!/usr/bin/env python3
'Make Table 2 from checked reliability contrasts.\n\nBayesian results use 2–16 comparisons per essay. The exploratory F1 results use 6–16 because its reliability estimate was unstable at the earlier checkpoints. Holm adjustment accounts for all six displayed tests together.'
from __future__ import annotations

import argparse
from pathlib import Path

from table_common import (
    verified_csv, validate, table, group, row_tex, contrast_label,
)

ROOT = Path(__file__).resolve().parents[1]
COMPARATORS = ('random', 'pollitt', 'hybrid')


def holm_adjusted(p_values: list[float]) -> list[float]:
    "Adjust the six displayed p values together using Holm's step-down method."
    if len(p_values) != 6 or any(not 0 <= p <= 1 for p in p_values):
        raise ValueError('Expected exactly six valid raw p values')
    result = [0.0] * len(p_values)
    maximum = 0.0
    for rank, index in enumerate(sorted(range(len(p_values)), key=p_values.__getitem__)):
        maximum = max(maximum, (len(p_values) - rank) * p_values[index])
        result[index] = min(1.0, maximum)
    return result


def render(input_dir: Path, posthoc_dir: Path) -> str:
    original = verified_csv(input_dir, 'rq2.csv')
    supplemental = verified_csv(posthoc_dir, 'contrasts.csv')
    validate(original, 3)
    validate(supplemental, 3)

    bayesian = [
        next(r for r in original if r['contrast_id'] == f'Bayesian:p50-{s}')
        for s in COMPARATORS
    ]
    f1 = [
        next(r for r in supplemental
             if r['window'] == 'B6-B16' and r['contrast_id'] == f'p50-{s}')
        for s in COMPARATORS
    ]
    rows = bayesian + f1
    adjusted = holm_adjusted([float(r['p_value']) for r in rows])

    def format_row(index: int, strategy: str) -> str:
        
        
        display_row = dict(rows[index], display_holm_p=round(adjusted[index], 3))
        return row_tex(display_row, pcol='display_holm_p',
                       label=contrast_label(f'p50-{strategy}'))

    body = [group('Bayesian EAP: $B=2$--16 (equal B1/B2 average)')]
    body.extend(format_row(i, s) for i, s in enumerate(COMPARATORS))
    body += [r'\addlinespace', group('F1 SSR: $B=6$--16')]
    body.extend(format_row(i + 3, s) for i, s in enumerate(COMPARATORS))

    note = (
        r'Each contrast is p50 minus the indicated alternative in the integrated '
        r'signed discrepancy (internal reliability $-R^2$). The Bayesian rows '
        r'average B1 and B2 equally over all eight budgets ($B=2$--16). '
        r'The F1 rows use a post hoc $B=6$--16 window because SSR was '
        r'unstable at $B=2$ (271/384 negative) and $B=4$ (3/384 negative).'
    )
    return table('Differences in Signed Reliability--Recovery Discrepancy (RQ2)',
                 'tab:rq2-main', body, note, pheader=r'$p_{\mathrm{Holm}}$')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-dir', type=Path,
                   default=ROOT / 'data/primary')
    p.add_argument('--posthoc-dir', type=Path,
                   default=ROOT / 'data/ssr')
    p.add_argument('--output', type=Path,
                   default=ROOT / 'output/tables/table_rq2_main.tex')
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    result = render(args.input_dir, args.posthoc_dir)
    if args.check:
        if args.output.read_text() != result:
            raise ValueError('stale RQ2 main table')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result)
    print('PASS: RQ2 main table sourced from verified D153 releases')


if __name__ == '__main__':
    main()

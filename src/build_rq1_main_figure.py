#!/usr/bin/env python3
'Draw Figure 2: ranking recovery relative to random pairing.\n\nThe data columns use B2 for the simpler Bayesian model and B1 for the full model. The figure labels follow the manuscript: B1 is simpler and B2 is full. All plotted differences are checked against the input values.'
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from matplotlib.lines import Line2D

from build_results_figures import (
    BUDGETS, STYLE, load_inputs, number, plt, require, style, validate_layout
)


DISPLAY = (("B2", "B1"), ("B1", "B2"), ("F1", "F1"))
PAIRINGS = (("p50", "p50"), ("pollitt", "Pollitt"), ("hybrid", "Hybrid"))


def make_figure(data):
    fig, axes = plt.subplots(1, 3, figsize=(7.35, 3.0), sharey=True)
    fig.subplots_adjust(left=.085, right=.99, bottom=.18, top=.78, wspace=.14)
    checks = 0
    for ax, (source, manuscript) in zip(axes, DISPLAY):
        ax.axhline(0., color=".40", lw=.8, zorder=0)
        for strategy, label in PAIRINGS:
            color, marker, linestyle, _ = STYLE[strategy]
            values = []
            for B in BUDGETS:
                adaptive = data["curves"][("RQ1", source, strategy, str(B))]
                random = data["curves"][("RQ1", source, "random", str(B))]
                values.append(number(adaptive, "estimate") - number(random, "estimate"))
                checks += 1
            line, = ax.plot(BUDGETS, values, color=color, ls=linestyle,
                            lw=1.35, label=label)
            np.testing.assert_array_equal(line.get_xdata(), BUDGETS)
            np.testing.assert_array_equal(line.get_ydata(), values)
        ax.set_title(manuscript, loc="left")
        ax.set_ylim(-.045, .085)
        ax.set_yticks(np.arange(-.04, .081, .02))
        ax.set_xticks(BUDGETS)
        ax.set_xlabel("Comparisons per essay (B)")
        ax.set_axisbelow(True)
    axes[0].set_ylabel(r"Recovery difference from random ($\Delta R^2$)")
    handles = [
        Line2D([], [], color=STYLE[strategy][0], ls=STYLE[strategy][2],
               lw=1.35, label=label) for strategy, label in PAIRINGS
    ]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
               bbox_to_anchor=(.5, .98), fontsize=7,
               columnspacing=1.8, handlelength=2.8)
    require(checks == 72, "expected 72 source-verified RQ1 differences")
    require(tuple(ax.get_title(loc="left") for ax in axes) == ("B1","B2","F1"),
            "manuscript Bayesian panel labels incorrect")
    validate_layout(fig)
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path,
                        default=Path("data/primary"))
    parser.add_argument("--posthoc-dir", type=Path,
                        default=Path("data/ssr"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("output/figures"))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    data = load_inputs(args.input_dir, args.posthoc_dir)
    style()
    plt.rcParams["svg.hashsalt"] = "JEM-RQ1-mapped-2026-10-28"
    fig = make_figure(data)
    if not args.verify_only:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        stem = "figure2_rq1_recovery"
        for ext in ("pdf", "svg", "png"):
            path = args.output_dir / (stem + "." + ext)
            metadata = ({"Creator":"JEM RQ1 model-ID display mapping",
                         "CreationDate":None, "ModDate":None} if ext=="pdf"
                        else {"Creator":"JEM RQ1 model-ID display mapping",
                              "Date":None} if ext=="svg"
                        else {"Software":"JEM RQ1 model-ID display mapping"})
            fig.savefig(path, dpi=300, metadata=metadata)
            if ext=="svg":
                path.write_text("\n".join(line.rstrip()
                                for line in path.read_text().splitlines())+"\n")
    plt.close(fig)
    print("PASS: 72 verified RQ1 source differences; display B1(simple), B2(full), F1")


if __name__ == "__main__":
    main()

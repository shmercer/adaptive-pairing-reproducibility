#!/usr/bin/env python3
'Make Table 3 from checked estimator results. Verify the 30-test Holm adjustment before displaying means and significant differences.'
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/estimator"
OUTPUT = ROOT / "output/tables/table_rq3_main.tex"
ESTIMATORS = ("B1", "B2", "F1", "F2", "F3")
STRATEGIES = ("random", "p50", "pollitt", "overall")
OUTCOMES = (
    ("R2", r"Dense-reference recovery ($R^2$; higher is better)"),
    ("log_loss", "Held-out log loss (lower is better)"),
    ("spread_error", "Absolute spread error (lower is better)"),
)
NOTE = (
    "Values are means across comparison budgets $B=4$, 8, and 16; overall "
    "values are means across the nine strategy-by-budget conditions. The final "
    "column identifies which estimators each model significantly outperformed "
    "overall, using Holm adjustment across 30 tests ($p<.05$). A dash "
    "indicates no significant advantage over another estimator. "
    "B1 = simpler Bayesian; B2 = full Bayesian; "
    "F1 = conventional frequentist; F2 = alpha-adjusted frequentist; "
    "F3 = bootstrap-corrected F2. Recovery and spread error are relative to "
    "each estimator's own dense reference."
)


def verified_csv(directory: Path, name: str) -> list[dict[str, str]]:
    hashes: dict[str, str] = {}
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        expected, filename = line.split(maxsplit=1)
        filename = filename.lstrip("*")
        if filename in hashes:
            raise ValueError(f"duplicate SHA256SUMS entry: {filename}")
        hashes[filename] = expected
    if name not in hashes:
        raise ValueError(f"unverified source: {name}")
    path = directory / name
    if hashlib.sha256(path.read_bytes()).hexdigest() != hashes[name]:
        raise ValueError(f"source SHA-256 mismatch: {name}")
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def checked_data(directory: Path):
    absolute = verified_csv(directory, "absolute_performance.csv")
    tests = verified_csv(directory, "rq3_holm30.csv")
    if len(absolute) != 60 or len(tests) != 30:
        raise ValueError("expected 60 descriptive rows and 30 inferential rows")

    means = {}
    for r in absolute:
        key = (r["outcome"], r["manuscript_estimator"], r["strategy"])
        if key in means or not math.isfinite(float(r["absolute_mean"])):
            raise ValueError(f"duplicate/nonfinite absolute mean: {key}")
        if (r["n_prompts"], r["n_cells"]) != ("16", "96"):
            raise ValueError(f"incomplete absolute support: {key}")
        means[key] = float(r["absolute_mean"])
    expected_means = set(itertools.product(
        [x for x, _ in OUTCOMES], ESTIMATORS, STRATEGIES))
    if set(means) != expected_means:
        raise ValueError("unexpected absolute performance coverage")
    for outcome, _ in OUTCOMES:
        for model in ESTIMATORS:
            a, b, c = (means[(outcome, model, s)] for s in STRATEGIES[:3])
            if abs(means[(outcome, model, "overall")] - (a + b + c)/3) > 1e-12:
                raise ValueError("overall mean is not the equal-strategy mean")

    pairs = {tuple(sorted(x)) for x in itertools.combinations(ESTIMATORS, 2)}
    expected_tests = set(itertools.product([x for x, _ in OUTCOMES], pairs))
    seen = set()
    for r in tests:
        pair = tuple(sorted((r["manuscript_first"], r["manuscript_second"])))
        key = (r["outcome"], pair)
        if key in seen or pair not in pairs:
            raise ValueError(f"duplicate/unexpected estimator comparison: {key}")
        seen.add(key)
        if (r["family"], r["n_prompts"], r["n_cells"], r["status"]) != (
            "Holm-30", "16", "96", "estimable"
        ):
            raise ValueError(f"wrong family or support: {key}")
        estimate = float(r["estimate"])
        p = float(r["p_value"])
        p_adjusted = float(r["p_holm30"])
        if not (math.isfinite(estimate) and math.isfinite(p)
                and 0 <= p <= p_adjusted <= 1):
            raise ValueError(f"invalid inference: {key}")
        first_wins = estimate > 0 if r["outcome"] == "R2" else estimate < 0
        favored = r["manuscript_first"] if first_wins else r["manuscript_second"]
        if favored != r["favored_manuscript_estimator"]:
            raise ValueError(f"estimator direction mismatch: {key}")
    if seen != expected_tests:
        raise ValueError("incomplete Holm-30 family")

    order = sorted(range(30), key=lambda i: float(tests[i]["p_value"]))
    cumulative = 0.0
    checked = [0.0] * 30
    for rank, index in enumerate(order):
        cumulative = min(1.0, max(cumulative, (30-rank) * float(tests[index]["p_value"])))
        checked[index] = cumulative
    for i, r in enumerate(tests):
        if abs(checked[i] - float(r["p_holm30"])) > 1e-12:
            raise ValueError("Holm-30 adjusted p values do not reproduce")
    return means, tests


def number(value: float) -> str:
    s = f"{value:.3f}"
    return s[1:] if s.startswith("0.") else s


def render(directory: Path) -> str:
    means, tests = checked_data(directory)
    lines = [
        "% Generated by build_rq3_main_table.py from SHA-verified D155 aggregates. Do not edit by hand.",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Estimator Performance by Pairing Strategy}",
        r"\label{tab:rq3-main}",
        r"\small",
        r"\setlength{\tabcolsep}{3.5pt}",
        r"\begin{tabular}{@{}lrrrrl@{}}",
        r"\toprule",
        r"Estimator & Random & p50 & Pollitt & Overall & \shortstack[l]{Significantly\\better than} \\",
        r"\midrule",
    ]
    for k, (outcome, heading) in enumerate(OUTCOMES):
        if k:
            lines.append(r"\addlinespace[4pt]")
        lines.append(r"\multicolumn{6}{@{}l}{\textit{" + heading + r"}} \\")
        for model in ESTIMATORS:
            values = [number(means[(outcome, model, s)]) for s in STRATEGIES]
            better = sorted((
                r["manuscript_second"] if r["manuscript_first"] == model
                else r["manuscript_first"]
                for r in tests if r["outcome"] == outcome
                and float(r["p_holm30"]) < .05
                and r["favored_manuscript_estimator"] == model
            ), key=ESTIMATORS.index)
            lines.append(" & ".join([
                model, *values, ", ".join(better) if better else r"\textemdash"
            ]) + r" \\")
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\par\smallskip",
        r"\begin{minipage}{\linewidth}",
        r"\footnotesize",
        r"\textit{Note.} " + NOTE,
        r"\end{minipage}",
        r"\end{table}",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=INPUT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render(args.input_dir)
    if args.check:
        if not args.output.exists() or args.output.read_text() != expected:
            raise SystemExit("RQ3 table differs from verified D155 data")
        print("RQ3 main table: PASS")
    else:
        args.output.write_text(expected)
        print(f"RQ3 main table generated: {args.output}")


if __name__ == "__main__":
    main()

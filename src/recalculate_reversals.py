#!/usr/bin/env python3
'Summarize judgments repeated with the essay order reversed.\n\nCheck whether the same essay wins and whether both judgments favor the same presentation position. These are descriptive results; they do not estimate a causal effect of position or agreement under identical presentation.'
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
import validate_observations as observations

CELL_FIELDS = ("cell_id", "prompt_id", "trait", "n_pairs", "n_same_winner",
               "n_changed_winner", "n_both_first", "n_both_second",
               "n_base_first", "n_reversal_first", "same_winner_rate",
               "first_preferred_rate", "first_original_rate",
               "first_reversed_rate", "both_first_given_change")
PROMPT_FIELDS = ("prompt_id", "n_cells", "n_pairs", "same_winner_rate",
                 "first_preferred_rate", "first_original_rate",
                 "first_reversed_rate")
OVERALL_FIELDS = ("n_pairs", "n_presentations", "n_prompts", "n_cells",
                  "n_same_winner", "n_changed_winner", "n_both_first",
                  "n_both_second", "n_base_first", "n_reversal_first",
                  "n_first_preferred", "same_winner_rate",
                  "first_preferred_rate", "first_original_rate",
                  "first_reversed_rate", "both_first_given_change",
                  "both_second_given_change", "same_winner_prompt_equal",
                  "first_preferred_prompt_equal", "first_original_prompt_equal",
                  "first_reversed_prompt_equal")


def need(ok, message):
    if not ok:
        raise ValueError(message)


def classify(original_first_wins: str, reversed_first_wins: str) -> str:
    'Identify whether the same essay wins after its presentation position is reversed.'
    need(original_first_wins in ("0", "1") and
         reversed_first_wins in ("0", "1"),
         "Invalid first-wins orientation")
    if original_first_wins != reversed_first_wins:
        return "same_winner"
    return "both_first" if original_first_wins == "1" else "both_second"


def proportion(numer, denom):
    return numer / denom if denom else math.nan


def summarize_counts(c):
    n = c["n_pairs"]
    need(n > 0, "Missing reversal events in cell")
    same = c["n_same_winner"]
    bf, bs = c["n_both_first"], c["n_both_second"]
    changed = n - same
    need(changed == bf + bs and n == same + bf + bs,
         "Reversal classifications do not partition observations")
    base, reversed_ = c["n_base_first"], c["n_reversal_first"]
    need(base + reversed_ == same + 2 * bf,
         "First-preferred identity does not reconcile")
    return dict(n_pairs=n, n_same_winner=same,
                n_changed_winner=changed, n_both_first=bf,
                n_both_second=bs, n_base_first=base,
                n_reversal_first=reversed_,
                same_winner_rate=same / n,
                first_preferred_rate=(base + reversed_) / (2 * n),
                first_original_rate=base / n,
                first_reversed_rate=reversed_ / n,
                both_first_given_change=proportion(bf, changed))


def mean(rows, field):
    need(rows, "Empty reversal aggregation")
    vals = [float(r[field]) for r in rows]
    need(all(math.isfinite(v) for v in vals),
         "Nonfinite six-trait prompt reversal summary")
    return math.fsum(vals) / len(vals)


def calculate(root: Path, *, verify=True):
    root = root.expanduser().resolve()
    if verify:
        observations.validate(root)
    design = {}
    for d in observations.rows(root / "data/design/cells.csv",
                               observations.CELL_COLUMNS):
        ci = int(d["cell_id"])
        design[ci] = (d["prompt_id"], d["trait"], int(d["n_reversal"]))
    need(len(design) == 96, "Missing original 96 cells")

    reversed_by_cell = defaultdict(dict)
    for r in observations.rows(root / "data/judgments/reversals.csv",
                               observations.REV_COLUMNS):
        ci, pair_id = int(r["cell_id"]), r["base_pair_id"]
        need(ci in design and pair_id not in reversed_by_cell[ci],
             "Unknown or duplicate reversal base pair")
        reversed_by_cell[ci][pair_id] = r["first_wins"]

    cell_results = []
    for ci in sorted(design):
        prompt, trait, expected_pairs = design[ci]
        lookup = reversed_by_cell[ci]
        counts = Counter()
        for b in observations.rows(root / f"data/judgments/cell_{ci:03d}.csv",
                                   observations.BASE_COLUMNS):
            original = b["first_wins"]
            reversed_winner = lookup.get(b["pair_id"])
            if reversed_winner is None:
                continue
            outcome = classify(original, reversed_winner)
            counts["n_pairs"] += 1
            counts["n_" + outcome] += 1
            counts["n_base_first"] += int(original)
            counts["n_reversal_first"] += int(reversed_winner)
        need(counts["n_pairs"] == expected_pairs ==
             len(reversed_by_cell[ci]),
             "Per-cell matched original/reversed event count differs")
        cell_results.append(dict(cell_id=ci, prompt_id=prompt, trait=trait,
                                 **summarize_counts(counts)))

    by_prompt = defaultdict(list)
    for row in cell_results:
        by_prompt[row["prompt_id"]].append(row)
    prompt_results = []
    for prompt in sorted(by_prompt):
        z = by_prompt[prompt]
        need(len(z) == 6 and len({x["trait"] for x in z}) == 6,
             "Six distinct traits required per prompt")
        prompt_results.append(dict(
            prompt_id=prompt, n_cells=len(z),
            n_pairs=sum(r["n_pairs"] for r in z),
            **{key: mean(z, key)
               for key in ("same_winner_rate", "first_preferred_rate",
                           "first_original_rate", "first_reversed_rate")}))

    counts = {key: sum(row[key] for row in cell_results)
              for key in ("n_pairs", "n_same_winner", "n_changed_winner",
                          "n_both_first", "n_both_second",
                          "n_base_first", "n_reversal_first")}
    need(counts["n_pairs"] == 33858 and len(prompt_results) == 16 and
         len(cell_results) == 96, "Frozen W011 reversal sample differs")
    n = counts["n_pairs"]
    first = counts["n_base_first"] + counts["n_reversal_first"]
    overall = dict(
        n_presentations=2 * n,
        n_prompts=len(prompt_results), n_cells=len(cell_results),
        **counts,
        n_first_preferred=first,
        same_winner_rate=counts["n_same_winner"] / n,
        first_preferred_rate=first / (2 * n),
        first_original_rate=counts["n_base_first"] / n,
        first_reversed_rate=counts["n_reversal_first"] / n,
        both_first_given_change=proportion(
            counts["n_both_first"], counts["n_changed_winner"]),
        both_second_given_change=proportion(
            counts["n_both_second"], counts["n_changed_winner"]),
        **{out_name: mean(prompt_results, metric)
           for out_name, metric in (
               ("same_winner_prompt_equal", "same_winner_rate"),
               ("first_preferred_prompt_equal", "first_preferred_rate"),
               ("first_original_prompt_equal", "first_original_rate"),
               ("first_reversed_prompt_equal", "first_reversed_rate"))})
    need(first == counts["n_same_winner"] + 2 * counts["n_both_first"],
         "Original/reversed first-preferred algebra differs")
    need(set(overall) == set(OVERALL_FIELDS) and
         all(set(row) == set(CELL_FIELDS) for row in cell_results) and
         all(set(row) == set(PROMPT_FIELDS) for row in prompt_results),
         "Reversal summary output schemas diverge from the frozen analysis")
    verify_reported(overall)
    return overall, cell_results, prompt_results


def verify_reported(overall):
    need(overall["n_pairs"] == 33858 and overall["n_same_winner"] == 24704 and
         overall["n_both_first"] == 8642 and overall["n_presentations"] == 67716,
         "Reported reversal counts differ from the manuscript")
    need(math.isclose(overall["first_preferred_rate"],
                      overall["n_first_preferred"] / overall["n_presentations"],
                      rel_tol=0, abs_tol=1e-15),
         "Paired-presentation first-position rate uses the wrong count or denominator")
    for field, expected in (("same_winner_rate", "73.0"),
                            ("both_first_given_change", "94.4"),
                            ("first_preferred_rate", "62.0")):
        need(f"{100 * overall[field]:.1f}" == expected,
             f"{field} differs from the manuscript at reported precision")


def write(path, columns, records):
    with path.open("w", newline="", encoding="utf-8") as stream:
        w = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        w.writeheader()
        w.writerows(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path,
                        default=Path("observations"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    root = args.data_root.expanduser().resolve()
    need(not output.exists() and output.parent.is_dir() and
         not output.is_relative_to(root),
         "Use a new output directory outside the observation inputs")
    summary, cells, prompts = calculate(root)
    output.mkdir(mode=0o700)
    write(output / "reversal_overall.csv", OVERALL_FIELDS, [summary])
    write(output / "reversal_cells.csv", CELL_FIELDS, cells)
    write(output / "reversal_prompts.csv", PROMPT_FIELDS, prompts)
    (output / "README.txt").write_text(
        "Descriptive rates for the original and reversed essay order.\n"
        "same_winner=the same essay was selected after swapping positions.\n"
        "both_first/both_second=both judgments favor the same position.\n"
        "prompt_equal=average of six trait rates per prompt, then 16 prompts.\n"
        "first_preferred_rate uses only the matched original/reversed pairs.\n"
        "This is NOT an identical-presentation test/retest or a causal\n"
        "estimate of presentation-position effects.\n",
        encoding="utf-8")
    print("PASS: Reconstructed reversal summaries from 33858 matched "
          "outcome pairs in 96 cells and 16 prompts")
    print("PASS: Same-winner and both-first/both-second classes reconcile "
          "with original/reversed position preferences")
    print("PASS: Reported reversal counts and percentages; first-position preference within the matched pairs")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"Check Table 4 using correlations summarized within each writing prompt.\n\nFisher's z transformation puts correlations on a scale suitable for averaging. When prompt summaries are supplied, the script recalculates intervals across the 16 prompts and checks the displayed table values. It writes a numerical summary without requiring individual human ratings or essay scores."
from __future__ import annotations

import csv
import math
import re
import shutil
import statistics
from pathlib import Path

ESTIMATORS = ("B1", "B2", "F1", "F2", "F3")
T_975_DF15 = 2.131449545559323  
FIELDS = (
    "estimator", "b16_r", "b16_low", "b16_high",
    "dense_r", "dense_low", "dense_high",
    "dense_minus_b16", "gap_low", "gap_high",
)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields=FIELDS):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def interval(z):
    check(len(z) == 16 and all(math.isfinite(v) for v in z),
          "Expected 16 finite independent prompt-level z values")
    center = statistics.mean(z)
    radius = T_975_DF15 * statistics.stdev(z) / 4
    return math.tanh(center), math.tanh(center-radius), math.tanh(center+radius)


def paired_interval(z_b, z_d):
    check(len(z_b) == len(z_d) == 16, "Expected 16 matched prompts")
    mb, md = statistics.mean(z_b), statistics.mean(z_d)
    rb, rd = math.tanh(mb), math.tanh(md)
    influence = [(1-rd**2)*(d-md) - (1-rb**2)*(b-mb)
                 for b, d in zip(z_b, z_d)]
    gap = rd-rb
    radius = T_975_DF15 * statistics.stdev(influence) / 4
    return gap, gap-radius, gap+radius


def calculate(prompt_rows):
    check(len(prompt_rows) == 160,
          "Expected five estimators x two reference types x 16 prompts")
    grouped = {}
    for row in prompt_rows:
        key = row["estimator"], row["reference_type"]
        prompt = row["prompt"]
        check(key[0] in ESTIMATORS and key[1] in ("B16", "dense"),
              f"Unexpected estimator or reference: {key}")
        val = float(row["pearson_z"])
        check(math.isfinite(val), "Nonfinite Fisher-z correlation")
        grouped.setdefault(key, {})
        check(prompt not in grouped[key], f"Duplicate prompt within {key}")
        grouped[key][prompt] = val
    output = []
    for e in ESTIMATORS:
        b, d = grouped[e, "B16"], grouped[e, "dense"]
        check(len(b) == len(d) == 16 and set(b) == set(d),
              f"Missing or unmatched prompts for {e}")
        keys = sorted(b)
        zb, zd = [b[k] for k in keys], [d[k] for k in keys]
        br, bl, bh = interval(zb)
        dr, dl, dh = interval(zd)
        gap, gl, gh = paired_interval(zb, zd)
        output.append(dict(zip(FIELDS, (
            e, br, bl, bh, dr, dl, dh, gap, gl, gh
        ))))
    return output


def verify_summary(rows, expected):
    check(len(rows) == len(expected) == 5, "Incomplete human-score summary")
    for row, published in zip(rows, expected):
        check(row["estimator"] == published["estimator"],
              "Manuscript estimator mapping changed")
        for name in FIELDS[1:]:
            
            check(abs(float(row[name])-float(published[name])) <= 0.000002,
                  f"{row['estimator']} {name} differs from reviewed summary")


def verify_table(rows, table_path):
    'Check every displayed Table 4 value against the calculated results.'
    displayed = {}
    for line in Path(table_path).read_text(encoding="utf-8").splitlines():
        if re.match(r"^(B[12]|F[123])\s*&", line):
            label, values = line.split("&", 1)
            label = label.strip()
            check(label not in displayed, "Duplicate estimator in Table 4")
            displayed[label] = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", values)
    check(set(displayed) == set(ESTIMATORS), "Incomplete Table 4 estimator rows")
    check(len(rows) == 5 and {r["estimator"] for r in rows} == set(ESTIMATORS),
          "Incomplete calculated Table 4 results")
    for row in rows:
        expected = [f"{float(row[field]):.3f}" for field in FIELDS[1:]]
        actual = displayed[row["estimator"]]
        check(len(actual) == 9 and
              [f"{float(value):.3f}" for value in actual] == expected,
              f"Table 4 displayed values differ from calculation: {row['estimator']}")


def reproduce(data_dir, output_dir):
    data_dir, output_dir = Path(data_dir), Path(output_dir)
    expected = read_csv(data_dir / "human_summary.csv")
    prompt_path = data_dir / "human_prompt_z.csv"
    if prompt_path.is_file():
        result = calculate(read_csv(prompt_path))
        verify_summary(result, expected)
        status = "PASS: Table 4: all 45 displayed values checked against recalculated prompt summaries"
    else:
        result = expected
        print("NOTE: Human correlations are from the reviewed five-row "
              "summary only; independent CI reproduction needs human_prompt_z.csv")
        status = "SUMMARY ONLY: Table 4 checked against supplied summary; prompt data unavailable"
    verify_table(result, data_dir / "table_rq3_human.tex")
    write_csv(output_dir / "human_correlations.csv",
              [{k: v if k == "estimator" else f"{float(v):.9f}"
                for k, v in row.items()} for row in result])
    shutil.copyfile(data_dir / "table_rq3_human.tex", output_dir / "table_rq3_human.tex")
    (output_dir / "human_table_verification.txt").write_text(status + "\n", encoding="utf-8")
    print(status)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("output/tables"))
    args = parser.parse_args()
    reproduce(args.data_dir, args.output_dir)

'Check input hashes, comparison coverage and figure layout. Share the plotting style used in Figures 2–4.'

from __future__ import annotations

import argparse

import csv

import hashlib

import itertools

import json

import math

import os

from pathlib import Path

import platform

import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "d153c-matplotlib"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from matplotlib.lines import Line2D

import numpy as np

PRIMARY_MANIFEST_SHA256 = "2ec7dbc5c7f0449d7d3f8626a3cb096e8e6e4c32778e750e5184fc3adc5c436c"

STRATEGIES = ("random", "p50", "pollitt", "hybrid")

ESTIMATORS = ("B1", "B2", "F1")

BUDGETS = tuple(range(2, 17, 2))

ENDPOINTS = ("stop_attained_by_cap", "readiness_attained_by_cap",
             "premature_stop", "readiness_without_stopping")

STYLE = {
    "random": ("#333333", "o", "-", "Random"),
    "p50": ("#0072B2", "s", "--", "TrueSkill p50"),
    "pollitt": ("#D55E00", "^", "-.", "Pollitt-inspired"),
    "hybrid": ("#009E73", "D", ":", "Hybrid"),
}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_release(directory, *, primary=False):
    'Verify every listed file hash before reading the numerical inputs.'
    manifest = directory / "SHA256SUMS"
    require(manifest.is_file(), f"Missing manifest: {manifest}")
    if primary:
        require(sha256(manifest) == PRIMARY_MANIFEST_SHA256, "D153B manifest identity changed")
    hashes = {}
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        require(Path(name).name == name and name not in hashes,
                "Manifest entries must be unique local filenames")
        require(len(digest) == 64 and (directory / name).is_file(), f"Missing release file: {name}")
        require(sha256(directory / name) == digest, f"SHA256 mismatch: {name}")
        hashes[name] = digest
    require(bool(hashes), "Empty release manifest")
    return hashes

def read_csv(directory, name, required, hashes):
    require(name in hashes, f"CSV absent from verified manifest: {name}")
    with (directory / name).open(newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames),
                f"Duplicate or absent columns: {name}")
        require(set(required) <= set(reader.fieldnames), f"Missing columns: {name}")
        rows = list(reader)
    require(rows and all(None not in row for row in rows), f"Malformed or empty CSV: {name}")
    return rows

def number(row, key):
    value = float(row[key])
    require(math.isfinite(value), f"Nonfinite {key}")
    return value

def count(row, key):
    value = number(row, key)
    require(value >= 0 and value == int(value), f"Invalid count {key}")
    return int(value)

def unique_index(rows, keys):
    result = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        require(key not in result, f"Duplicate statistical key: {key}")
        result[key] = row
    return result

def validate_inference(row):
    require(row["status"] == "estimable" and row["reason"] == "complete_target_support",
            "Unexpected incomplete inference support")
    require(count(row, "n_prompts") == count(row, "target_prompts") == 16,
            "Expected 16 prompt clusters")
    require(count(row, "n_cells") == 96 and count(row, "target_traits") == 6,
            "Expected 96 repeated prompt-by-trait cells")
    lo, value, hi = (number(row, k) for k in ("ci95_low", "estimate", "ci95_high"))
    require(lo <= value <= hi, "CI does not bracket estimate")
    require(number(row, "se") >= 0 and number(row, "df_satterthwaite") > 0,
            "Invalid standard error or degrees of freedom")

def load_inputs(input_dir, posthoc_dir):
    primary_hashes = verify_release(input_dir, primary=True)
    posthoc_hashes = verify_release(posthoc_dir)
    infer_cols = ("estimate", "se", "df_satterthwaite", "ci95_low", "ci95_high",
                  "n_prompts", "n_cells", "target_prompts", "target_traits", "status", "reason")
    all_curves = read_csv(input_dir, "curves.csv", (*infer_cols, "analysis", "outcome", "strategy", "estimator", "B"), primary_hashes)
    curves = [r for r in all_curves if r["analysis"] in ("RQ1", "RQ2")]
    for row in curves:
        validate_inference(row)
        require(row["outcome"] == {"RQ1": "R2", "RQ2": "gap"}[row["analysis"]], "Unexpected curve outcome")
    curve_index = unique_index(curves, ("analysis", "estimator", "strategy", "B"))
    require(set(curve_index) == set(itertools.product(("RQ1", "RQ2"), ESTIMATORS, STRATEGIES, map(str, BUDGETS))),
            "Expected all eight budgets for all 3 estimators and 4 strategies in RQ1/RQ2")
    stop_cols = ("estimator", "strategy", "threshold", "endpoint", "rate", "n_prompts", "n_observed", "n_eligible",
                 "n_missing", "n_events", "n_classified_all", "n_classified_excluded_with_incomplete_prompt",
                 "n_known_stops", "n_observed_stop_hits", "n_stop_right_censored", "n_stop_unresolved",
                 "n_known_readiness", "n_observed_readiness_hits", "n_readiness_right_censored", "n_readiness_unresolved",
                 "weighting", "target_prompts", "target_traits")
    stopping = read_csv(input_dir, "stopping_summary.csv", stop_cols, primary_hashes)
    stopping_index = unique_index(stopping, ("threshold", "endpoint", "estimator", "strategy"))
    require(set(stopping_index) == set(itertools.product(("0.7", "0.9"), ENDPOINTS, ESTIMATORS, STRATEGIES)), "Incomplete stopping grid")
    for row in stopping:
        counts = {k: count(row, k) for k in stop_cols if k.startswith("n_") or k.startswith("target_")}
        require(counts["target_prompts"] == 16 and counts["target_traits"] == 6, "Stopping target changed")
        require(counts["n_prompts"] <= 16 and counts["n_events"] <= counts["n_observed"] <= counts["n_eligible"] <= 96,
                "Inconsistent stopping denominators")
        require(counts["n_observed"] + counts["n_classified_excluded_with_incomplete_prompt"] == counts["n_classified_all"],
                "Stopping exclusions inconsistent")
        conditional = row["endpoint"] in ENDPOINTS[2:]
        require(row["weighting"] == ("equal_prompt_classified_event_rates" if conditional else "equal_prompt_six_equal_traits"),
                "Unexpected stopping conditioning")
        if counts["n_observed"] == 0:
            require(row["rate"] == "" and counts["n_prompts"] == 0, "Empty support must remain undefined")
        else:
            require(0 <= number(row, "rate") <= 1 and counts["n_prompts"] > 0, "Invalid stopping rate")
        for kind in ("stop", "readiness"):
            require(counts[f"n_observed_{kind}_hits"] + counts[f"n_{kind}_right_censored"] == 96,
                    "Unexpected stopping classification; review unresolved overlap before plotting")
    diagnostics = read_csv(posthoc_dir, "ssr_by_budget.csv", ("B", "n_results", "n_negative", "min_ssr"), posthoc_hashes)
    diagnostic_index = unique_index(diagnostics, ("B",))
    require(set(diagnostic_index) == {(str(b),) for b in BUDGETS}, "Missing diagnostic budget")
    for row in diagnostics:
        require(count(row, "n_results") == 384 and count(row, "n_negative") <= 384, "SSR diagnostic support changed")
        number(row, "min_ssr")
    worst = read_csv(posthoc_dir, "ssr_worst_case.csv", ("B", "ssr", "observed_variance", "mean_squared_se"), posthoc_hashes)
    require(len(worst) == 1 and worst[0]["B"] == "2", "Expected one B2 severity diagnostic")
    require(number(worst[0], "ssr") == number(diagnostic_index[("2",)], "min_ssr"), "Worst case is not B2 minimum")
    return {"curves": curve_index, "stopping": stopping_index,
            "diagnostics": diagnostic_index, "worst": worst[0],
            "hashes": {"D153B": primary_hashes, "D153C_posthoc": posthoc_hashes}}

def style():
    
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8,
                         "axes.titlesize": 9, "axes.labelsize": 8,
                         "xtick.labelsize": 7, "ytick.labelsize": 7,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.linewidth": .6, "grid.linewidth": .4,
                         "pdf.fonttype": 42, "ps.fonttype": 42,
                         "svg.hashsalt": "D153C-2026-10-24", "savefig.dpi": 300})

def validate_layout(fig):
    'Check that visible figure labels fit on the page; visual inspection is still needed.'
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts = list(fig.texts)
    for legend_ in fig.legends:
        texts.extend(legend_.get_texts())
    for ax in fig.axes:
        texts.extend(ax.texts)
        texts.extend([ax.title, ax._left_title, ax._right_title])
        for axis in (ax.xaxis, ax.yaxis):
            texts.extend([axis.label, axis.offsetText])
            lower, upper = sorted(axis.get_view_interval())
            for tick in axis.get_major_ticks():
                
                
                if lower <= tick.get_loc() <= upper:
                    texts.extend([tick.label1, tick.label2])
    for text in texts:
        if not text.get_visible() or not text.get_text():
            continue
        bounds = text.get_window_extent(renderer)
        
        if text.axes is not None and not text.axes.get_visible():
            continue
        require(bounds.x0 >= -1 and bounds.y0 >= -1 and bounds.x1 <= fig.bbox.x1 + 1 and bounds.y1 <= fig.bbox.y1 + 1,
                f"Text outside figure canvas: {text.get_text()}")


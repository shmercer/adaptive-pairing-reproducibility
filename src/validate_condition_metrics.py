#!/usr/bin/env python3
'Check the full-precision performance measures used for statistical analysis.\n\nRequire the expected columns, file hashes and all reported method-by-budget combinations. Check their prompt and trait identities against the judgment index. Individual essay scores and human ratings are not inputs.'
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

FIELDS = ("cell_index", "prompt_id", "trait", "replicate_index", "strategy",
          "B", "estimator", "N", "M", "replay_seed", "R2", "reliability",
          "log_loss", "spread_error")
VALUES = ("R2", "reliability", "log_loss", "spread_error")
STRATEGIES = ("random", "p50", "pollitt", "hybrid")
PRIMARY = ("B1", "B2", "F1")
BUDGETS = (2, 4, 6, 8, 10, 12, 14, 16)
RQ3_B = (4, 8, 16)
EXPECTED_CELLS = set(range(1, 109)) - set(range(25, 31)) - set(range(97, 103))
SCHEMA = "JEM-manuscript-conditions-v2"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def read_rows(path, fields):
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        need(reader.fieldnames == list(fields), "Unexpected condition CSV schema")
        for row in reader:
            need(None not in row and all(v is not None for v in row.values()),
                 "Malformed condition row")
            yield row


def verify(root: Path, observations: Path) -> dict:
    root = root.expanduser().resolve()
    observations = observations.expanduser().resolve()
    need(root.is_dir() and observations.is_dir(),
         "Missing conditions or observations directory")
    files = {
        "data/condition_metrics.csv",
        "data/metadata.json",
    }
    manifest = root / "data/SHA256SUMS"
    need(manifest.is_file() and not manifest.is_symlink(),
         "Missing condition SHA256 manifest")
    observed = {}
    for line in manifest.read_text(encoding="ascii").splitlines():
        pieces = line.split(maxsplit=1)
        need(len(pieces) == 2, "Malformed condition SHA entry")
        fingerprint, path = pieces
        need(path in files and path not in observed and
             len(fingerprint) == 64 and
             all(c in "0123456789abcdef" for c in fingerprint),
             "Unexpected condition manifest file/identity")
        item = root / path
        need(item.is_file() and not item.is_symlink() and
             item.stat().st_size < 8_000_000 and sha(item) == fingerprint,
             "Condition SHA256, file size or symlink check failed")
        observed[path] = fingerprint
    need(set(observed) == files, "Incomplete condition manifest")
    for p in root.rglob("*"):
        need(not p.is_symlink(), "Symlink in condition export")
        if p.is_file():
            need(p.relative_to(root).as_posix() in files | {"data/SHA256SUMS"},
                 "Unexpected condition export file")

    metadata = json.loads((root / "data/metadata.json").read_text(encoding="utf-8"))
    need(metadata.get("schema") == SCHEMA and
         metadata.get("counts") == {
             "rows": 10944, "cells": 96, "prompts": 16, "estimators": 5} and
         metadata.get("includes_human_scores") is False and
         metadata.get("includes_item_scores") is False,
         "Unexpected condition metadata or private score flag")
    design_file = observations / "data/design/cells.csv"
    need(design_file.is_file(), "Missing anonymous cell design")
    cells = {}
    with design_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = int(row["cell_id"])
            need(idx not in cells, "Duplicate anonymous cell")
            cells[idx] = (row["prompt_id"], row["trait"], int(row["n_items"]))
    need(set(cells) == EXPECTED_CELLS, "Wrong original noncontiguous cells")
    replicate = {}
    combination = defaultdict(set)
    totals = Counter()
    for row in read_rows(root / "data/condition_metrics.csv", FIELDS):
        ci = int(row["cell_index"])
        need(ci in cells, "Foreign cell in conditions")
        prompt, trait, n = cells[ci]
        need((row["prompt_id"], row["trait"]) == (prompt, trait),
             "Foreign anonymous prompt or trait")
        b, size, m, seed = (int(row[f]) for f in ("B", "N", "M", "replay_seed"))
        rep = int(row["replicate_index"])
        need(1 <= rep <= 5 and rep == replicate.setdefault(ci, rep) and
             seed == 114000000 + 10 * ci + rep and
             size == n and m == b * n // 2 and
             2 * m == b * n and b in BUDGETS,
             "Incorrect D136 primary replicate, seed or exposure")
        strategy, method = row["strategy"], row["estimator"]
        need(strategy in STRATEGIES and method in (*PRIMARY, "F2", "F3"),
             "Unknown strategy or estimator")
        permitted = ((method in PRIMARY) or
                     (method == "F2" and strategy != "hybrid" and b in RQ3_B) or
                     (method == "F3" and strategy != "hybrid" and b in RQ3_B))
        need(permitted, "Unexpected estimator/strategy/budget condition")
        identity = (strategy, b, method)
        need(identity not in combination[ci], "Duplicate estimator checkpoint")
        combination[ci].add(identity)
        for field in VALUES:
            entry = row[field]
            unreported = (field in ("log_loss", "spread_error") and
                          (strategy == "hybrid" or b not in RQ3_B)) or (
                              field == "reliability" and method in ("F2", "F3"))
            need(not unreported or entry == "", "Unreported condition outcome must be omitted")
            if entry:
                try:
                    value = float(entry)
                except ValueError as exc:
                    raise ValueError("Non-numeric original metric") from exc
                need(math.isfinite(value), "Nonfinite original metric")
            
        totals["rows"] += 1
    expected_per_cell = {
        (strategy, b, method)
        for strategy in STRATEGIES
        for b in BUDGETS
        for method in PRIMARY
    } | {
        (strategy, b, "F2")
        for strategy in ("random", "p50", "pollitt") for b in RQ3_B
    } | {
        (strategy, b, "F3")
        for strategy in ("random", "p50", "pollitt") for b in RQ3_B
    }
    need(len(expected_per_cell) == 114 and len(combination) == 96 and
         all(entries == expected_per_cell for entries in combination.values()) and
         totals["rows"] == 10944,
         "Incomplete or duplicate 114-condition grid")
    return {"rows": totals["rows"], "cells": len(combination),
            "prompts": len({p for p, _, _ in cells.values()}),
            "conditions_per_cell": 114, "signed_files": len(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conditions", required=True, type=Path)
    parser.add_argument("--observations", required=True, type=Path)
    a = parser.parse_args()
    report = verify(a.conditions, a.observations)
    print("PASS: Full-precision D153 condition panel verified: "
          f"{report['rows']} rows / {report['cells']} cells / "
          f"{report['prompts']} prompts, one assigned seed per cell")
    print("PASS: Source data schemas, hashes, 114-condition manuscript grid; "
          "no human or item-level scores")


if __name__ == "__main__":
    main()

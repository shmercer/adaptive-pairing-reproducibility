#!/usr/bin/env python3
'Check the stored pairwise judgments before they are used.\n\nVerify file hashes, allowed columns, all expected essay pairs, the reserved prediction pairs and the reversed presentations. Require the original prompt and trait coverage. Print counts only; do not print essay text or individual judgments.'
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

EXPECTED = {
    "base": 676326, "selectable": 608652, "heldout": 67674,
    "reversal": 33858, "cells": 96, "prompts": 16, "target_essays": 1714,
}
TRAITS = {"Cohesion", "Syntax", "Vocabulary", "Phraseology",
          "Grammar", "Conventions"}
FROZEN_CELL_IDS = set(range(1, 109)) - set(range(25, 31)) - set(range(97, 103))
INDEX_COLUMNS = ("item_id", "prompt_id", "public_essay_key")
CELL_COLUMNS = ("cell_id", "prompt_id", "trait", "n_items", "n_base",
                "n_selectable", "n_heldout", "n_reversal")
BASE_COLUMNS = ("pair_id", "first_id", "second_id", "first_wins", "partition")
REV_COLUMNS = ("cell_id", "base_pair_id", "first_id", "second_id", "first_wins")
MAX_FILE_BYTES = 8_000_000


def need(condition: bool, description: str) -> None:
    if not condition:
        raise ValueError(description)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rows(path: Path, fields):
    need(path.is_file() and not path.is_symlink(),
         "Missing or symlinked observation CSV")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        need(reader.fieldnames == list(fields),
             "Unexpected observation CSV schema")
        for record in reader:
            need(None not in record and all(v is not None for v in record.values()),
                 "Malformed observation CSV row")
            yield record


def known_data_file(name: str) -> bool:
    return (name == "README.md" or
            name == "data/essays/item_index.csv" or
            name == "data/design/cells.csv" or
            name == "data/design/metadata.json" or
            name == "data/judgments/reversals.csv" or
            bool(re.fullmatch(r"data/judgments/cell_[0-9]{3}\.csv", name)))


def verify_contents(root: Path) -> dict:
    manifest = root / "data/SHA256SUMS"
    need(manifest.is_file() and not manifest.is_symlink(),
         "Missing or symlinked observation SHA256SUMS")
    recorded = {}
    for line in manifest.read_text(encoding="ascii").splitlines():
        fragments = line.split(maxsplit=1)
        need(len(fragments) == 2, "Malformed observation manifest entry")
        fingerprint, name = fragments
        need(bool(re.fullmatch(r"[0-9a-f]{64}", fingerprint)) and
             known_data_file(name) and name not in recorded and
             not Path(name).is_absolute() and ".." not in Path(name).parts,
             "Unsafe, duplicate, or unexpected observation manifest entry")
        path = root / name
        need(path.is_file() and not path.is_symlink(), "Missing observation file")
        need(path.stat().st_size <= MAX_FILE_BYTES,
             "Observation file exceeds anonymous hosting size limit")
        need(sha256(path) == fingerprint,
             "Observation SHA256 mismatch; package modified or incomplete")
        recorded[name] = fingerprint
    need(len(recorded) == 101, "Expected exactly 101 signed observation files")
    for path in root.rglob("*"):
        need(not path.is_symlink(), "Observation package may not contain symlinks")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            need(relative == "data/SHA256SUMS" or relative in recorded,
                 "Unexpected unverified observation file")
    need("data/essays/item_index.csv" in recorded and
         "data/design/cells.csv" in recorded and
         "data/design/metadata.json" in recorded and
         "data/judgments/reversals.csv" in recorded and
         "README.md" in recorded and
         len([p for p in recorded if re.fullmatch(
             r"data/judgments/cell_[0-9]{3}\.csv", p)]) == 96,
         "Missing indexed judgment datasets")
    return recorded


def read_index(root: Path, expected: dict):
    items = {}
    prompts = Counter()
    public_keys = set()
    for record in rows(root / "data/essays/item_index.csv", INDEX_COLUMNS):
        item, prompt, key = (record[c] for c in INDEX_COLUMNS)
        need(re.fullmatch(r"p[0-9]{2}_e[0-9]{4}", item) and
             re.fullmatch(r"p[0-9]{2}", prompt) and
             item.startswith(prompt + "_") and
             re.fullmatch(r"k[0-9a-f]{24}", key),
             "Invalid pseudonymous essay identity or public join key")
        need(item not in items and key not in public_keys,
             "Duplicate pseudonymous essay or public join key")
        items[item] = prompt
        public_keys.add(key)
        prompts[prompt] += 1
    need(len(items) == expected["target_essays"] and
         len(prompts) == expected["prompts"],
         "Frozen essay or prompt totals differ")
    need(set(prompts) == {f"p{i:02d}" for i in range(1, expected["prompts"] + 1)},
         "Anonymous prompt codes differ")
    return items, prompts


def read_cells(root: Path, prompts: Counter, expected: dict):
    design = {}
    traits_per_prompt = defaultdict(set)
    for record in rows(root / "data/design/cells.csv", CELL_COLUMNS):
        cell_id = int(record["cell_id"])
        prompt = record["prompt_id"]
        trait = record["trait"]
        need(cell_id > 0 and cell_id not in design and prompt in prompts and
             trait in TRAITS and trait not in traits_per_prompt[prompt],
             "Duplicate or unexpected cell, prompt, or trait")
        observed = {field: int(record[field]) for field in
                    ("n_items", "n_base", "n_selectable", "n_heldout", "n_reversal")}
        count = prompts[prompt]
        need(observed["n_items"] == count and
             observed["n_base"] == count * (count - 1) // 2 and
             observed["n_selectable"] + observed["n_heldout"] == observed["n_base"],
             "Invalid cell item/complete-graph/partition counts")
        design[cell_id] = {"prompt": prompt, "trait": trait, **observed}
        traits_per_prompt[prompt].add(trait)
    need(len(design) == expected["cells"] and
         set(design) == FROZEN_CELL_IDS and
         all(traits_per_prompt[p] == TRAITS for p in prompts),
         "Original 96 noncontiguous cell identities or trait grid differ")
    return design


def read_reversals(root: Path, cells: dict, items: dict, expected: dict):
    reversals = defaultdict(dict)
    total = 0
    for record in rows(root / "data/judgments/reversals.csv", REV_COLUMNS):
        cell_id = int(record["cell_id"])
        pair_id = record["base_pair_id"]
        first, second = record["first_id"], record["second_id"]
        need(cell_id in cells and
             re.fullmatch(r"b[0-9]{6}", pair_id) and
             pair_id not in reversals[cell_id] and
             first in items and second in items and first != second and
             items[first] == items[second] == cells[cell_id]["prompt"] and
             record["first_wins"] in ("0", "1"),
             "Invalid or duplicate reversal record")
        reversals[cell_id][pair_id] = (first, second)
        total += 1
    need(total == expected["reversal"] and all(
         len(reversals[c]) == cells[c]["n_reversal"] for c in cells),
         "Frozen reversal counts differ")
    return reversals, total


def validate(data_root: Path, expected=None) -> dict:
    expected = EXPECTED if expected is None else expected
    root = data_root.expanduser().resolve()
    need(root.is_dir() and not root.is_symlink(), "Observation root missing")
    verify_contents(root)
    items, prompts = read_index(root, expected)
    cells = read_cells(root, prompts, expected)
    reversals, reversal_total = read_reversals(root, cells, items, expected)
    totals = Counter()
    for cell_id in sorted(cells):
        cell = cells[cell_id]
        path = root / f"data/judgments/cell_{cell_id:03d}.csv"
        seen_edges = set()
        found_reversals = set()
        counts = Counter()
        for line_no, record in enumerate(rows(path, BASE_COLUMNS), 1):
            pair_id, a, b, winner, partition = (record[f] for f in BASE_COLUMNS)
            need(pair_id == f"b{line_no:06d}" and
                 a in items and b in items and a != b and
                 items[a] == items[b] == cell["prompt"] and
                 winner in ("0", "1") and
                 partition in ("selectable", "heldout"),
                 "Invalid pair identifier, presentation, or partition")
            pair = (min(a, b), max(a, b))
            need(pair not in seen_edges,
                 "Repeated unordered pair in complete graph")
            seen_edges.add(pair)
            reverse = reversals[cell_id].get(pair_id)
            if reverse is not None:
                need(reverse == (b, a), "Reversal did not exchange original order")
                found_reversals.add(pair_id)
            counts[partition] += 1
            counts["base"] += 1
        need(counts["base"] == cell["n_base"] and
             counts["selectable"] == cell["n_selectable"] and
             counts["heldout"] == cell["n_heldout"] and
             len(seen_edges) == cell["n_base"] and
             len(found_reversals) == cell["n_reversal"],
             "Per-cell complete graph or heldout/reversal counts differ")
        totals.update(counts)
    totals["reversal"] = reversal_total
    totals["cells"] = len(cells)
    totals["prompts"] = len(prompts)
    totals["target_essays"] = len(items)
    need(all(totals[k] == expected[k] for k in expected),
         "Frozen observation totals differ")
    metadata = json.loads((root / "data/design/metadata.json").read_text(
        encoding="utf-8"))
    need(isinstance(metadata, dict) and metadata.get("format_version") == 1 and
         metadata.get("counts") == dict(totals),
         "Frozen metadata summary differs from independent reconstruction")
    return dict(sorted(totals.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("observations"))
    args = parser.parse_args()
    totals = validate(args.data_root)
    print("PASS: Independent reviewer observation validation")
    print(f"PASS: {totals['cells']} complete graphs / {totals['base']} "
          f"base / {totals['heldout']} heldout / "
          f"{totals['reversal']} reversals / "
          f"{totals['target_essays']} pseudonymous essays")
    print("PASS: Signed inputs, original cell identities, oriented reversals,"
          " and rating-free schemas")


if __name__ == "__main__":
    main()

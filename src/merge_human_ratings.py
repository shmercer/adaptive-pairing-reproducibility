#!/usr/bin/env python3
"Optionally match the 1,714 study essays to original public ELLIPSE human ratings.\n\nDownload the original train and test files separately. This standalone utility uses Python's standard library and makes no network calls. Keep downloads and joined scores outside this package and all Git checkouts. Joining ratings does not supply the fitted essay scores needed to recalculate item-level Table 4 correlations."
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

TRAITS = ("Cohesion", "Syntax", "Vocabulary", "Phraseology", "Grammar", "Conventions")
INDEX_COLUMNS = ("item_id", "prompt_id", "public_essay_key")
OUTPUT_COLUMNS = ("item_id", "prompt_id", *TRAITS)
EXPECTED = 1714

KEY_PREFIX = "ELLIPSE-Corpus/text_id_kaggle/v1:"


def require(condition, description):
    if not condition:
        raise ValueError(description)


def public_essay_key(source_id: str) -> str:
    'Match an original public corpus ID using its stripped UTF-8 string, without numeric conversion. This deterministic key permits linking; it does not guarantee anonymity.'
    require(isinstance(source_id, str) and bool(source_id.strip()),
            "Missing public corpus text_id_kaggle")
    identifier = source_id.strip()
    return "k" + hashlib.sha256((KEY_PREFIX + identifier).encode("utf-8")).hexdigest()[:24]


def read_index(path: Path, expected: int = EXPECTED) -> dict[str, tuple[str, str]]:
    require(path.is_file() and not path.is_symlink(),
            "Pseudonymous item index not found")
    items = {}
    item_ids = set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == list(INDEX_COLUMNS),
                "Item index must contain ONLY the three approved columns")
        for row in reader:
            require(None not in row and all(v is not None for v in row.values()),
                    "Malformed item-index row")
            item_id, prompt, key = (row[c] for c in INDEX_COLUMNS)
            require(item_id and prompt and key.startswith("k") and len(key) == 25,
                    "Invalid pseudonymous item or join key")
            require(key not in items and item_id not in item_ids,
                    "Duplicate item or public join key")
            item_ids.add(item_id)
            items[key] = item_id, prompt
    require(len(items) == expected, "Pseudonymous item count differs from study")
    require(len({v[1] for v in items.values()}) == 16 or expected != EXPECTED,
            "Expected 16 anonymous prompt codes")
    return items


def verify_rating(value: str, trait: str) -> str:
    require(isinstance(value, str) and bool(value.strip()),
            f"Missing original human score for {trait}")
    try:
        number = Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(f"Non-numeric original human score for {trait}") from exc
    require(number.is_finite(), f"Nonfinite original human score for {trait}")
    return value.strip()


def join(data_root: Path, train: Path, test: Path, output: Path,
         expected: int = EXPECTED) -> dict:
    data_root, train, test = (p.expanduser().resolve() for p in (data_root, train, test))
    output = output.expanduser().resolve()
    item_index = data_root / "data" / "essays" / "item_index.csv"
    require(item_index.exists(), "Anonymous Luna item index is missing")
    index = read_index(item_index, expected=expected)
    package_root = data_root.parent if data_root.name == "observations" else data_root
    require(not output.is_relative_to(package_root),
            "Write human ratings outside the reviewer package")
    require(not any((parent / ".git").exists() for parent in (output.parent, *output.parents)),
            "Write human ratings outside Git working trees")
    require(output != item_index and not output.exists(),
            "Use a NEW output path; never overwrite original data or earlier results")
    require(output != train and output != test,
            "Output cannot overwrite source ELLIPSE ratings")
    require(train.is_file() and test.is_file() and
            not train.is_symlink() and not test.is_symlink(),
            "Download both original ELLIPSE train and extracted test CSVs first")
    require(train != test, "Provide separate original train and test CSVs")
    require(not any(path.is_relative_to(package_root) for path in (train, test)),
            "Keep original ELLIPSE source files outside the reviewer package")

    matches = {}
    source_ids = set()
    for source in (train, test):
        with source.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            require(reader.fieldnames is not None and
                    {"text_id_kaggle", *TRAITS} <= set(reader.fieldnames),
                    "Original ELLIPSE source lacks required rating columns")
            for row in reader:
                require(None not in row and all(x is not None for x in row.values()),
                        "Malformed original ELLIPSE CSV row")
                raw_id = row["text_id_kaggle"]
                require(raw_id and raw_id.strip(), "Missing public corpus text_id_kaggle")
                require(raw_id.strip() not in source_ids,
                        "Duplicate public corpus text_id_kaggle across train/test")
                source_ids.add(raw_id.strip())
                key = public_essay_key(raw_id)
                if key not in index:
                    continue
                require(key not in matches,
                        "Duplicate target essay across ELLIPSE train/test")
                item_id, prompt = index[key]
                matches[key] = dict(item_id=item_id, prompt_id=prompt,
                                    **{trait: verify_rating(row[trait], trait)
                                       for trait in TRAITS})
    require(len(matches) == expected,
            f"Matched {len(matches)}/{expected} essays. Check original "
            "ELLIPSE train/test versions and item-index join namespace.")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".human-score-", suffix=".csv",
                                    dir=output.parent)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS,
                                    lineterminator="\n")
            writer.writeheader()
            for row in sorted(matches.values(), key=lambda z: z["item_id"]):
                writer.writerow(row)
        require(not output.exists(), "Output appeared during preparation")
        os.replace(temporary, output)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    return {"matched_essays": len(matches),
            "source": "original public ELLIPSE training and test releases",
            "output_type": "local human trait ratings; NOT for GitHub"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("observations"),
                        help="Comparison-data directory in the extracted package")
    parser.add_argument("--train", required=True, type=Path,
                        help="Path to original ELLIPSE_Final_github_train.csv")
    parser.add_argument("--test", required=True, type=Path,
                        help="Path to original extracted ELLIPSE_Final_github_test.csv")
    parser.add_argument("--output", type=Path, required=True,
                        help="NEW local output outside this package and all Git checkouts")
    args = parser.parse_args()
    report = join(args.data_root, args.train, args.test, args.output)
    print("PASS:", report["matched_essays"], "human-scored essays matched")
    print("Ratings written locally outside the package. Do NOT commit or upload them.")


if __name__ == "__main__":
    main()

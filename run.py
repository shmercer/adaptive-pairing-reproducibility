#!/usr/bin/env python3
'Reproduce the manuscript figures and tables and check their inputs.\n\nRun from the extracted package: python3 run.py. Add --analysis for the statistical recalculation or --tables-only to omit figures. Results are written under output/. The README lists required software and optional inputs.'
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def verify_package():
    'Check the hashes and completeness of all distributed files before running calculations.'
    manifest = ROOT / "SHA256SUMS"
    if not manifest.is_file():
        raise ValueError("Missing package SHA256SUMS; extract a complete copy")
    recorded = set()
    for line in manifest.read_text(encoding="ascii").splitlines():
        digest, name = line.split(maxsplit=1)
        path = Path(name)
        if (path.is_absolute() or ".." in path.parts or name in recorded or
                not (ROOT / path).is_file() or (ROOT / path).is_symlink()):
            raise ValueError("Unsafe, missing or duplicate package manifest entry")
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Package SHA256 mismatch: {name}")
        recorded.add(name)
    allowed_generated = {"output", ".venv", "__pycache__"}
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*")
              if p.is_file() and p != manifest and
              not any(part in allowed_generated for part in p.relative_to(ROOT).parts)}
    if not recorded or actual != recorded:
        raise ValueError("Package contains unexpected files or is incomplete")
    print(f"PASS: Complete package manifest ({len(recorded)} files)")


def verify_release(folder):
    manifest = folder / "SHA256SUMS"
    if not manifest.is_file():
        raise ValueError(f"Missing SHA256 manifest: {manifest}")
    lines = manifest.read_text(encoding="ascii").splitlines()
    if not lines:
        raise ValueError(f"Empty SHA256 manifest: {manifest}")
    for line in lines:
        digest, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        path = folder / name
        if Path(name).name != name or not path.is_file():
            raise ValueError(f"Missing or unsafe manifest entry: {name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f"SHA256 mismatch: {path}")
    print(f"PASS: {folder.relative_to(ROOT)} ({len(lines)} source files verified)")


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables-only", action="store_true",
                        help="No matplotlib required; create tabular results only.")
    parser.add_argument("--analysis", action="store_true",
                        help="Also recalculate statistical comparisons across 16 "
                             "writing prompts; requires condition data and R 4.6.1.")
    args = parser.parse_args()

    verify_package()
    for name in ("primary", "ssr", "estimator", ""):
        verify_release(ROOT / "data" / name)

    if (ROOT / "data/position").exists():
        verify_release(ROOT / "data/position")
        (ROOT / "output").mkdir(exist_ok=True)
        subprocess.run(["Rscript", "--vanilla", "src/recalculate_position.R",
                        "--data=data/position", "--output=output/position_summary.csv"],
                       cwd=ROOT, check=True)

    
    if (ROOT / "observations").exists():
        run("src/validate_observations.py", "--data-root", "observations")
    if (ROOT / "conditions").exists():
        if not (ROOT / "observations").exists():
            raise ValueError("Condition data require the observations/ directory")
        run("src/validate_condition_metrics.py", "--conditions", "conditions",
            "--observations", "observations")
    if args.analysis:
        if not (ROOT / "conditions").is_dir():
            raise ValueError("Statistical recalculation requires the conditions/ directory")
        if shutil.which("Rscript") is None:
            raise ValueError("Independent RQ1-3 analysis requires Rscript 4.6.1")
        
        (ROOT / "output").mkdir(parents=True, exist_ok=True)
        target = ROOT / "output" / "analysis"
        if target.exists():
            raise ValueError("Analysis output already exists; preserve prior receipts")
        subprocess.run(["Rscript", "--vanilla", "src/recalculate_inference.R",
                        f"--root={ROOT}", f"--output={target}"],
                       cwd=ROOT, check=True)
        
        
        run("src/recalculate_reversals.py", "--data-root", "observations",
            "--output-dir", "output/analysis/reversal")

    figures = ROOT / "output" / "figures"
    tables = ROOT / "output" / "tables"
    figures.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    
    run("src/build_rq2_main_table.py",
        "--input-dir", "data/primary", "--posthoc-dir", "data/ssr",
        "--output", "output/tables/table_rq2_main.tex")

    
    run("src/build_rq3_main_table.py",
        "--input-dir", "data/estimator",
        "--output", "output/tables/table_rq3_main.tex")

    
    run("src/human_correlations.py",
        "--data-dir", "data",
        "--output-dir", "output/tables")

    if not args.tables_only:
        run("src/build_hybrid_pairing_flowchart.py",
            "--out-dir", "output/figures")
        run("src/build_rq1_main_figure.py",
            "--input-dir", "data/primary", "--posthoc-dir", "data/ssr",
            "--output-dir", "output/figures")
        run("src/build_rq2_storyline_figures.py",
            "--input-dir", "data/primary", "--posthoc-dir", "data/ssr",
            "--output-dir", "output/figures")
    print("PASS: Reviewer artifact outputs written to output/")


if __name__ == "__main__":
    main()

"""Command line entry point: ``python -m triallens.local.cli --raw data/raw --out data/out``."""

from __future__ import annotations

import argparse
import sys

from triallens.local.runner import run_pipeline, write_run
from triallens.local.spark import get_local_spark
from triallens.quality.engine import evaluate_all, summarize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the TrialLens pipeline locally on CSV extracts.")
    parser.add_argument("--raw", required=True, help="directory with one <source>.csv per raw source")
    parser.add_argument("--out", help="write clean/curated/ontology datasets as parquet to this directory")
    parser.add_argument("--skip-ontology", action="store_true", help="only build clean and curated layers")
    args = parser.parse_args(argv)

    spark = get_local_spark()
    run = run_pipeline(spark, args.raw, include_ontology=not args.skip_ontology)

    datasets = {**run.by_name("clean"), **run.by_name("curated")}
    results = evaluate_all(datasets)
    print(summarize(results))

    for key in sorted(run.datasets):
        if not key.startswith("raw/"):
            print(f"{key:55s} {run[key].count():>8d} rows")

    if args.out:
        write_run(run, args.out)
        print(f"wrote datasets to {args.out}")
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

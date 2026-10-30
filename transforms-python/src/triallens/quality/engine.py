"""Local evaluator for the expectations declared in config/expectations.yaml.

Semantics mirror the Foundry checks generated in foundry_checks.py so that CI catches
expectation failures before a branch is merged.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from triallens.config import EXPECTATION_KINDS, load_expectations


@dataclass(frozen=True)
class ExpectationResult:
    dataset: str
    name: str
    kind: str
    passed: bool
    failing_rows: int
    message: str

    @property
    def check_id(self) -> str:
        return f"{self.dataset}:{self.name}"


def evaluate(dataset: str, df: DataFrame, expectation: Mapping[str, Any]) -> ExpectationResult:
    kind = expectation["kind"]
    if kind not in EXPECTATION_KINDS:
        raise ValueError(f"{dataset}:{expectation['name']}: unknown kind {kind!r}")
    column = expectation.get("column")
    if column is not None and column not in df.columns:
        return ExpectationResult(dataset, expectation["name"], kind, False, -1, f"column {column!r} missing")

    if kind == "row_count_min":
        count = df.count()
        passed = count >= expectation["min"]
        return ExpectationResult(
            dataset, expectation["name"], kind, passed, 0 if passed else 1, f"{count} rows (min {expectation['min']})"
        )

    c = F.col(column)
    if kind == "primary_key":
        stats = df.agg(
            F.count("*").alias("n"),
            F.sum(c.isNull().cast("int")).alias("nulls"),
            F.countDistinct(c).alias("distinct"),
        ).first()
        nulls = stats["nulls"] or 0
        duplicates = (stats["n"] - nulls) - stats["distinct"]
        failing = nulls + duplicates
        return ExpectationResult(
            dataset, expectation["name"], kind, failing == 0, failing, f"{nulls} nulls, {duplicates} duplicates"
        )

    if kind == "not_null":
        violation = c.isNull()
    elif kind == "in_set":
        violation = c.isNotNull() & ~c.isin(*expectation["values"])
    elif kind == "range":
        violation = c.isNotNull() & ((c < expectation["min"]) | (c > expectation["max"]))
    elif kind == "regex":
        violation = c.isNotNull() & ~c.cast("string").rlike(expectation["pattern"])
    else:  # pragma: no cover - guarded above
        raise AssertionError(kind)

    failing = df.where(violation).count()
    return ExpectationResult(dataset, expectation["name"], kind, failing == 0, failing, f"{failing} violating rows")


def evaluate_dataset(dataset: str, df: DataFrame) -> list[ExpectationResult]:
    return [evaluate(dataset, df, exp) for exp in load_expectations().get(dataset, ())]


def evaluate_all(datasets: Mapping[str, DataFrame]) -> list[ExpectationResult]:
    """Evaluate every configured expectation. ``datasets`` is keyed by dataset name."""
    results: list[ExpectationResult] = []
    for dataset in load_expectations():
        if dataset not in datasets:
            raise KeyError(f"no dataset named {dataset!r} to evaluate expectations on")
        results.extend(evaluate_dataset(dataset, datasets[dataset]))
    return results


def summarize(results: Iterable[ExpectationResult]) -> str:
    results = list(results)
    failed = [r for r in results if not r.passed]
    lines = [f"{len(results) - len(failed)}/{len(results)} expectations passed"]
    lines += [f"  FAILED {r.check_id} ({r.kind}): {r.message}" for r in failed]
    return "\n".join(lines)

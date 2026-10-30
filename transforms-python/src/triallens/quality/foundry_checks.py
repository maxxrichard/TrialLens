"""Translate config/expectations.yaml into Foundry data expectations (``Check`` objects).

Only imported inside Foundry, where the ``transforms`` package is available.
"""

from __future__ import annotations

from typing import Any

from triallens.config import expectations_for


def to_expectation(spec: dict[str, Any]):
    from transforms import expectations as E

    kind = spec["kind"]
    column = spec.get("column")
    if kind == "primary_key":
        return E.primary_key(column)
    if kind == "not_null":
        return E.col(column).non_null()
    if kind == "in_set":
        return E.col(column).is_in(*spec["values"])
    if kind == "range":
        return E.all(E.col(column).gte(spec["min"]), E.col(column).lte(spec["max"]))
    if kind == "regex":
        return E.col(column).rlike(spec["pattern"])
    if kind == "row_count_min":
        return E.count().gte(spec["min"])
    raise ValueError(f"unsupported expectation kind {kind!r}")


def checks_for(dataset_name: str) -> list:
    from transforms.api import Check

    return [
        Check(to_expectation(spec), f"{dataset_name}: {spec['name']}", on_error=spec.get("on_error", "FAIL"))
        for spec in expectations_for(dataset_name)
    ]

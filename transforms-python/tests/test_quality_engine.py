from __future__ import annotations

from triallens.quality.engine import evaluate


def _df(spark):
    return spark.createDataFrame(
        [("a", "X", 5.0), ("b", "Y", 50.0), ("b", None, None), (None, "Z", 1.0)],
        "id string, code string, value double",
    )


def test_primary_key_counts_nulls_and_duplicates(spark):
    result = evaluate("t", _df(spark), {"name": "pk", "kind": "primary_key", "column": "id"})
    assert not result.passed
    assert result.failing_rows == 2  # one null + one duplicate


def test_in_set_range_regex_ignore_nulls(spark):
    df = _df(spark)
    assert not evaluate("t", df, {"name": "s", "kind": "in_set", "column": "code", "values": ["X", "Y"]}).passed
    assert evaluate("t", df, {"name": "s", "kind": "in_set", "column": "code", "values": ["X", "Y", "Z"]}).passed
    assert evaluate("t", df, {"name": "r", "kind": "range", "column": "value", "min": 0, "max": 50}).passed
    assert evaluate("t", df, {"name": "r", "kind": "range", "column": "value", "min": 2, "max": 50}).failing_rows == 1
    assert evaluate("t", df, {"name": "x", "kind": "regex", "column": "code", "pattern": "^[A-Z]$"}).passed


def test_not_null_and_row_count(spark):
    df = _df(spark)
    assert evaluate("t", df, {"name": "n", "kind": "not_null", "column": "code"}).failing_rows == 1
    assert evaluate("t", df, {"name": "c", "kind": "row_count_min", "min": 4}).passed
    assert not evaluate("t", df.limit(0), {"name": "c", "kind": "row_count_min", "min": 1}).passed


def test_missing_column_fails(spark):
    result = evaluate("t", _df(spark), {"name": "n", "kind": "not_null", "column": "nope"})
    assert not result.passed and "missing" in result.message

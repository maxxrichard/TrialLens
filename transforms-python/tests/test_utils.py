from __future__ import annotations

import datetime as dt

from pyspark.sql import functions as F

from conftest import SALT
from triallens.utils.columns import (
    age_band,
    code_key,
    is_censored,
    map_values,
    normalize_study_code,
    parse_bool,
    parse_date,
    parse_decimal,
    parse_timestamp,
)
from triallens.utils.pseudonymize import pseudonymize, pseudonymize_value


def _single_column(spark, values, fn):
    df = spark.createDataFrame([(v,) for v in values], "raw string")
    return [row[0] for row in df.select(fn(F.col("raw"))).collect()]


def test_parse_date_accepts_iso_german_and_compact_formats(spark):
    out = _single_column(spark, ["2023-04-05", "05.04.2023", "20230405", "", None, "not a date"], parse_date)
    assert out == [dt.date(2023, 4, 5)] * 3 + [None, None, None]


def test_parse_timestamp(spark):
    out = _single_column(spark, ["2023-04-05T10:15:00", "2023-04-05 10:15:00", "05.04.2023 10:15"], parse_timestamp)
    assert out == [dt.datetime(2023, 4, 5, 10, 15)] * 3


def test_parse_decimal_handles_commas_and_censoring(spark):
    out = _single_column(spark, ["4,2", "4.2", "<0,01", ">1000", " 7 ", "n/a", ""], parse_decimal)
    assert out == [4.2, 4.2, 0.01, 1000.0, 7.0, None, None]
    assert _single_column(spark, ["<0,01", "4.2", None], is_censored) == [True, False, False]


def test_parse_bool(spark):
    assert _single_column(spark, ["Y", "ja", "true", "0", "nein", "maybe"], parse_bool) == [True, True, True, False, False, None]


def test_code_key_and_map_values(spark):
    mapping = {"ABETA42": "ABETA42", "ABETA142": "ABETA42"}
    out = _single_column(spark, ["Abeta1-42", "abeta 42", "tau"], lambda c: map_values(code_key(c), mapping, "UNMAPPED"))
    assert out == ["ABETA42", "ABETA42", "UNMAPPED"]


def test_normalize_study_code(spark):
    assert _single_column(spark, ["TL-001", "tl001", "TL 002", "XY-001"], normalize_study_code) == [
        "TL-001", "TL-001", "TL-002", None,
    ]


def test_age_band(spark):
    df = spark.createDataFrame([(45,), (50,), (79,), (80,), (None,)], "age int")
    assert [r[0] for r in df.select(age_band(F.col("age"))).collect()] == ["<50", "50-59", "70-79", "80+", "UNKNOWN"]


def test_pseudonym_is_stable_normalised_and_matches_python(spark):
    out = _single_column(spark, ["MRN1000001", " mrn1000001 ", "MRN1000002", "", None], lambda c: pseudonymize(c, SALT))
    assert out[0] == out[1]
    assert out[0] != out[2]
    assert out[3] is None and out[4] is None
    assert out[0].startswith("TL-P-") and len(out[0]) == 21
    assert out[0] == pseudonymize_value("MRN1000001", SALT)
    assert pseudonymize_value("MRN1000001", "another-salt") != out[0]

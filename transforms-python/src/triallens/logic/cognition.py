"""Cognitive assessments captured in the eCRF."""

from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from triallens.reference import HIGHER_IS_BETTER, IMPAIRMENT_THRESHOLD, INSTRUMENT_ALIASES, INSTRUMENT_MAX
from triallens.utils.columns import clean_str, code_key, map_values, parse_date, parse_decimal
from triallens.utils.pseudonymize import pseudonymize


def _lookup_double(c: Column, mapping: dict[str, float]) -> Column:
    return map_values(c, {k: str(v) for k, v in mapping.items()}).cast("double")


def normalize_visit_code(c: str | Column) -> Column:
    """``Baseline`` / ``V0`` -> ``BL``; ``M6`` / ``m-06`` -> ``M06``; anything else -> NULL."""
    key = code_key(c)
    return (
        F.when(key.isin("BL", "BASELINE", "V0", "V00", "SCREENING"), F.lit("BL"))
        .when(key.rlike("^M[0-9]{1,2}$"), F.concat(F.lit("M"), F.lpad(F.substring(key, 2, 2), 2, "0")))
        .otherwise(F.lit(None).cast("string"))
    )


def clean_cognitive_assessments(assessments: DataFrame, salt: str) -> DataFrame:
    instrument = map_values(code_key("instrument"), INSTRUMENT_ALIASES)
    score = parse_decimal("score")
    max_score = _lookup_double(instrument, INSTRUMENT_MAX)
    typed = assessments.select(
        clean_str("assessment_id").alias("assessment_id"),
        pseudonymize(F.col("mrn"), salt).alias("patient_id"),
        normalize_visit_code("visit_code").alias("visit_code"),
        instrument.alias("instrument"),
        # Scores outside the instrument's scale are data-entry errors and are dropped.
        F.when((score >= 0) & (score <= max_score), score).alias("score"),
        parse_date("assessed_date").alias("assessed_date"),
        clean_str("rater_id").alias("rater_id"),
    ).where(
        F.col("assessment_id").isNotNull()
        & F.col("patient_id").isNotNull()
        & F.col("visit_code").isNotNull()
        & F.col("instrument").isNotNull()
        & F.col("score").isNotNull()
        & F.col("assessed_date").isNotNull()
    )
    return typed.dropDuplicates(["assessment_id"])


def curate_cognitive_scores(assessments: DataFrame) -> DataFrame:
    instrument = F.col("instrument")
    score = F.col("score")
    max_score = _lookup_double(instrument, INSTRUMENT_MAX)
    threshold = _lookup_double(instrument, IMPAIRMENT_THRESHOLD)
    higher_is_better = map_values(instrument, {k: str(v).lower() for k, v in HIGHER_IS_BETTER.items()}).cast("boolean")
    return assessments.select(
        "assessment_id",
        F.concat_ws("-", F.col("patient_id"), F.col("visit_code")).alias("visit_id"),
        "patient_id",
        "visit_code",
        "instrument",
        "score",
        max_score.alias("score_max"),
        # 1.0 = best possible performance, 0.0 = worst, comparable across instruments.
        F.round(F.when(higher_is_better, score / max_score).otherwise(1 - score / max_score), 4).alias(
            "score_normalized"
        ),
        F.coalesce(
            F.when(higher_is_better, score < threshold).otherwise(score >= threshold), F.lit(False)
        ).alias("impairment_flag"),
        "assessed_date",
        "rater_id",
    )

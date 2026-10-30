"""Column-level parsing helpers shared by the clean layer.

Upstream extracts are heterogeneous (German and ISO date formats, decimal commas,
censored values such as ``<0.5``, free-text codes). These helpers turn raw string
columns into typed columns and return NULL - never raise - on unparseable input, so
that bad rows can be filtered and counted instead of failing a build.

Requires ``spark.sql.legacy.timeParserPolicy=CORRECTED`` (set on the Foundry profile
and in the local session) so that non-matching date patterns yield NULL.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

DATE_FORMATS = ("yyyy-MM-dd", "dd.MM.yyyy", "yyyyMMdd", "MM/dd/yyyy")
TIMESTAMP_FORMATS = (
    "yyyy-MM-dd'T'HH:mm:ss",
    "yyyy-MM-dd HH:mm:ss",
    "dd.MM.yyyy HH:mm",
    "dd.MM.yyyy HH:mm:ss",
    "yyyy-MM-dd",
)
_NUMBER_PATTERN = r"^-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?$"

TRUE_TOKENS = ("Y", "YES", "TRUE", "T", "1", "J", "JA")
FALSE_TOKENS = ("N", "NO", "FALSE", "F", "0", "NEIN")


def col(c: str | Column) -> Column:
    return F.col(c) if isinstance(c, str) else c


def clean_str(c: str | Column) -> Column:
    """Trim; empty strings become NULL."""
    trimmed = F.trim(col(c))
    return F.when(trimmed == "", F.lit(None).cast("string")).otherwise(trimmed)


def upper_str(c: str | Column) -> Column:
    return F.upper(clean_str(c))


def code_key(c: str | Column) -> Column:
    """Normalise a free-text code for dictionary lookup: upper case, alphanumerics only."""
    return F.regexp_replace(upper_str(c), "[^A-Z0-9]", "")


def parse_date(c: str | Column) -> Column:
    value = clean_str(c)
    return F.coalesce(*[F.to_date(value, fmt) for fmt in DATE_FORMATS])


def parse_timestamp(c: str | Column) -> Column:
    value = clean_str(c)
    return F.coalesce(*[F.to_timestamp(value, fmt) for fmt in TIMESTAMP_FORMATS])


def parse_decimal(c: str | Column) -> Column:
    """Parse a number, accepting decimal commas and stripping censoring symbols (<, >)."""
    value = F.regexp_replace(F.regexp_replace(clean_str(c), ",", "."), r"[<>=\s]", "")
    return F.when(value.rlike(_NUMBER_PATTERN), value.cast("double"))


def is_censored(c: str | Column) -> Column:
    """True when a raw numeric value carries a censoring symbol (e.g. ``<0.5``)."""
    return F.coalesce(clean_str(c).rlike(r"^[<>]"), F.lit(False))


def parse_bool(c: str | Column) -> Column:
    value = upper_str(c)
    return (
        F.when(value.isin(*TRUE_TOKENS), F.lit(True))
        .when(value.isin(*FALSE_TOKENS), F.lit(False))
        .otherwise(F.lit(None).cast("boolean"))
    )


def map_values(c: str | Column, mapping: Mapping[str, str], default: str | None = None) -> Column:
    """Dictionary lookup on a column; unmapped values become ``default``."""
    pairs: list[Column] = []
    for key, value in mapping.items():
        pairs.extend([F.lit(key), F.lit(value)])
    lookup = F.create_map(*pairs)[col(c)]
    if default is None:
        return lookup
    return F.coalesce(lookup, F.lit(default))


def in_range_or_null(c: Column, low: float, high: float) -> Column:
    return F.when((c >= low) & (c <= high), c)


def latest_per_key(df: DataFrame, keys: Iterable[str], order_col: str) -> DataFrame:
    """Keep the most recent row per key (NULL ordering values lose)."""
    window = Window.partitionBy(*keys).orderBy(F.col(order_col).desc_nulls_last())
    return df.withColumn("_rn", F.row_number().over(window)).where(F.col("_rn") == 1).drop("_rn")


def age_band(age: Column) -> Column:
    return (
        F.when(age.isNull(), "UNKNOWN")
        .when(age < 50, "<50")
        .when(age < 60, "50-59")
        .when(age < 70, "60-69")
        .when(age < 80, "70-79")
        .otherwise("80+")
    )


def normalize_study_code(c: str | Column) -> Column:
    """``tl001`` / ``TL 001`` / ``TL-001`` -> ``TL-001``; anything else -> NULL."""
    key = code_key(c)
    return F.when(key.rlike("^TL[0-9]{3}$"), F.concat(F.lit("TL-"), F.substring(key, 3, 3)))

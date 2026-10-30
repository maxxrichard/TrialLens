"""Keyed pseudonymisation of patient identifiers (GDPR Art. 4(5)).

Medical record numbers (MRNs) never leave the clean-layer transforms: they are replaced
by ``TL-P-<16 hex>`` = first 64 bits of SHA-256(salt | normalised MRN). The salt lives
in a restricted dataset, so re-identification requires both the salt and the MRN
list, which only the data protection officer's group can access.

The Spark and pure-Python implementations below are kept bit-for-bit identical; a
unit test enforces this so that LIMS / notebook integrations can compute the same
pseudonym outside Spark.
"""

from __future__ import annotations

import hashlib
import re

from pyspark.sql import Column
from pyspark.sql import functions as F

PREFIX = "TL-P-"
DIGEST_CHARS = 16


def _normalize_py(value: str) -> str:
    return re.sub(r"\s+", "", value).upper()


def pseudonymize_value(value: str | None, salt: str) -> str | None:
    if value is None:
        return None
    normalized = _normalize_py(value)
    if not normalized:
        return None
    digest = hashlib.sha256(f"{salt}|{normalized}".encode()).hexdigest()
    return PREFIX + digest[:DIGEST_CHARS].upper()


def pseudonymize(c: str | Column, salt: str) -> Column:
    column = F.col(c) if isinstance(c, str) else c
    normalized = F.upper(F.regexp_replace(column, r"\s+", ""))
    digest = F.sha2(F.concat(F.lit(salt), F.lit("|"), normalized), 256)
    return F.when(normalized.isNull() | (normalized == ""), F.lit(None).cast("string")).otherwise(
        F.concat(F.lit(PREFIX), F.upper(F.substring(digest, 1, DIGEST_CHARS)))
    )

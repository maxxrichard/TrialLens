"""Build the backing dataset of every ontology object type from its YAML definition.

Backing kinds (``backing:`` in ontology/object_types/*.yaml):

* ``source`` (+ optional ``filter``, ``group_by``/``aggregations``, ``columns``):
  projection of a clean or curated dataset onto the object's properties.
* ``builder``: a named Python builder (reference data, data-quality objects).
* ``writeback: true``: objects created only through Actions; the backing dataset is an
  empty, correctly typed seed and edits live in the ontology's writeback dataset.

After any of these, columns are cast to the declared property types, rows without a
primary key are dropped and the primary key is de-duplicated.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import reduce

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

from triallens.config import load_expectations, load_sources
from triallens.datasets import dataset_path, logical
from triallens.logic.lab import reference_ranges_df
from triallens.ontology_spec import ObjectType
from triallens.quality.record_rules import RECORD_RULES
from triallens.reference import BIOMARKER_CATALOG

SPARK_TYPES: dict[str, T.DataType] = {
    "string": T.StringType(),
    "integer": T.IntegerType(),
    "long": T.LongType(),
    "double": T.DoubleType(),
    "boolean": T.BooleanType(),
    "date": T.DateType(),
    "timestamp": T.TimestampType(),
}


def schema_for(obj: ObjectType) -> T.StructType:
    return T.StructType([T.StructField(p, SPARK_TYPES[t], True) for p, t in obj.properties.items()])


# ------------------------------------------------------------------- builders


@dataclass(frozen=True)
class Builder:
    inputs: tuple[str, ...]
    fn: Callable[[Mapping[str, DataFrame], SparkSession], DataFrame]


def _biomarker_catalog(_: Mapping[str, DataFrame], spark: SparkSession) -> DataFrame:
    return spark.createDataFrame(
        BIOMARKER_CATALOG,
        "analyte string, display_name string, category string, matrix string, unit string, description string",
    )


def _reference_ranges(_: Mapping[str, DataFrame], spark: SparkSession) -> DataFrame:
    return reference_ranges_df(spark)


def _data_sources(_: Mapping[str, DataFrame], spark: SparkSession) -> DataFrame:
    rows = [
        (
            s["name"],
            s["display_name"],
            s["system"],
            s["domain"],
            s["format"],
            s["refresh"],
            s["owner_team"],
            bool(s["contains_personal_data"]),
            ",".join(s.get("markings", [])),
            dataset_path(logical("raw", s["name"])),
        )
        for s in load_sources()
    ]
    return spark.createDataFrame(
        rows,
        "source_id string, display_name string, source_system string, domain string, ingestion_format string, "
        "refresh_cadence string, owner_team string, contains_personal_data boolean, markings string, "
        "raw_dataset_path string",
    )


def _data_quality_checks(_: Mapping[str, DataFrame], spark: SparkSession) -> DataFrame:
    rows = []
    for dataset, items in load_expectations().items():
        for exp in items:
            rows.append(
                (
                    f"{dataset}:{exp['name']}",
                    exp["name"],
                    "DATASET_EXPECTATION",
                    dataset,
                    exp.get("column"),
                    exp["kind"],
                    "CRITICAL" if exp.get("on_error", "FAIL") == "FAIL" else "MEDIUM",
                    exp.get("on_error", "FAIL"),
                    "Build-blocking expectation" if exp.get("on_error", "FAIL") == "FAIL" else "Warning expectation",
                )
            )
    for rule in RECORD_RULES:
        rows.append(
            (
                rule.check_id,
                rule.code,
                "RECORD_RULE",
                rule.dataset.split("/", 1)[1],
                rule.record_id_column,
                "record_rule",
                rule.severity,
                "ISSUE",
                rule.description,
            )
        )
    return spark.createDataFrame(
        rows,
        "check_id string, check_name string, check_type string, dataset string, column_name string, "
        "kind string, severity string, on_error string, description string",
    )


def _data_quality_issues(datasets: Mapping[str, DataFrame], spark: SparkSession) -> DataFrame:
    frames = []
    for rule in RECORD_RULES:
        record_id = F.col(rule.record_id_column).cast("string")
        frames.append(
            datasets[rule.dataset]
            .where(F.expr(rule.condition))
            .select(
                F.substring(F.sha2(F.concat_ws("|", F.lit(rule.check_id), record_id), 256), 1, 20).alias("issue_id"),
                F.lit(rule.check_id).alias("check_id"),
                F.lit(rule.code).alias("rule_code"),
                F.lit(rule.severity).alias("severity"),
                F.lit(rule.dataset.split("/", 1)[1]).alias("source_dataset"),
                record_id.alias("record_id"),
                F.col("patient_id"),
                F.lit("OPEN").alias("status"),
                F.lit(None).cast("string").alias("assignee"),
                F.lit(None).cast("string").alias("resolution_note"),
                F.current_date().alias("detected_date"),
                F.lit(rule.description).alias("description"),
            )
        )
    return reduce(DataFrame.unionByName, frames)


BUILDERS: dict[str, Builder] = {
    "biomarker_catalog": Builder((), _biomarker_catalog),
    "reference_ranges": Builder((), _reference_ranges),
    "data_sources": Builder((), _data_sources),
    "data_quality_checks": Builder((), _data_quality_checks),
    "data_quality_issues": Builder(tuple(sorted({r.dataset for r in RECORD_RULES})), _data_quality_issues),
}


# ------------------------------------------------------------------ backing


def required_inputs(obj: ObjectType) -> list[str]:
    if obj.is_writeback:
        return []
    if obj.builder:
        return list(BUILDERS[obj.builder].inputs)
    return [obj.source]


def build_object_backing(obj: ObjectType, datasets: Mapping[str, DataFrame], spark: SparkSession) -> DataFrame:
    if obj.is_writeback:
        return spark.createDataFrame([], schema_for(obj))

    if obj.builder:
        df = BUILDERS[obj.builder].fn(datasets, spark)
    else:
        df = datasets[obj.source]

    backing = obj.backing
    if backing.get("filter"):
        df = df.where(F.expr(backing["filter"]))
    if backing.get("group_by"):
        aggregations = [F.expr(expr).alias(name) for name, expr in backing.get("aggregations", {}).items()]
        df = df.groupBy(*backing["group_by"]).agg(*aggregations) if aggregations else df.select(*backing["group_by"]).distinct()

    columns = backing.get("columns", {})
    projected = df.select(
        *[
            (F.expr(columns[prop]) if prop in columns else F.col(prop)).cast(SPARK_TYPES[ptype]).alias(prop)
            for prop, ptype in obj.properties.items()
        ]
    )
    return projected.where(F.col(obj.primary_key).isNotNull()).dropDuplicates([obj.primary_key])

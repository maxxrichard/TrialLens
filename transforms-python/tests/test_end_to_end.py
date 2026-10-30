"""End-to-end: synthetic extracts -> full pipeline -> expectations, ontology contract, SQL."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from pyspark.sql import functions as F

from triallens.config import load_sources, repo_root
from triallens.local.runner import run_pipeline
from triallens.local.synthetic import generate
from triallens.ontology_backing import SPARK_TYPES
from triallens.ontology_spec import load_link_types, load_object_types, object_types_by_name
from triallens.quality.engine import evaluate_all, summarize

pytestmark = pytest.mark.e2e

MIN_LINK_INTEGRITY = 0.98


@pytest.fixture(scope="module")
def raw_dir(tmp_path_factory) -> Path:
    directory = tmp_path_factory.mktemp("raw")
    generate(directory, n_patients=150, seed=11)
    return directory


@pytest.fixture(scope="module")
def run(spark, raw_dir):
    return run_pipeline(spark, raw_dir)


def test_generator_writes_every_source_with_declared_columns(raw_dir):
    for source in load_sources():
        with (raw_dir / f"{source['name']}.csv").open(encoding="utf-8") as handle:
            reader = csv.reader(handle)
            assert next(reader) == source["columns"]
            assert sum(1 for _ in reader) > 0, source["name"]


def test_all_120_expectations_pass(run):
    results = evaluate_all({**run.by_name("clean"), **run.by_name("curated")})
    assert len(results) == 120
    assert all(r.passed for r in results), summarize(results)


def test_no_mrn_reaches_curated_or_ontology(run):
    for key, df in run.datasets.items():
        if key.startswith(("curated/", "ontology/")):
            assert "mrn" not in df.columns, key
            conditions = [F.col(c).rlike("(?i)^\\s*MRN[0-9]+") for c, dtype in df.dtypes if dtype == "string"]
            if conditions:
                leaked = df.where(F.coalesce(*[F.when(c, F.lit(True)) for c in conditions], F.lit(False)))
                assert leaked.count() == 0, key


def test_ontology_backing_datasets_match_object_types(run):
    for obj in load_object_types():
        df = run[obj.backing_dataset]
        assert df.columns == list(obj.properties), obj.api_name
        for field in df.schema.fields:
            assert field.dataType == SPARK_TYPES[obj.properties[field.name]], (obj.api_name, field.name)
        assert df.where(F.col(obj.primary_key).isNull()).count() == 0, obj.api_name
        assert df.count() == df.select(obj.primary_key).distinct().count(), obj.api_name
        if not obj.is_writeback:
            assert df.count() > 0, f"{obj.api_name} has no objects"


def test_link_referential_integrity(run):
    objects = object_types_by_name()
    for link in load_link_types():
        one, many = objects[link["one"]], objects[link["many"]]
        keys = run[many.backing_dataset].select(F.col(link["foreignKey"]).alias("k")).where(F.col("k").isNotNull())
        total = keys.count()
        if total == 0:
            continue
        targets = run[one.backing_dataset].select(F.col(one.primary_key).alias("k"))
        resolved = keys.join(targets, "k", "left_semi").count()
        assert resolved / total >= MIN_LINK_INTEGRITY, f"{link['apiName']}: {resolved}/{total} resolve"


def test_record_rules_raise_issues(run):
    issues = run["ontology/data_quality_issue"]
    codes = {r["rule_code"] for r in issues.select("rule_code").distinct().collect()}
    assert {"BIOMARKER_QC_FAIL", "CSF_PREANALYTIC_DELAY"} <= codes


def test_cohort_features_are_plausible(run):
    features = run["curated/cohort_features"]
    assert features.count() == run["clean/ehr_patients_clean"].count()
    by_status = {r["amyloid_status"]: r["count"] for r in features.groupBy("amyloid_status").count().collect()}
    assert by_status.get("POSITIVE", 0) > 0 and by_status.get("NEGATIVE", 0) > 0
    assert features.where(F.col("apoe_genotype").isNotNull()).count() > 0


def test_sql_analyses_run(spark, run):
    for name, df in {**run.by_name("clean"), **run.by_name("curated")}.items():
        df.createOrReplaceTempView(name)
    sql_files = sorted((repo_root() / "sql").glob("*.sql"))
    assert len(sql_files) >= 5
    for path in sql_files:
        result = spark.sql(path.read_text(encoding="utf-8").strip().rstrip(";"))
        result.collect()

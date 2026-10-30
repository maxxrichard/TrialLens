"""Static checks of the pipeline configuration (no Spark jobs)."""

from __future__ import annotations

from collections import Counter

from triallens.config import EXPECTATION_KINDS, load_expectations, load_sources, source_names
from triallens.datasets import dataset_path, logical, name_of
from triallens.pipeline_spec import STEPS, step_outputs, validate_dag


def test_fourteen_sources_with_unique_names_and_columns():
    sources = load_sources()
    assert len(sources) == 14
    assert len(set(source_names())) == 14
    for source in sources:
        assert source["columns"], source["name"]
        assert len(set(source["columns"])) == len(source["columns"]), source["name"]
        assert source["markings"], source["name"]


def test_dag_is_valid_and_layered():
    validate_dag([logical("raw", n) for n in source_names()])
    layers = Counter(o.split("/", 1)[0] for o in step_outputs())
    assert layers == {"clean": 14, "curated": 10}


def test_every_raw_source_is_consumed_by_exactly_one_clean_step():
    consumed = Counter(d for s in STEPS for d in s.inputs.values() if d.startswith("raw/"))
    assert consumed == Counter(logical("raw", n) for n in source_names())


def test_120_expectations_five_per_dataset():
    expectations = load_expectations()
    assert sum(len(v) for v in expectations.values()) == 120
    assert all(len(v) == 5 for v in expectations.values())
    assert set(expectations) == {name_of(o) for o in step_outputs()}


def test_expectations_are_well_formed():
    for dataset, items in load_expectations().items():
        names = [e["name"] for e in items]
        assert len(names) == len(set(names)), dataset
        for exp in items:
            assert exp["kind"] in EXPECTATION_KINDS, (dataset, exp)
            if exp["kind"] != "row_count_min":
                assert exp.get("column"), (dataset, exp)
            if exp["kind"] == "in_set":
                assert exp["values"], (dataset, exp)
            if exp["kind"] == "range":
                assert exp["min"] <= exp["max"], (dataset, exp)
            assert exp.get("on_error", "FAIL") in ("FAIL", "WARN")


def test_dataset_paths():
    assert dataset_path("clean/ehr_patients_clean") == "/TrialLens/data/clean/ehr_patients_clean"

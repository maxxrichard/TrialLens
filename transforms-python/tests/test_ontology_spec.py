"""Static consistency checks of the ontology definitions."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

from triallens.config import repo_root
from triallens.ontology_backing import BUILDERS
from triallens.ontology_spec import (
    PROPERTY_TYPES,
    camel_case,
    load_action_types,
    load_link_types,
    load_object_types,
    object_types_by_name,
    snake_case,
)
from triallens.pipeline_spec import step_outputs

DOMAINS = {"clinical", "study", "lab_biomarker", "specimen", "imaging", "omics", "cohort", "governance"}


def _markings() -> set[str]:
    doc = yaml.safe_load((repo_root() / "markings" / "markings.yaml").read_text())
    return {m["id"] for m in doc["markings"]}


def _groups() -> set[str]:
    doc = yaml.safe_load((repo_root() / "markings" / "markings.yaml").read_text())
    return {g["id"] for g in doc["groups"]}


def test_35_object_types_in_8_domains():
    objects = load_object_types()
    assert len(objects) == 35
    assert {o.domain for o in objects} == DOMAINS
    assert len({o.api_name for o in objects}) == 35
    assert len({o.backing_dataset for o in objects}) == 35


def test_object_type_definitions():
    markings = _markings()
    outputs = set(step_outputs())
    for obj in load_object_types():
        assert obj.primary_key in obj.properties, obj.api_name
        assert obj.properties[obj.primary_key] in ("string", "integer", "long"), obj.api_name
        assert obj.title_property in obj.properties, obj.api_name
        assert set(obj.properties.values()) <= set(PROPERTY_TYPES), obj.api_name
        assert obj.markings and set(obj.markings) <= markings, obj.api_name
        assert set(obj.editable_properties) <= set(obj.properties), obj.api_name
        kinds = [k for k in ("source", "builder", "writeback") if obj.backing.get(k)]
        assert len(kinds) == 1, obj.api_name
        if obj.source:
            assert obj.source in outputs, (obj.api_name, obj.source)
        if obj.builder:
            assert obj.builder in BUILDERS, obj.api_name
        for column in obj.backing.get("columns", {}):
            assert column in obj.properties, (obj.api_name, column)


def test_link_types_reference_existing_objects_and_typed_keys():
    objects = object_types_by_name()
    links = load_link_types()
    assert len({link["apiName"] for link in links}) == len(links)
    for link in links:
        one, many = objects[link["one"]], objects[link["many"]]
        fk = link["foreignKey"]
        assert fk in many.properties, link["apiName"]
        assert many.properties[fk] == one.properties[one.primary_key], link["apiName"]


def test_every_object_type_is_linked():
    linked = Counter()
    for link in load_link_types():
        linked[link["one"]] += 1
        linked[link["many"]] += 1
    unlinked = {o.api_name for o in load_object_types()} - set(linked)
    assert unlinked == {"DataSource"}  # catalogue entry, navigated by name


def test_action_types_reference_existing_objects_groups_and_functions():
    objects = object_types_by_name()
    groups = _groups()
    ts_sources = "\n".join(
        p.read_text() for p in (repo_root() / "functions-typescript" / "src" / "foundry").glob("*.ts")
    )
    actions = load_action_types()
    assert len(actions) == 7
    for action in actions:
        for param in action["parameters"]:
            if "objectType" in param:
                assert param["objectType"] in objects, (action["apiName"], param)
        for edit in action["edits"]:
            assert edit["objectType"] in objects, action["apiName"]
            for prop in edit.get("properties", {}):
                assert prop in objects[edit["objectType"]].properties, (action["apiName"], prop)
        for criterion in action["submissionCriteria"]:
            if criterion["type"] == "groupMembership":
                assert set(criterion["groups"]) <= groups, action["apiName"]
        function = action["backing"].get("function")
        if function:
            assert f"public async {function}(" in ts_sources, f"missing Foundry function {function}"


def test_writeback_objects_are_only_created_by_actions():
    created = {e["objectType"] for a in load_action_types() for e in a["edits"] if e["operation"] == "create"}
    writeback = {o.api_name for o in load_object_types() if o.is_writeback}
    assert writeback <= created


def test_name_helpers():
    assert snake_case("BiomarkerMeasurement") == "biomarker_measurement"
    assert camel_case("latest_ptau217") == "latestPtau217"
    assert Path(repo_root() / "ontology").is_dir()

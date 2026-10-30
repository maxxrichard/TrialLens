"""Workshop / Quiver / AIP Logic / Pipeline Builder specs reference valid ontology entities."""

from __future__ import annotations

import importlib.util

from triallens.config import repo_root


def _validator_module():
    path = repo_root() / "tools" / "validate_specs.py"
    spec = importlib.util.spec_from_file_location("validate_specs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_specs_are_consistent_with_ontology():
    validator = _validator_module().Validator()
    assert validator.run() == []


def test_all_backing_functions_are_discovered():
    validator = _validator_module().Validator()
    assert "CohortFunctions.createCohortFromCriteria" in validator.functions
    assert "AipTools.validateProposedCriteria" in validator.functions

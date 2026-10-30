"""Configuration loaders. Pure Python (no Spark) so specs can be validated anywhere."""

from __future__ import annotations

import os
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

EXPECTATION_KINDS = {"primary_key", "not_null", "in_set", "range", "regex", "row_count_min"}


def _read_yaml(filename: str) -> Any:
    text = resources.files("triallens.config").joinpath(filename).read_text(encoding="utf-8")
    return yaml.safe_load(text)


@lru_cache(maxsize=None)
def load_sources() -> tuple[dict[str, Any], ...]:
    """The 14 upstream sources, in declaration order."""
    return tuple(_read_yaml("sources.yaml")["sources"])


def source_names() -> list[str]:
    return [s["name"] for s in load_sources()]


@lru_cache(maxsize=None)
def load_expectations() -> dict[str, tuple[dict[str, Any], ...]]:
    """Expectations keyed by dataset name (the last segment of the logical dataset name)."""
    raw = _read_yaml("expectations.yaml")["datasets"]
    return {dataset: tuple(items) for dataset, items in raw.items()}


def expectations_for(dataset_name: str) -> tuple[dict[str, Any], ...]:
    return load_expectations().get(dataset_name, ())


def repo_root() -> Path:
    # transforms-python/src/triallens/config/__init__.py -> repository root
    return Path(__file__).resolve().parents[4]


def ontology_dir() -> Path:
    """Location of the ontology definitions (YAML).

    Resolution order: $TRIALLENS_ONTOLOGY_DIR, then <repo>/ontology. The release
    workflow vendors ontology/ into the Foundry repository at the same relative path.
    """
    override = os.environ.get("TRIALLENS_ONTOLOGY_DIR")
    return Path(override) if override else repo_root() / "ontology"

"""Logical dataset names and their Foundry paths.

Logical names look like ``<layer>/<name>`` (e.g. ``clean/ehr_patients_clean``) and are
used by the pipeline spec, the local runner and the Foundry transform generators alike.
"""

from __future__ import annotations

FOUNDRY_ROOT = "/TrialLens/data"
LAYERS = ("raw", "clean", "curated", "ontology")

# Restricted single-row dataset holding the pseudonymisation salt (column ``salt``).
# Only the pseudonymisation service user and the data protection officer can read it.
SALT_DATASET = "/TrialLens/secure/pseudonymization_key"


def logical(layer: str, name: str) -> str:
    if layer not in LAYERS:
        raise ValueError(f"unknown layer {layer!r}")
    return f"{layer}/{name}"


def layer_of(logical_name: str) -> str:
    return logical_name.split("/", 1)[0]


def name_of(logical_name: str) -> str:
    return logical_name.split("/", 1)[1]


def dataset_path(logical_name: str) -> str:
    layer = layer_of(logical_name)
    if layer not in LAYERS:
        raise ValueError(f"unknown layer in {logical_name!r}")
    return f"{FOUNDRY_ROOT}/{logical_name}"


def param_name(logical_name: str) -> str:
    """A valid Python identifier for a logical dataset (used as transform input name)."""
    return logical_name.replace("/", "__")

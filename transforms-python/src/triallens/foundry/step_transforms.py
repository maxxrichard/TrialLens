"""One Foundry transform per pipeline step (clean + curated layers).

Generated from triallens.pipeline_spec.STEPS; each output carries the data expectations
configured for it in config/expectations.yaml.
"""

from __future__ import annotations

from transforms.api import Input, Markings, Output, transform_df

from triallens.datasets import SALT_DATASET, dataset_path, layer_of
from triallens.pipeline_spec import STEPS, Step
from triallens.quality.foundry_checks import checks_for

# Marking IDs are resolved per environment by the release pipeline (see docs/release-management.md).
DIRECT_IDENTIFIERS_MARKING_ID = "{{ markings.TRIALLENS_DIRECT_IDENTIFIERS }}"


def _input_for(logical_name: str, step: Step) -> Input:
    # Curated steps read pseudonymised clean data only; the identifying fields are dropped
    # in the curated transforms, so the DIRECT_IDENTIFIERS marking stops propagating here.
    if layer_of(step.output) == "curated" and layer_of(logical_name) == "clean":
        return Input(
            dataset_path(logical_name),
            stop_propagating=Markings([DIRECT_IDENTIFIERS_MARKING_ID], on_branches=["master"]),
        )
    return Input(dataset_path(logical_name))


def _make_transform(step: Step):
    inputs = {param: _input_for(logical_name, step) for param, logical_name in step.inputs.items()}
    if step.needs_salt:
        inputs["pseudonymization_key"] = Input(SALT_DATASET)

    @transform_df(Output(dataset_path(step.output), checks=checks_for(step.name)), **inputs)
    def compute(**dataframes):
        kwargs = dict(dataframes)
        if step.needs_salt:
            kwargs["salt"] = kwargs.pop("pseudonymization_key").first()["salt"]
        return step.fn(**kwargs)

    compute.__name__ = f"compute_{step.name}"
    return compute


TRANSFORMS = [_make_transform(step) for step in STEPS]

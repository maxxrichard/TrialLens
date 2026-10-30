"""One Foundry transform per ontology object type, producing its backing dataset."""

from __future__ import annotations

from transforms.api import Input, Output, transform

from triallens.datasets import dataset_path, param_name
from triallens.ontology_backing import build_object_backing, required_inputs
from triallens.ontology_spec import ObjectType, load_object_types


def _make_transform(obj: ObjectType):
    logical_inputs = required_inputs(obj)
    inputs = {param_name(name): Input(dataset_path(name)) for name in logical_inputs}

    @transform(out=Output(dataset_path(obj.backing_dataset)), **inputs)
    def compute(ctx, out, **transform_inputs):
        datasets = {name: transform_inputs[param_name(name)].dataframe() for name in logical_inputs}
        out.write_dataframe(build_object_backing(obj, datasets, ctx.spark_session))

    compute.__name__ = f"compute_{obj.backing_name}"
    return compute


TRANSFORMS = [_make_transform(obj) for obj in load_object_types()]

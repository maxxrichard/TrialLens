"""Foundry pipeline entry point (registered in transforms-python/setup.py)."""

from transforms.api import Pipeline

from triallens.foundry.ontology_transforms import TRANSFORMS as ONTOLOGY_TRANSFORMS
from triallens.foundry.step_transforms import TRANSFORMS as STEP_TRANSFORMS

my_pipeline = Pipeline()
my_pipeline.add_transforms(*STEP_TRANSFORMS, *ONTOLOGY_TRANSFORMS)

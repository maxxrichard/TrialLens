"""Foundry Python transforms repository setup (used by the Foundry build, not by local dev).

Local development installs the package from the repository root pyproject.toml.
"""

import os

from setuptools import find_packages, setup

setup(
    name=os.environ.get("PKG_NAME", "triallens"),
    version=os.environ.get("PKG_VERSION", "1.4.0"),
    description="TrialLens Foundry transforms",
    packages=find_packages(where="src", exclude=["contrib", "docs", "test"]),
    package_dir={"": "src"},
    package_data={"triallens": ["config/*.yaml"]},
    entry_points={"transforms.pipelines": ["root = triallens.pipeline:my_pipeline"]},
)

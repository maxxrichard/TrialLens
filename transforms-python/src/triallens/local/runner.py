"""Run the full TrialLens DAG locally: raw CSVs -> clean -> curated -> ontology backing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession

from triallens.config import source_names
from triallens.datasets import logical, name_of
from triallens.ontology_backing import build_object_backing, required_inputs
from triallens.ontology_spec import load_object_types
from triallens.pipeline_spec import STEPS, validate_dag

LOCAL_SALT = "local-development-salt-not-for-production"


@dataclass
class PipelineRun:
    datasets: dict[str, DataFrame] = field(default_factory=dict)  # keyed by logical name

    def by_name(self, layer: str | None = None) -> dict[str, DataFrame]:
        """Datasets keyed by their short name, optionally restricted to one layer."""
        return {
            name_of(key): df
            for key, df in self.datasets.items()
            if layer is None or key.startswith(f"{layer}/")
        }

    def __getitem__(self, logical_name: str) -> DataFrame:
        return self.datasets[logical_name]


def read_raw(spark: SparkSession, raw_dir: Path) -> dict[str, DataFrame]:
    frames = {}
    for name in source_names():
        path = raw_dir / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"raw source {name!r} not found at {path}")
        # Raw datasets are untyped: every column is read as a string, like the Foundry sync.
        frames[logical("raw", name)] = spark.read.option("header", True).option("multiLine", False).csv(str(path))
    return frames


def run_pipeline(
    spark: SparkSession,
    raw_dir: Path | str,
    salt: str = LOCAL_SALT,
    include_ontology: bool = True,
) -> PipelineRun:
    run = PipelineRun(read_raw(spark, Path(raw_dir)))
    validate_dag(list(run.datasets))

    for step in STEPS:
        kwargs = {param: run[name] for param, name in step.inputs.items()}
        if step.needs_salt:
            kwargs["salt"] = salt
        # Cache each step so downstream steps do not recompute the whole lineage.
        run.datasets[step.output] = step.fn(**kwargs).cache()

    if include_ontology:
        for obj in load_object_types():
            inputs = {name: run[name] for name in required_inputs(obj)}
            run.datasets[obj.backing_dataset] = build_object_backing(obj, inputs, spark).cache()
    return run


def write_run(run: PipelineRun, out_dir: Path | str, layers: tuple[str, ...] = ("clean", "curated", "ontology")) -> None:
    out = Path(out_dir)
    for key, df in run.datasets.items():
        if key.split("/", 1)[0] in layers:
            df.write.mode("overwrite").parquet(str(out / key))

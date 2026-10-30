"""Loader for the ontology definitions in <repo>/ontology (pure Python, no Spark)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from triallens.config import ontology_dir

PROPERTY_TYPES = ("string", "integer", "long", "double", "boolean", "date", "timestamp")


def snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def camel_case(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


@dataclass(frozen=True)
class ObjectType:
    api_name: str
    display_name: str
    plural_display_name: str
    description: str
    domain: str
    primary_key: str
    title_property: str
    markings: tuple[str, ...]
    properties: dict[str, str]  # property (= backing column) -> type
    backing: dict[str, Any]
    editable_properties: tuple[str, ...] = ()

    @property
    def backing_name(self) -> str:
        return snake_case(self.api_name)

    @property
    def backing_dataset(self) -> str:
        return f"ontology/{self.backing_name}"

    @property
    def is_writeback(self) -> bool:
        return bool(self.backing.get("writeback"))

    @property
    def builder(self) -> str | None:
        return self.backing.get("builder")

    @property
    def source(self) -> str | None:
        return self.backing.get("source")

    def property_api_name(self, prop: str) -> str:
        """Foundry property API names are the camelCase form of the backing column."""
        return camel_case(prop)


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def load_object_types(directory: str | None = None) -> tuple[ObjectType, ...]:
    base = Path(directory) if directory else ontology_dir()
    objects: list[ObjectType] = []
    for path in sorted((base / "object_types").glob("*.yaml")):
        doc = _load_yaml(path)
        domain = doc["domain"]
        for spec in doc["object_types"]:
            objects.append(
                ObjectType(
                    api_name=spec["apiName"],
                    display_name=spec["displayName"],
                    plural_display_name=spec.get("pluralDisplayName", spec["displayName"] + "s"),
                    description=spec.get("description", ""),
                    domain=domain,
                    primary_key=spec["primaryKey"],
                    title_property=spec.get("titleProperty", spec["primaryKey"]),
                    markings=tuple(spec.get("markings", ())),
                    properties=dict(spec["properties"]),
                    backing=dict(spec["backing"]),
                    editable_properties=tuple(spec.get("editableProperties", ())),
                )
            )
    return tuple(objects)


def object_types_by_name(directory: str | None = None) -> dict[str, ObjectType]:
    return {o.api_name: o for o in load_object_types(directory)}


@lru_cache(maxsize=None)
def load_link_types(directory: str | None = None) -> tuple[dict[str, Any], ...]:
    base = Path(directory) if directory else ontology_dir()
    return tuple(_load_yaml(base / "link_types.yaml")["link_types"])


@lru_cache(maxsize=None)
def load_action_types(directory: str | None = None) -> tuple[dict[str, Any], ...]:
    base = Path(directory) if directory else ontology_dir()
    return tuple(_load_yaml(base / "action_types.yaml")["action_types"])

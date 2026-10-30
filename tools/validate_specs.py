"""Validate Workshop, Quiver, AIP Logic and Pipeline Builder specs against the ontology.

Catches broken references before they reach Foundry: unknown object types, properties,
links, actions, action parameters, functions and AIP flows.

Usage: python tools/validate_specs.py   (exit code 1 on errors)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

from triallens.config import repo_root, source_names
from triallens.ontology_spec import load_action_types, load_link_types, object_types_by_name
from triallens.pipeline_spec import step_outputs

ROOT = repo_root()


class Validator:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.objects = object_types_by_name()
        self.links = {link["apiName"]: link for link in load_link_types()}
        self.actions = {a["apiName"]: a for a in load_action_types()}
        self.functions = self._ts_functions()
        self.flows = {p.stem for p in (ROOT / "aip-logic").glob("*.yaml")}

    @staticmethod
    def _ts_functions() -> set[str]:
        functions = set()
        for path in (ROOT / "functions-typescript" / "src" / "foundry").glob("*.ts"):
            text = path.read_text(encoding="utf-8")
            for cls in re.finditer(r"export class (\w+) \{(.*?)\n\}", text, re.S):
                for method in re.finditer(r"public (?:async )?(\w+)\(", cls.group(2)):
                    functions.add(f"{cls.group(1)}.{method.group(1)}")
        return functions

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    # ----------------------------------------------------------------- checks
    def object_type(self, where: str, name: str | None) -> bool:
        if name not in self.objects:
            self.error(where, f"unknown object type {name!r}")
            return False
        return True

    def properties(self, where: str, object_type: str, props: list[str]) -> None:
        known = self.objects[object_type].properties
        for prop in props:
            if prop not in known:
                self.error(where, f"{object_type} has no property {prop!r}")

    def function(self, where: str, name: str) -> None:
        if name not in self.functions:
            self.error(where, f"unknown function {name!r}")

    def link(self, where: str, name: str, target: str | None = None) -> None:
        link = self.links.get(name)
        if link is None:
            self.error(where, f"unknown link {name!r}")
        elif target and target not in (link["one"], link["many"]):
            self.error(where, f"link {name!r} does not reach {target}")

    # ----------------------------------------------------------- spec kinds
    def workshop(self, path: Path) -> None:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        variables = {}
        for var in spec.get("variables", []):
            variables[var["id"]] = var
            if var["type"] in ("object", "objectSet"):
                self.object_type(f"{path.name}:{var['id']}", var.get("objectType"))
        for page in spec["pages"]:
            for widget in page["widgets"]:
                self._widget(f"{path.name}:{page['id']}.{widget['id']}", widget, variables)

    def _widget(self, where: str, widget: dict[str, Any], variables: dict[str, Any]) -> None:
        for name in widget.get("writes", []) + widget.get("inputs", []):
            if name not in variables:
                self.error(where, f"unknown variable {name!r}")
        if "function" in widget:
            self.function(where, widget["function"])
        if "orderFunction" in widget:
            self.function(where, widget["orderFunction"])
        for derived in widget.get("derivedColumns", []):
            self.function(where, derived["function"])
        if widget.get("type") == "aip-logic" and widget.get("flow") not in self.flows:
            self.error(where, f"unknown AIP Logic flow {widget.get('flow')!r}")

        object_type = widget.get("objectType")
        if object_type and self.object_type(where, object_type):
            props = list(widget.get("columns", []))
            props += [widget[k] for k in ("x", "y", "groupBy") if isinstance(widget.get(k), str)]
            for key in ("filter", "sort"):
                if key in widget:
                    props.append(widget[key]["property"])
            if "aggregation" in widget and "filter" in widget["aggregation"]:
                props.append(widget["aggregation"]["filter"]["property"])
            props += widget.get("filterFrom", {}).get("properties", [])
            self.properties(where, object_type, props)
            if "linkFrom" in widget:
                link_from = widget["linkFrom"]
                if link_from["variable"] not in variables:
                    self.error(where, f"unknown variable {link_from['variable']!r}")
                self.link(where, link_from["link"], object_type)

        for button in widget.get("actions", []):
            action = self.actions.get(button["action"])
            if action is None:
                self.error(where, f"unknown action {button['action']!r}")
                continue
            parameter_ids = {p["id"] for p in action["parameters"]}
            for param, variable in button.get("parameters", {}).items():
                if param not in parameter_ids:
                    self.error(where, f"action {button['action']} has no parameter {param!r}")
                if variable not in variables:
                    self.error(where, f"unknown variable {variable!r}")

    def aip_flow(self, path: Path) -> None:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        where = path.name
        for tool in spec.get("tools", []):
            self.function(where, tool["function"])
        for name in spec.get("data_access", {}).get("object_types", []):
            self.object_type(where, name)
        for item in spec.get("inputs", []):
            if "objectType" in item:
                self.object_type(where, item["objectType"])
        if not spec.get("guardrails"):
            self.error(where, "every AIP Logic flow must declare guardrails")

    def quiver(self, path: Path) -> None:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        types: dict[str, str] = {}
        for item in spec["inputs"]:
            where = f"{path.name}:{item['id']}"
            if self.object_type(where, item["objectType"]):
                types[item["id"]] = item["objectType"]
            if "linkFrom" in item:
                self.link(where, item["linkFrom"]["link"], item["objectType"])
        for card in spec["cards"]:
            where = f"{path.name}:{card['id']}"
            targets = [card["input"]] if "input" in card else card.get("inputs", [])
            for target in targets:
                object_type = types.get(target)
                if object_type is None:
                    continue  # derived card input
                props = [c["property"] for c in card.get("conditions", [])]
                props += [card[k] for k in ("x", "y") if isinstance(card.get(k), str)]
                props += card.get("rows", []) + card.get("properties", [])
                self.properties(where, object_type, props)

    def pipeline_builder(self, path: Path) -> None:
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        known = {f"raw/{n}" for n in source_names()} | set(step_outputs())
        for name in spec.get("inputs", []):
            if name not in known:
                self.error(path.name, f"unknown input dataset {name!r}")
        if spec.get("output") not in known:
            self.error(path.name, f"output {spec.get('output')!r} is not a pipeline dataset")

    def run(self) -> list[str]:
        workshop = sorted((ROOT / "workshop").glob("*.yaml"))
        if len(workshop) != 5:
            self.error("workshop", f"expected 5 Workshop apps, found {len(workshop)}")
        for path in workshop:
            self.workshop(path)
        for path in sorted((ROOT / "aip-logic").glob("*.yaml")):
            self.aip_flow(path)
        for path in sorted((ROOT / "quiver").glob("*.yaml")):
            self.quiver(path)
        for path in sorted((ROOT / "pipeline-builder").glob("*.yaml")):
            self.pipeline_builder(path)
        return self.errors


def main() -> int:
    errors = Validator().run()
    for error in errors:
        print(f"ERROR {error}")
    print(f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

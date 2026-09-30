from __future__ import annotations

import json
from importlib.resources import files
from urllib.parse import quote

import httpx
from celpy import Environment, json_to_cel
from jsonschema import Draft202012Validator

from .types import LabError, digest


class Registry:
    def __init__(self):
        self.contracts = json.loads(files("aclab").joinpath("data/contracts.json").read_text())
        meta = json.loads(files("aclab").joinpath("data/contract.schema.json").read_text())
        self.validators = {}
        self.programs = {}
        for name, contract in self.contracts.items():
            Draft202012Validator(meta).validate(contract)
            for direction in ("input", "output"):
                schema = contract[direction + "_schema"]
                Draft202012Validator.check_schema(schema)
                self.validators[(name, direction)] = Draft202012Validator(schema)
            for condition in contract["preconditions"] + contract["postconditions"]:
                env = Environment()
                self.programs[condition["cel"]] = env.program(env.compile(condition["cel"]))
        self.hash = digest(self.contracts)

    def get(self, name: str):
        if name not in self.contracts:
            raise LabError("UNKNOWN_TOOL", "Select an operation from the provided tool catalog")
        return self.contracts[name]

    def check(self, conditions: list[dict], context: dict):
        activation = {k: json_to_cel(v) for k, v in context.items()}
        for condition in conditions:
            try:
                valid = self.programs[condition["cel"]].evaluate(activation)
                if type(valid).__name__ != "BoolType" or not bool(valid):
                    return condition["id"]
            except Exception:
                return condition["id"]
        return None

    def local_validate(self, name: str, direction: str, instance):
        # JSON Schema permits arbitrary JSON; forbid nonfinite Python numbers on all paths.
        try:
            digest(instance)
        except (ValueError, TypeError):
            return ["Instance must be finite JSON"]
        errors = sorted(self.validators[(name, direction)].iter_errors(instance), key=lambda e: str(list(e.path)))
        return [f"/{'/'.join(map(str, e.path))}: {e.message}" for e in errors[:8]]

    def tool_descriptions(self, level: str):
        levels = ["baseline", "semantics", "counterexamples", "workflows", "recovery"]
        depth = levels.index(level)
        result = []
        for name, c in self.contracts.items():
            description = c["description"]
            extra = {}
            if depth >= 1:
                extra.update(intent=c["intent"], effects=c["effects"], preconditions=c["preconditions"], positive_examples=c["positive_examples"])
            if depth >= 2:
                extra["counterexamples"] = c["counterexamples"]
            if depth >= 3:
                extra["workflow"] = c["workflow"]
            if depth >= 4:
                extra["recovery"] = c["recovery"]
            if extra:
                description += "\nExplicit contract: " + json.dumps(extra, separators=(",", ":"))
            result.append({"name": name, "description": description, "parameters": c["input_schema"]})
        return result


class Validator:
    def __init__(self, registry: Registry, backend: str = "jsonschema", one_url: str = "http://127.0.0.1:8080", client=None):
        self.registry, self.backend, self.one_url = registry, backend, one_url.rstrip("/")
        self.client = client
        self.checked_remote: set[str] = set()

    async def validate(self, name: str, direction: str, instance):
        if self.backend == "jsonschema":
            return self.registry.local_validate(name, direction, instance)
        c = self.registry.get(name)
        schema_path = f"lab/{name}-{direction}"
        # Verify the remote schema matches this contract before accepting a remote verdict.
        if schema_path not in self.checked_remote:
            try:
                response = await self.client.get(f"{self.one_url}/{quote(schema_path, safe='/')}.json", headers={"Accept": "application/schema+json"})
                response.raise_for_status()
                remote = response.json()
                local = c[direction + "_schema"]
                # One may assign a root identifier to a self-contained input schema.
                # Only that exact canonical ID is normalized; constraints remain pinned.
                if isinstance(remote, dict) and "$id" not in local and '"$ref"' not in json.dumps(local) and remote.get("$id") == f"{self.one_url}/{schema_path}":
                    remote = {k: v for k, v in remote.items() if k != "$id"}
                remote_hash = digest(remote)
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                raise LabError("VALIDATOR_UNAVAILABLE", "Cannot fetch the pinned One schema") from exc
            if remote_hash != digest(c[direction + "_schema"]):
                raise LabError("REGISTRY_DRIFT", "One schema does not match the pinned local contract")
            self.checked_remote.add(schema_path)
        try:
            digest(instance)
            response = await self.client.post(f"{self.one_url}/self/v1/api/schemas/evaluate/{quote(schema_path, safe='/')}", json=instance)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or type(result.get("valid")) is not bool:
                raise ValueError("Missing Boolean validation result")
            return [] if result["valid"] else ["One/Blaze rejected the instance"]
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise LabError("VALIDATOR_UNAVAILABLE", "One validation failed; no silent fallback") from exc

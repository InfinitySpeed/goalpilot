"""Validated mission contracts. Commands are argv arrays, never shell strings."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class ContractError(ValueError):
    pass


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def positive(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ContractError(f"{name} must be a finite positive number")
    return value


def validate(contract: dict, *, require_checks: bool = True) -> dict:
    if not isinstance(contract, dict):
        raise ContractError("Mission must be a JSON object")
    for field in ("goal", "repo"):
        if not isinstance(contract.get(field), str) or not contract[field].strip():
            raise ContractError(f"Missing {field}")
    if not Path(contract["repo"]).is_dir():
        raise ContractError("Repository directory does not exist")
    checks = contract.get("checks")
    if not isinstance(checks, list) or (require_checks and not checks):
        raise ContractError("Executable acceptance checks must be an array and cannot be empty here")
    seen = set()
    for check in checks:
        if not isinstance(check, dict):
            raise ContractError("Checks must be objects")
        ident = check.get("id")
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ContractError("Check IDs must be nonempty and unique")
        seen.add(ident)
        if not isinstance(check.get("description"), str) or not check["description"].strip():
            raise ContractError("Every check needs a description")
        command = check.get("command")
        if not isinstance(command, list) or not command or any(not isinstance(x, str) or "\0" in x for x in command) or not command[0]:
            raise ContractError("Check command must be a nonempty argv array (no shell string)")
        positive(check.get("timeout_seconds", 30), "check timeout")
    budget = contract.setdefault("budget", {})
    if not isinstance(budget, dict):
        raise ContractError("budget must be an object")
    for key, default in (("max_calls", 4), ("wall_seconds", 600), ("attempt_seconds", 180), ("max_tokens", 100000)):
        budget.setdefault(key, default)
        positive(budget[key], key)
    if type(budget["max_calls"]) is not int or type(budget["max_tokens"]) is not int:
        raise ContractError("max_calls and max_tokens must be integers")
    if 'max_uncached_tokens' in budget:
        positive(budget['max_uncached_tokens'],'max_uncached_tokens')
        if type(budget['max_uncached_tokens']) is not int:
            raise ContractError('max_uncached_tokens must be an integer')
    scope = contract.setdefault("scope", "inferred")
    if scope not in ("inferred", "user_defined"):
        raise ContractError("scope must be inferred or user_defined")
    for field in ("assumptions", "milestones", "limitations"):
        contract.setdefault(field, [])
        if not isinstance(contract[field], list) or any(not isinstance(x, str) for x in contract[field]):
            raise ContractError(f"{field} must be an array of strings")
    return contract


def load_contract(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ContractError("Mission must be an object")
    repo = value.get("repo", "")
    if isinstance(repo, str):
        value["repo"] = str((path.parent / repo).resolve())
    return validate(value)


PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "milestones": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "checks": {"type": "array", "minItems": 1, "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "id": {"type": "string"}, "description": {"type": "string"},
                "command": {"type": "array", "items": {"type": "string"}},
                "timeout_seconds": {"type": "number"},
            }, "required": ["id", "description", "command", "timeout_seconds"]}},
    }, "required": ["assumptions", "milestones", "limitations", "checks"],
}

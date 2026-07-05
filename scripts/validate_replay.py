#!/usr/bin/env python
# scripts/validate_replay.py — Validate GameReplay JSON against schema v1.0
# Usage: python scripts/validate_replay.py <replay.json>

import json, sys, os
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "docs" / "specs" / "replay-schema-v1.0.json"

def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)

def validate_against_schema(instance, schema, path="$"):
    """Simple structural validator. For production use, consider jsonschema library."""
    errors = []

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected {schema['const']}, got {instance}")

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance} not in {schema['enum']}")

    if "type" in schema:
        expected = schema["type"]
        if isinstance(expected, list):
            valid = any(_check_type(instance, t) for t in expected)
        else:
            valid = _check_type(instance, expected)
        if not valid:
            errors.append(f"{path}: expected {expected}, got {type(instance).__name__}")

    if "required" in schema and isinstance(instance, dict):
        for key in schema["required"]:
            if key not in instance:
                errors.append(f"{path}: missing required key '{key}'")

    if "properties" in schema and isinstance(instance, dict):
        for key, prop_schema in schema["properties"].items():
            if key in instance:
                errors.extend(validate_against_schema(instance[key], prop_schema, f"{path}.{key}"))

    if "items" in schema:
        if isinstance(instance, list):
            item_schema = schema["items"]
            for i, item in enumerate(instance):
                errors.extend(validate_against_schema(item, item_schema, f"{path}[{i}]"))

    if "minimum" in schema and isinstance(instance, (int, float)):
        if instance < schema["minimum"]:
            errors.append(f"{path}: {instance} < min {schema['minimum']}")

    if "maximum" in schema and isinstance(instance, (int, float)):
        if instance > schema["maximum"]:
            errors.append(f"{path}: {instance} > max {schema['maximum']}")

    if "maxItems" in schema and isinstance(instance, list):
        if len(instance) > schema["maxItems"]:
            errors.append(f"{path}: {len(instance)} items exceeds max {schema['maxItems']}")

    return errors

def _check_type(instance, expected_type):
    if expected_type == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected_type == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected_type == "string":
        return isinstance(instance, str)
    if expected_type == "array":
        return isinstance(instance, list)
    if expected_type == "object":
        return isinstance(instance, dict)
    if expected_type == "null":
        return instance is None
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_replay.py <replay.json>")
        sys.exit(1)

    replay_path = sys.argv[1]
    if not os.path.exists(replay_path):
        print(f"ERROR: file not found: {replay_path}")
        sys.exit(1)

    schema = load_schema()
    with open(replay_path, encoding="utf-8") as f:
        replay = json.load(f)

    errors = validate_against_schema(replay, schema)

    if errors:
        print(f"FAIL: {len(errors)} validation error(s)")
        for e in errors[:20]:
            print(f"  {e}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more")
        sys.exit(1)
    else:
        print(f"OK: {replay_path} is valid GameReplay v1.0")
        print(f"  Turns: {len(replay.get('turns', []))}")
        print(f"  Winner: P{replay.get('result', {}).get('winner', '?')} via {replay.get('result', {}).get('victory_type', '?')}")
        sys.exit(0)

if __name__ == "__main__":
    main()

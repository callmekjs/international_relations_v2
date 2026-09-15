"""Strict-mode rules shared by function tools and Structured Outputs: every object sets
additionalProperties false and lists every property as required."""


def strict_schema_problems(schema: dict, path: str = "$") -> list[str]:
    problems = []
    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is not False:
            problems.append(f"{path}: additionalProperties must be false")
        if sorted(schema.get("required", [])) != sorted(properties):
            problems.append(f"{path}: required must list every property")
        for name, sub in properties.items():
            problems += strict_schema_problems(sub, f"{path}.{name}")
    if schema.get("type") == "array" or "array" in (schema.get("type") or []):
        problems += strict_schema_problems(schema.get("items", {}), f"{path}[]")
    return problems

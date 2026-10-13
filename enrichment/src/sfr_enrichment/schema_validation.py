"""Strict JSON shape validation independent of benchmark orchestration."""

from typing import Any


def check_schema(value: Any, contract: dict[str, Any]) -> None:
    kind = (
        "null"
        if value is None
        else "object"
        if isinstance(value, dict)
        else "array"
        if isinstance(value, list)
        else "string"
        if isinstance(value, str)
        else "other"
    )
    types = contract["type"]
    if kind not in (types if isinstance(types, list) else [types]) or (
        "enum" in contract and value not in contract["enum"]
    ):
        raise ValueError("Ответ не соответствует JSON schema")
    if kind == "object":
        properties = contract.get("properties", {})
        # Preserve the existing strict fixed-object contract. Only explicitly
        # typed additionalProperties introduces a dictionary of evidence.
        required = contract.get("required", list(properties))
        additional = contract.get("additionalProperties", False)
        if not set(required) <= set(value) or (
            additional is False and set(value) - set(properties)
        ):
            raise ValueError("Лишние или отсутствующие поля JSON schema")
        for key, item in value.items():
            if key in properties:
                check_schema(item, properties[key])
            elif isinstance(additional, dict):
                check_schema(item, additional)
    elif kind == "array":
        if len(value) < contract.get("minItems", 0):
            raise ValueError("Пустой обязательный массив")
        for item in value:
            check_schema(item, contract["items"])

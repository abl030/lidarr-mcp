"""Extract parameter types from OpenAPI schemas.

Handles:
- Path parameters ({id})
- Query parameters
- Request body (JSON)
- $ref resolution
- allOf/oneOf/anyOf composition
- readOnly field exclusion
- Large integer sanitization (>= 2^53)
- Conditional required field downgrade
"""

from __future__ import annotations

from typing import Any


# Sentinel: integers >= 2^53 are unsafe for JSON serialization
MAX_SAFE_INT = 2**53


def parse_parameters(
    spec: dict[str, Any],
    operation: dict[str, Any],
    path_params: list[str],
) -> list[dict[str, Any]]:
    """Parse all parameters for an operation.

    Returns a list of parameter dicts with:
      name, type, required, default, description, enum, location
    """
    # TODO: Implement in Sprint 1
    return []


def resolve_schema_type(
    spec: dict[str, Any],
    schema: dict[str, Any],
) -> str:
    """Resolve an OpenAPI schema to a Python type string.

    Handles $ref, allOf, arrays, enums, etc.
    Returns: 'str', 'int', 'float', 'bool', 'dict[str, Any]', 'list[dict[str, Any]]', etc.
    """
    # TODO: Implement in Sprint 1
    return "Any"

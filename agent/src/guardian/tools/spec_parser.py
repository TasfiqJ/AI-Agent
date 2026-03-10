"""OpenAPI/Swagger spec parser — extract endpoints with schemas."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


async def openapi_parse(path: str, repo_path: str = ".") -> list[dict[str, Any]]:
    """Parse an OpenAPI 3.x or Swagger 2.x spec file.

    Returns a list of endpoint definitions with method, path, params, and response schemas.
    """
    full_path = Path(repo_path) / path
    if not full_path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")

    content = full_path.read_text(encoding="utf-8")

    if full_path.suffix in (".yaml", ".yml"):
        spec = yaml.safe_load(content)
    elif full_path.suffix == ".json":
        spec = json.loads(content)
    else:
        # Try YAML first, then JSON
        try:
            spec = yaml.safe_load(content)
        except yaml.YAMLError:
            spec = json.loads(content)

    if not isinstance(spec, dict):
        raise ValueError(f"Invalid spec format in {path}")

    # Detect OpenAPI version
    if "openapi" in spec:
        return _parse_openapi_3(spec)
    elif "swagger" in spec:
        return _parse_swagger_2(spec)
    else:
        raise ValueError(f"Cannot detect OpenAPI/Swagger version in {path}")


def _parse_openapi_3(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse OpenAPI 3.x spec."""
    endpoints: list[dict[str, Any]] = []
    paths = spec.get("paths", {})

    for path, methods in paths.items():
        # Collect path-level parameters
        path_params = methods.get("parameters", [])

        for method in ("get", "post", "put", "patch", "delete"):
            if method not in methods:
                continue

            operation = methods[method]
            params = _extract_params(
                path_params + operation.get("parameters", [])
            )

            # Extract request body schema
            request_body = operation.get("requestBody", {})
            body_schema = _extract_body_schema_v3(request_body)

            # Extract response schema (200 or 201)
            response_schema = _extract_response_schema_v3(
                operation.get("responses", {})
            )

            endpoints.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId", ""),
                    "summary": operation.get("summary", ""),
                    "params": params,
                    "request_body": body_schema,
                    "response_schema": response_schema,
                    "security": operation.get("security", []),
                }
            )

    return endpoints


def _parse_swagger_2(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse Swagger 2.x spec."""
    endpoints: list[dict[str, Any]] = []
    paths = spec.get("paths", {})

    for path, methods in paths.items():
        path_params = methods.get("parameters", [])

        for method in ("get", "post", "put", "patch", "delete"):
            if method not in methods:
                continue

            operation = methods[method]
            all_params = path_params + operation.get("parameters", [])
            params = _extract_params(all_params)

            body_param = next(
                (p for p in all_params if p.get("in") == "body"), None
            )
            body_schema = body_param.get("schema", {}) if body_param else {}

            response_schema = _extract_response_schema_v2(
                operation.get("responses", {})
            )

            endpoints.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId", ""),
                    "summary": operation.get("summary", ""),
                    "params": params,
                    "request_body": body_schema,
                    "response_schema": response_schema,
                    "security": operation.get("security", []),
                }
            )

    return endpoints


def _extract_params(params: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract parameter definitions."""
    result = []
    for p in params:
        result.append(
            {
                "name": p.get("name", ""),
                "in": p.get("in", ""),
                "required": p.get("required", False),
                "schema": p.get("schema", {}),
            }
        )
    return result


def _extract_body_schema_v3(
    request_body: dict[str, Any],
) -> dict[str, Any]:
    """Extract request body schema from OpenAPI 3.x."""
    content = request_body.get("content", {})
    json_content = content.get("application/json", {})
    return json_content.get("schema", {})


def _extract_response_schema_v3(
    responses: dict[str, Any],
) -> dict[str, Any]:
    """Extract response schema from the first success response."""
    for code in ("200", "201", "202"):
        if code in responses:
            content = responses[code].get("content", {})
            json_content = content.get("application/json", {})
            return json_content.get("schema", {})
    return {}


def _extract_response_schema_v2(
    responses: dict[str, Any],
) -> dict[str, Any]:
    """Extract response schema from Swagger 2.x."""
    for code in ("200", "201", "202"):
        if code in responses:
            return responses[code].get("schema", {})
    return {}

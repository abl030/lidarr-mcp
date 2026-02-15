"""Tests for schema_parser — parameter extraction from OpenAPI operations."""

from generator.loader import load_spec
from generator.schema_parser import (
    parse_parameters,
    resolve_schema_type,
    get_response_type,
)


def _spec():
    return load_spec()


# ── resolve_schema_type ───────────────────────────────────────────────


def test_string_type():
    assert resolve_schema_type({}, {"type": "string"}) == "str"


def test_integer_type():
    assert resolve_schema_type({}, {"type": "integer"}) == "int"


def test_number_type():
    assert resolve_schema_type({}, {"type": "number"}) == "float"


def test_boolean_type():
    assert resolve_schema_type({}, {"type": "boolean"}) == "bool"


def test_object_type():
    assert resolve_schema_type({}, {"type": "object"}) == "dict"


def test_properties_implies_dict():
    assert resolve_schema_type({}, {"properties": {"a": {"type": "string"}}}) == "dict"


def test_array_of_strings():
    assert resolve_schema_type({}, {"type": "array", "items": {"type": "string"}}) == "list[str]"


def test_array_of_integers():
    assert resolve_schema_type({}, {"type": "array", "items": {"type": "integer"}}) == "list[int]"


def test_enum_resolves_to_str():
    assert resolve_schema_type({}, {"enum": ["a", "b", "c"], "type": "string"}) == "str"


def test_ref_resolves():
    spec = {
        "components": {
            "schemas": {
                "Foo": {"type": "object", "properties": {"x": {"type": "string"}}}
            }
        }
    }
    assert resolve_schema_type(spec, {"$ref": "#/components/schemas/Foo"}) == "dict"


def test_allof_with_ref_resolves_to_dict():
    spec = {
        "components": {
            "schemas": {
                "Bar": {"type": "object", "properties": {"y": {"type": "integer"}}}
            }
        }
    }
    schema = {"allOf": [{"$ref": "#/components/schemas/Bar"}]}
    assert resolve_schema_type(spec, schema) == "dict"


def test_array_with_ref_items():
    spec = {
        "components": {
            "schemas": {
                "Item": {"type": "object", "properties": {"id": {"type": "integer"}}}
            }
        }
    }
    schema = {"type": "array", "items": {"$ref": "#/components/schemas/Item"}}
    assert resolve_schema_type(spec, schema) == "list[dict]"


def test_empty_schema():
    assert resolve_schema_type({}, {}) == "Any"


# ── parse_parameters ─────────────────────────────────────────────────


def test_path_params():
    spec = _spec()
    # GET /api/v1/artist/{id} has a path param 'id'
    op = spec["paths"]["/api/v1/artist/{id}"]["get"]
    op["_method"] = "get"
    params = parse_parameters(spec, op, "/api/v1/artist/{id}")
    names = [p["name"] for p in params]
    assert "id" in names
    id_param = next(p for p in params if p["name"] == "id")
    assert id_param["location"] == "path"
    assert id_param["required"] is True


def test_query_params():
    spec = _spec()
    # GET /api/v1/wanted/missing has query params page, pageSize, etc.
    op = spec["paths"]["/api/v1/wanted/missing"]["get"]
    op["_method"] = "get"
    params = parse_parameters(spec, op, "/api/v1/wanted/missing")
    names = [p["name"] for p in params]
    assert "page" in names
    assert "pageSize" in names
    page = next(p for p in params if p["name"] == "page")
    assert page["location"] == "query"
    assert page["default"] == 1


def test_body_params_from_schema():
    spec = _spec()
    # POST /api/v1/artist has a request body with ArtistResource
    op = spec["paths"]["/api/v1/artist"]["post"]
    op["_method"] = "post"
    params = parse_parameters(spec, op, "/api/v1/artist")
    body_params = [p for p in params if p["location"] == "body"]
    body_names = [p["name"] for p in body_params]
    # Should include fields like artistName, foreignArtistId, monitored
    assert "artistName" in body_names
    assert "monitored" in body_names
    # Should NOT include 'id' (skipped for bodies)
    assert "id" not in body_names


def test_readonly_fields_excluded():
    spec = _spec()
    # POST /api/v1/artist — 'ended' is readOnly on ArtistResource
    op = spec["paths"]["/api/v1/artist"]["post"]
    op["_method"] = "post"
    params = parse_parameters(spec, op, "/api/v1/artist")
    names = [p["name"] for p in params]
    assert "ended" not in names


def test_enum_in_description():
    spec = _spec()
    # GET /api/v1/wanted/missing — sortDirection is a $ref to SortDirection enum
    op = spec["paths"]["/api/v1/wanted/missing"]["get"]
    op["_method"] = "get"
    params = parse_parameters(spec, op, "/api/v1/wanted/missing")
    sort_dir = next(p for p in params if p["name"] == "sortDirection")
    assert sort_dir["enum"] is not None
    assert "ascending" in sort_dir["enum"]
    assert "values:" in sort_dir["description"].lower() or "Values:" in sort_dir["description"]


def test_update_defaults_to_none():
    spec = _spec()
    # PUT /api/v1/artist/{id} — update operation should default optional body fields to None
    op = spec["paths"]["/api/v1/artist/{id}"]["put"]
    op["_method"] = "put"
    params = parse_parameters(spec, op, "/api/v1/artist/{id}")
    body_params = [p for p in params if p["location"] == "body"]
    # All body params should have default=None for update ops
    for p in body_params:
        assert p["default"] is None, f"{p['name']} should default to None for update"


def test_no_duplicate_params():
    spec = _spec()
    # Check all operations for duplicate parameter names
    for path, path_item in spec["paths"].items():
        for method in ("get", "post", "put", "delete", "patch"):
            if method not in path_item:
                continue
            op = path_item[method]
            op["_method"] = method
            params = parse_parameters(spec, op, path)
            names = [p["name"] for p in params]
            dupes = [n for n in names if names.count(n) > 1]
            assert not dupes, f"Duplicate params in {method.upper()} {path}: {dupes}"


# ── get_response_type ─────────────────────────────────────────────────


def test_array_response():
    spec = _spec()
    op = spec["paths"]["/api/v1/artist"]["get"]
    assert get_response_type(spec, op) == "array"


def test_paging_response():
    spec = _spec()
    op = spec["paths"]["/api/v1/wanted/missing"]["get"]
    assert get_response_type(spec, op) == "paging"


def test_object_response():
    spec = _spec()
    op = spec["paths"]["/api/v1/artist/{id}"]["get"]
    assert get_response_type(spec, op) == "object"


def test_no_content_response():
    spec = _spec()
    op = spec["paths"]["/api/v1/artist/{id}"]["delete"]
    assert get_response_type(spec, op) in ("none", "object")

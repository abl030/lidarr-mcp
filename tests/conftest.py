"""Shared fixtures for lidarr-mcp tests."""

from __future__ import annotations

import importlib
import os
from types import ModuleType
from typing import Any

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Auto-skip integration tests when LIDARR_API_KEY is not set."""
    if os.environ.get("LIDARR_API_KEY"):
        return
    skip_marker = pytest.mark.skip(reason="LIDARR_API_KEY not set")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)


class _ToolUnwrapper:
    """Proxy that unwraps FastMCP ``FunctionTool`` objects on attribute access.

    ``@mcp.tool()`` replaces the original ``async def`` with a ``FunctionTool``
    instance.  This wrapper transparently returns ``.fn`` (the raw function) so
    tests can call ``await server.lidarr_list_artists()`` naturally.  Non-tool
    attributes (``_client``, ``_normalize_unicode``, constants, etc.) are
    returned as-is.
    """

    def __init__(self, mod: ModuleType) -> None:
        object.__setattr__(self, "_mod", mod)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(object.__getattribute__(self, "_mod"), name)
        # FastMCP FunctionTool has a `.fn` that holds the raw async function.
        if hasattr(attr, "fn") and callable(attr.fn):
            return attr.fn
        return attr

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_mod"), name, value)


@pytest.fixture(scope="session")
def server() -> _ToolUnwrapper:
    """Import the generated server module with env vars configured.

    Sets LIDARR_URL and LIDARR_API_KEY from the environment (or defaults),
    then imports ``generated.server`` so its module-level config picks up the
    values.  Returns a proxy that unwraps FunctionTool objects so tests can
    call ``await server.lidarr_list_artists()`` directly.
    """
    url = os.environ.get("LIDARR_URL", "http://localhost:8686")
    api_key = os.environ.get("LIDARR_API_KEY", "")

    os.environ["LIDARR_URL"] = url
    os.environ["LIDARR_API_KEY"] = api_key

    # Force (re-)import so module-level reads pick up the env vars.
    mod = importlib.import_module("generated.server")
    mod = importlib.reload(mod)
    return _ToolUnwrapper(mod)

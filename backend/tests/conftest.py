"""All tests are offline; API fixtures explicitly enter and exit application lifespan."""
import json
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.main import create_app

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "app" / "fixtures" / "product_515291.json"


@pytest.fixture(autouse=True)
def isolated_environment_and_no_network(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)

    async def forbidden_request(*args, **kwargs):
        pytest.fail("Real network I/O is forbidden in the Phase 1 test suite.")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden_request)


@pytest.fixture
def raw_product() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"), parse_float=Decimal)


@pytest.fixture
async def app_factory() -> AsyncIterator:
    async with AsyncExitStack() as stack:
        async def build(*, mode="mock", handler=None, upstream_client=None, **overrides):
            config = Settings(_env_file=None, ekt_mode=mode, **overrides)
            app = create_app(
                config, upstream_client=upstream_client,
                http_transport=httpx.MockTransport(handler) if handler is not None else None,
            )
            await stack.enter_async_context(app.router.lifespan_context(app))
            api = await stack.enter_async_context(httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test.local",
            ))
            return app, api
        yield build

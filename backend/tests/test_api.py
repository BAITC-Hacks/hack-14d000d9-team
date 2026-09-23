import logging

import httpx
import pytest

from app.clients.ekt_client import MockEKTClient
from app.config import Settings
from app.main import create_app


async def test_health_is_liveness_without_an_upstream_call(app_factory):
    def forbidden(request):
        pytest.fail("Health must not call EKT.")
    _, api = await app_factory(mode="live", handler=forbidden)
    response = await api.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok", "phase": 1, "source_mode": "live", "upstream_status": "not_checked",
        "capabilities": {"product_detail": True},
    }
    assert response.headers["X-EKT-Source"] == "live"


async def test_offline_mock_detail(app_factory):
    _, api = await app_factory()
    response = await api.get("/api/products/515291")
    assert response.status_code == 200
    body = response.json()
    assert body["price"] == "64920"
    assert body["specifications"]["rated_current"] == "250 А"
    assert body["total_quantity"] == 23
    assert "RATED_CURRENT_CONFLICT" in {issue["code"] for issue in body["issues"]}
    assert response.headers["X-EKT-Source"] == "mock"
    assert response.headers["Cache-Control"] == "no-store"
    assert "properties" not in body
    assert "offers" not in body


async def test_detail_is_fresh_and_exactly_one_request_each_time(app_factory, raw_product):
    calls = []

    def handler(request):
        calls.append(request)
        raw_product["price"] = len(calls)
        return httpx.Response(200, json=raw_product)

    _, api = await app_factory(mode="live", handler=handler)
    assert (await api.get("/api/products/515291")).json()["price"] == "1"
    assert (await api.get("/api/products/515291")).json()["price"] == "2"
    assert len(calls) == 2


@pytest.mark.parametrize("product_id", ["0", "-1", "1.5", "515291.0", "true", "abc", "9223372036854775808"])
async def test_invalid_path_ids_have_safe_specific_error(app_factory, product_id):
    _, api = await app_factory()
    response = await api.get(f"/api/products/{product_id}")
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_PRODUCT_ID"
    assert body["error"]["details"] == {}
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert "input" not in body["error"]


@pytest.mark.parametrize("upstream_status,expected_status,code", [
    (404, 404, "PRODUCT_NOT_FOUND"),
    (503, 503, "EKT_API_UNAVAILABLE"),
    (401, 503, "EKT_API_UNAVAILABLE"),
    (200, 502, "INVALID_EKT_RESPONSE"),
])
async def test_upstream_error_envelope_and_no_mock_fallback(app_factory, upstream_status, expected_status, code):
    _, api = await app_factory(mode="live", handler=lambda request: httpx.Response(upstream_status, text="private-upstream-data"))
    response = await api.get("/api/products/515291")
    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == code
    assert "private-upstream-data" not in response.text
    assert response.headers["X-EKT-Source"] == "live"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


async def test_api_connection_failure_is_not_a_missing_product(app_factory):
    def handler(request):
        raise httpx.ConnectError("not-public", request=request)
    _, api = await app_factory(mode="live", handler=handler)
    response = await api.get("/api/products/515291")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "EKT_API_UNAVAILABLE"


async def test_mock_unknown_product_is_404(app_factory):
    _, api = await app_factory()
    response = await api.get("/api/products/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


async def test_json_precision_survives_http_normalization_and_response(app_factory):
    _, api = await app_factory(mode="live", handler=lambda request: httpx.Response(
        200, content=b'{"id":515291,"price":0.12345678901234567890123456789}',
    ))
    body = (await api.get("/api/products/515291")).json()
    assert body["price"] == "0.12345678901234567890123456789"
    assert body["total_quantity"] is None
    assert body["available"] is None


async def test_shared_http_client_is_closed_after_lifespan():
    app = create_app(Settings(_env_file=None, ekt_mode="mock"))
    assert not hasattr(app.state, "http_client")
    async with app.router.lifespan_context(app):
        shared = app.state.http_client
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test.local") as api:
            await api.get("/health")
            await api.get("/api/products/515291")
        assert app.state.http_client is shared
        assert not shared.is_closed
    assert shared.is_closed


async def test_application_instances_do_not_share_clients_or_state(app_factory):
    first, _ = await app_factory()
    second, _ = await app_factory()
    assert first.state.http_client is not second.state.http_client
    assert first.state.services is not second.state.services
    assert first.state.services.client is not second.state.services.client


def test_injected_source_mode_cannot_silently_mix_data():
    with pytest.raises(ValueError, match="source mode"):
        create_app(Settings(_env_file=None, ekt_mode="live"), upstream_client=MockEKTClient())


async def test_only_phase1_routes_are_registered_and_money_schema_is_a_string(app_factory):
    _, api = await app_factory()
    schema = (await api.get("/openapi.json")).json()
    assert set(schema["paths"]) == {"/health", "/api/products/{product_id}"}
    price = schema["components"]["schemas"]["NormalizedProduct"]["properties"]["price"]
    assert {alternative["type"] for alternative in price["anyOf"]} == {"string", "null"}
    assert schema["paths"]["/api/products/{product_id}"]["get"]["responses"]["422"]["content"]["application/json"]["schema"]["$ref"].endswith("ErrorEnvelope")
    assert (await api.post("/api/cart/prepare", json={})).status_code == 404
    assert (await api.get("/api/products/515291/stock")).status_code == 404
    assert (await api.get("/api/products/515291/analogs")).status_code == 404
    assert (await api.post("/api/sessions")).status_code == 404


async def test_cors_is_disabled_by_default(app_factory):
    _, api = await app_factory()
    response = await api.get("/health", headers={"Origin": "https://other.example"})
    assert "access-control-allow-origin" not in response.headers


async def test_internal_error_is_safe_but_diagnostic_is_retained(app_factory, caplog):
    class BrokenDetailClient:
        mode = "mock"

        async def get_product(self, product_id):
            raise RuntimeError("private-secret-value")

    _, api = await app_factory(upstream_client=BrokenDetailClient())
    with caplog.at_level(logging.INFO, logger="ekt_bridge"):
        response = await api.get("/api/products/515291", headers={"Authorization": "private-secret-header"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "private-secret" not in response.text
    assert "private-secret" not in caplog.text
    assert "RuntimeError" in caplog.text
    assert response.headers["X-Request-ID"] in caplog.text


async def test_request_ids_are_generated_not_trusted_from_input(app_factory):
    _, api = await app_factory()
    first = await api.get("/health", headers={"X-Request-ID": "untrusted-id"})
    second = await api.get("/health")
    assert first.headers["X-Request-ID"] != "untrusted-id"
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]

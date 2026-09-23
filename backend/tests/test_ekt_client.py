from decimal import Decimal

import httpx
import pytest

from app.clients.ekt_client import EKTClient, MockEKTClient
from app.config import Settings
from app.exceptions import BridgeError


async def fetch(handler, product_id=515291, **settings_overrides):
    settings = Settings(_env_file=None, ekt_mode="live", **settings_overrides)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        return await EKTClient(http, settings).get_product(product_id)


async def test_detail_success_and_configured_target(raw_product):
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://catalog.example.test/supplied/detail?id=515291"
        assert request.method == "GET"
        assert request.extensions["timeout"]["read"] == 3
        return httpx.Response(200, json=raw_product)

    product = await fetch(
        handler, ekt_base_url="https://catalog.example.test",
        ekt_product_detail_path="/supplied/detail", ekt_timeout_seconds=3,
    )
    assert product["id"] == 515291
    assert len(calls) == 1


async def test_json_decimal_precision_is_preserved():
    raw = await fetch(lambda request: httpx.Response(
        200, content=b'{"id":515291,"price":0.12345678901234567890123456789}',
    ))
    assert raw["price"] == Decimal("0.12345678901234567890123456789")
    assert isinstance(raw["price"], Decimal)


@pytest.mark.parametrize("status,code,http_status", [
    (404, "PRODUCT_NOT_FOUND", 404),
    (401, "EKT_API_UNAVAILABLE", 503),
    (403, "EKT_API_UNAVAILABLE", 503),
    (408, "EKT_API_UNAVAILABLE", 503),
    (429, "EKT_API_UNAVAILABLE", 503),
    (500, "EKT_API_UNAVAILABLE", 503),
    (503, "EKT_API_UNAVAILABLE", 503),
    (400, "INVALID_EKT_RESPONSE", 502),
    (302, "INVALID_EKT_RESPONSE", 502),
])
async def test_http_status_mapping_does_not_expose_body(status, code, http_status):
    with pytest.raises(BridgeError) as caught:
        await fetch(lambda request: httpx.Response(status, text="secret-upstream-body"))
    assert caught.value.code == code
    assert caught.value.status == http_status
    assert "secret-upstream-body" not in str(caught.value.details)
    assert "secret-upstream-body" not in caught.value.message


@pytest.mark.parametrize("exception", [httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError])
async def test_transport_failure_becomes_unavailable(exception):
    def handler(request):
        raise exception("secret-internal-error", request=request)
    with pytest.raises(BridgeError) as caught:
        await fetch(handler)
    assert caught.value.code == "EKT_API_UNAVAILABLE"
    assert caught.value.status == 503
    assert "secret-internal-error" not in caught.value.message


@pytest.mark.parametrize("body", [
    b"not json", b"<html>upstream gateway</html>", b"", b"\xff\xff",
    b'{"id":515291,"price":NaN}', b'{"id":515291,"price":Infinity}',
])
async def test_invalid_json_is_rejected(body):
    with pytest.raises(BridgeError) as caught:
        await fetch(lambda request: httpx.Response(200, content=body))
    assert caught.value.code == "INVALID_EKT_RESPONSE"
    assert caught.value.status == 502


@pytest.mark.parametrize("body", [
    None, [], "text", {}, {"data": {"id": 515291}}, {"id": 99},
    {"id": True}, {"id": "515291"}, {"id": -1}, {"id": 515291.0},
])
async def test_invalid_envelope_or_identity_is_rejected(body):
    with pytest.raises(BridgeError) as caught:
        await fetch(lambda request: httpx.Response(200, json=body))
    assert caught.value.code == "INVALID_EKT_RESPONSE"


@pytest.mark.parametrize("product_id", [0, -1, True, 1.5, "515291"])
async def test_client_rejects_invalid_requested_id_without_io(product_id):
    def unexpected(request):
        pytest.fail("Invalid IDs must not reach HTTP.")
    with pytest.raises(BridgeError) as caught:
        await fetch(unexpected, product_id=product_id)
    assert caught.value.code == "INVALID_PRODUCT_ID"


async def test_catalog_urls_are_not_followed(raw_product):
    calls = []
    raw_product.update({
        "url_api_detail": "https://attacker.invalid/detail?id=9",
        "image": "http://127.0.0.1/private",
        "url": "https://attacker.invalid/catalog",
    })

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, json=raw_product)

    await fetch(handler)
    assert calls == ["https://ekt.kz/api/products/detail?id=515291"]


async def test_redirects_are_not_followed_even_when_shared_client_enables_them():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "https://attacker.invalid/"})

    settings = Settings(_env_file=None, ekt_mode="live")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as http:
        with pytest.raises(BridgeError):
            await EKTClient(http, settings).get_product(515291)
    assert len(calls) == 1


async def test_oversized_response_is_rejected():
    with pytest.raises(BridgeError) as caught:
        await fetch(lambda request: httpx.Response(200, content=b"x" * 1025), max_upstream_response_bytes=1024)
    assert caught.value.code == "INVALID_EKT_RESPONSE"


async def test_explicit_mock_source_returns_independent_copies():
    client = MockEKTClient()
    first = await client.get_product(515291)
    first["properties"]["TORGOVAYA_MARKA"] = "mutated"
    second = await client.get_product(515291)
    assert client.mode == "mock"
    assert second["properties"]["TORGOVAYA_MARKA"] == "Legrand"
    with pytest.raises(BridgeError) as caught:
        await client.get_product(999999)
    assert caught.value.code == "PRODUCT_NOT_FOUND"

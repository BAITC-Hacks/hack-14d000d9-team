"""Detail-only catalog clients. Live errors never trigger a mock fallback."""
import asyncio
import copy
import json
import logging
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Literal, Protocol

import httpx

from app.config import Settings
from app.exceptions import BridgeError
from app.services.normalization import valid_id

SourceMode = Literal["mock", "live"]
logger = logging.getLogger("ekt_bridge.upstream")


class ProductDetailClient(Protocol):
    @property
    def mode(self) -> SourceMode:
        """Declared source; injected test clients must match application configuration."""

    async def get_product(self, product_id: int) -> dict[str, object]:
        """Read one raw detail record. Routes must normalize it before returning it."""


def reject_constant(value: str) -> None:
    raise ValueError("Nonfinite JSON numeric constant.")


def validate_detail(raw: object, product_id: int) -> dict[str, object]:
    if not isinstance(raw, dict) or not valid_id(raw.get("id")) or raw["id"] != product_id:
        raise BridgeError("INVALID_EKT_RESPONSE", "The upstream detail has an invalid or mismatched identity.", 502)
    return raw


class EKTClient:
    mode: SourceMode = "live"

    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self.http = http
        self.settings = settings

    async def get_product(self, product_id: int) -> dict[str, object]:
        if not valid_id(product_id):
            raise BridgeError("INVALID_PRODUCT_ID", "Product ID must be a positive integer.", 422)
        # Never use url_api_detail, image, or product URLs from a catalog record.
        url = httpx.URL(self.settings.ekt_base_url + self.settings.ekt_product_detail_path)
        started = perf_counter()
        status: int | None = None
        try:
            async with asyncio.timeout(self.settings.ekt_timeout_seconds):
                async with self.http.stream(
                    "GET", url, params={"id": product_id},
                    timeout=self.settings.ekt_timeout_seconds, follow_redirects=False,
                ) as response:
                    status = response.status_code
                    if status == 404:
                        raise BridgeError("PRODUCT_NOT_FOUND", "The requested product was not found.", 404)
                    if not 200 <= status < 300:
                        if status >= 500 or status in {401, 403, 408, 429}:
                            raise BridgeError(
                                "EKT_API_UNAVAILABLE", "The upstream catalog is unavailable.", 503,
                                {"upstream_status": status},
                            )
                        raise BridgeError(
                            "INVALID_EKT_RESPONSE", "The upstream returned an unexpected HTTP status.", 502,
                            {"upstream_status": status},
                        )
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > self.settings.max_upstream_response_bytes:
                            raise BridgeError("INVALID_EKT_RESPONSE", "The upstream response exceeds the size limit.", 502)
                        body.extend(chunk)
            try:
                raw = json.loads(body, parse_float=Decimal, parse_constant=reject_constant)
            except (ValueError, UnicodeDecodeError, RecursionError):
                raise BridgeError("INVALID_EKT_RESPONSE", "The upstream did not return usable JSON.", 502) from None
            return validate_detail(raw, product_id)
        except (httpx.HTTPError, TimeoutError):
            raise BridgeError("EKT_API_UNAVAILABLE", "The upstream catalog request failed or timed out.", 503) from None
        finally:
            logger.info(
                "operation=product_detail upstream_status=%s duration_ms=%.2f",
                status, (perf_counter() - started) * 1000,
            )


class MockEKTClient:
    """Explicit offline source containing only the supplied example, not live stock."""
    mode: SourceMode = "mock"

    def __init__(self) -> None:
        path = Path(__file__).resolve().parents[1] / "fixtures" / "product_515291.json"
        raw = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal, parse_constant=reject_constant)
        self._product = validate_detail(raw, 515291)

    async def get_product(self, product_id: int) -> dict[str, object]:
        if not valid_id(product_id):
            raise BridgeError("INVALID_PRODUCT_ID", "Product ID must be a positive integer.", 422)
        if product_id != self._product["id"]:
            raise BridgeError("PRODUCT_NOT_FOUND", "The requested product is not present in the mock fixture.", 404)
        return copy.deepcopy(self._product)

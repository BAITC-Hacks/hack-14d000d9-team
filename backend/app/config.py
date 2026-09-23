"""Operator configuration for Phase 1 only; no cart or search settings."""
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True,
    )

    ekt_mode: Literal["mock", "live"] = "mock"
    ekt_base_url: str = "https://ekt.kz"
    ekt_product_detail_path: str = "/api/products/detail"
    ekt_timeout_seconds: float = Field(default=10, gt=0, le=60, allow_inf_nan=False)
    max_upstream_response_bytes: int = Field(default=2_097_152, ge=1024, le=10_485_760)

    @field_validator("ekt_base_url")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"https", "http"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or parts.path not in {"", "/"}
            or parts.query or parts.fragment
            or "\\" in value or "?" in value or "#" in value
            or any(character.isspace() or ord(character) < 32 for character in value)
        ):
            raise ValueError("Use an HTTP(S) origin without credentials, path, query, or fragment.")
        _ = parts.port  # Also rejects invalid and out-of-range port numbers.
        if parts.scheme == "http" and parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Non-local upstream origins must use HTTPS.")
        return value.rstrip("/")

    @field_validator("ekt_product_detail_path")
    @classmethod
    def validate_detail_path(cls, value: str) -> str:
        if (
            not re.fullmatch(r"/[A-Za-z0-9_./-]+", value)
            or value.startswith("//")
            or any(part in {".", "..", ""} for part in value[1:].split("/"))
        ):
            raise ValueError("Use a same-origin absolute path without escapes, query, or dot segments.")
        return value

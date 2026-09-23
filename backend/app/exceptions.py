"""Public errors contain safe metadata, never upstream bodies or exception messages."""
from typing import Any

from pydantic import BaseModel, Field


class BridgeError(Exception):
    def __init__(
        self, code: str, message: str, status: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


class ErrorContent(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorContent
    request_id: str

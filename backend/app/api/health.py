from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import ServiceDependency

router = APIRouter(tags=["Health"])


class Capabilities(BaseModel):
    product_detail: bool = True


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    phase: Literal[1] = 1
    source_mode: Literal["mock", "live"]
    upstream_status: Literal["not_checked"] = "not_checked"
    capabilities: Capabilities


@router.get("/health", response_model=HealthResponse, summary="Process liveness; no upstream request")
async def health(services: ServiceDependency) -> HealthResponse:
    return HealthResponse(source_mode=services.client.mode, capabilities=Capabilities())

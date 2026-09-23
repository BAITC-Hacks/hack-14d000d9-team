from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from app.clients.ekt_client import ProductDetailClient
from app.config import Settings
from app.services.product_service import ProductService


@dataclass(frozen=True)
class Services:
    settings: Settings
    client: ProductDetailClient
    products: ProductService


def get_services(request: Request) -> Services:
    return request.app.state.services


ServiceDependency = Annotated[Services, Depends(get_services)]

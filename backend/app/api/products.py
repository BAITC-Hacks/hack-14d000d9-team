import re
from typing import Annotated

from fastapi import APIRouter, Path
from pydantic import BeforeValidator

from app.dependencies import ServiceDependency
from app.schemas.product import MAX_ID, NormalizedProduct

router = APIRouter(prefix="/api/products", tags=["Product details"])


def parse_product_id(value: object) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,19}", value):
        raise ValueError("Product ID must contain positive integer digits only.")
    return int(value)


ProductID = Annotated[int, BeforeValidator(parse_product_id), Path(gt=0, le=MAX_ID)]


@router.get(
    "/{product_id}", response_model=NormalizedProduct,
    summary="Read normalized product details",
    description="Fresh detail evidence. Money is a decimal string; missing price and stock remain null.",
)
async def get_product(product_id: ProductID, services: ServiceDependency) -> NormalizedProduct:
    return await services.products.get_product(product_id)

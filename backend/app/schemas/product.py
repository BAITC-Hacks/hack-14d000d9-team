"""Explicit response contract. Money is a JSON string, not a binary-float number."""
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer, WithJsonSchema, computed_field

MAX_ID = 9_223_372_036_854_775_807
MAX_QUANTITY = 1_000_000_000
PositiveID = Annotated[int, Field(strict=True, gt=0, le=MAX_ID)]
WholeQuantity = Annotated[int, Field(strict=True, ge=0, le=MAX_QUANTITY)]
Money = Annotated[
    Decimal,
    Field(ge=0, allow_inf_nan=False),
    PlainSerializer(lambda value: format(value, "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {"type": "string", "description": "Exact nonnegative decimal money; currency is unknown.",
         "examples": ["64920", "0.10"]},
        mode="serialization",
    ),
]


class DataIssue(BaseModel):
    code: str
    field: str
    message: str
    observed_values: list[str | int | bool | None] | None = None


class StoreStock(BaseModel):
    id: PositiveID
    name: str | None = None
    quantity: WholeQuantity | None = None


class ProductSpecifications(BaseModel):
    brand: str | None = None
    product_type: str | None = None
    poles: Annotated[int, Field(strict=True, gt=0, le=MAX_QUANTITY)] | None = None
    rated_current: str | None = None
    rated_voltage: str | None = None
    breaking_capacity: str | None = None
    installation_type: str | None = None


class NormalizedProduct(BaseModel):
    id: PositiveID
    article: str | None = None
    supplier_article: str | None = None
    name: str | None = None
    description: str | None = None
    price: Money | None = None
    total_quantity: WholeQuantity | None = Field(
        default=None, description="Reported product.quantity only; never a warehouse sum.",
    )
    available: bool | None = Field(
        default=None, description="Derived only from usable product.quantity; null means unknown.",
    )
    stores: list[StoreStock] = Field(default_factory=list)
    specifications: ProductSpecifications = Field(default_factory=ProductSpecifications)
    image_url: str | None = None
    product_url: str | None = None
    issues: list[DataIssue] = Field(default_factory=list)

    @computed_field
    @property
    def warnings(self) -> list[str]:
        """Readable compatibility view derived from exactly the same issues."""
        return [issue.message for issue in self.issues]

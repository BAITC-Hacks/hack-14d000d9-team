"""Fetch once and normalize. No cache, search pool, or extra detail requests."""
from app.clients.ekt_client import ProductDetailClient
from app.schemas.product import NormalizedProduct
from app.services.normalization import normalize_product


class ProductService:
    def __init__(self, client: ProductDetailClient) -> None:
        self.client = client

    async def get_product(self, product_id: int) -> NormalizedProduct:
        raw = await self.client.get_product(product_id)
        return normalize_product(raw, expected_id=product_id)

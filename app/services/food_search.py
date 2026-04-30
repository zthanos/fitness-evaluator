"""Open Food Facts product search — free, no API key required."""
from __future__ import annotations

import logging
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product"

# Fields we need (keeps payload small)
_FIELDS = "product_name,brands,serving_size,nutriments,image_small_url,url,code"

TIMEOUT_SECONDS = 8.0
MAX_RESULTS = 10


class FoodProduct(BaseModel):
    barcode: Optional[str] = None
    name: str
    brand: Optional[str] = None
    serving_size: Optional[str] = None
    calories_per_100g: Optional[float] = None
    protein_per_100g: Optional[float] = None
    carbs_per_100g: Optional[float] = None
    fat_per_100g: Optional[float] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    source: str = "product_search"


class FoodSearchService:

    def search(self, query: str, max_results: int = MAX_RESULTS) -> list[FoodProduct]:
        """Search Open Food Facts by free text. Returns up to max_results products."""
        params = {
            "search_terms": query,
            "json": "1",
            "page_size": min(max_results, 20),
            "fields": _FIELDS,
            "sort_by": "unique_scans_n",
        }
        try:
            resp = httpx.get(OFF_SEARCH_URL, params=params, timeout=TIMEOUT_SECONDS)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Open Food Facts search failed: %s", exc)
            return []

        products = []
        for raw in data.get("products", []):
            product = self._parse_product(raw)
            if product:
                products.append(product)
        return products[:max_results]

    def _parse_product(self, raw: dict) -> Optional[FoodProduct]:
        name = raw.get("product_name", "").strip()
        if not name:
            return None

        n = raw.get("nutriments", {})
        return FoodProduct(
            barcode=raw.get("code"),
            name=name,
            brand=raw.get("brands", "").strip() or None,
            serving_size=raw.get("serving_size"),
            calories_per_100g=self._float(n.get("energy-kcal_100g") or n.get("energy_100g")),
            protein_per_100g=self._float(n.get("proteins_100g")),
            carbs_per_100g=self._float(n.get("carbohydrates_100g")),
            fat_per_100g=self._float(n.get("fat_100g")),
            image_url=raw.get("image_small_url"),
            source_url=raw.get("url"),
        )

    @staticmethod
    def _float(val) -> Optional[float]:
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

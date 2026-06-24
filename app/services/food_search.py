"""Open Food Facts product search — free, no API key required."""
from __future__ import annotations

import logging
import re
import unicodedata
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

_GREEK_FOOD_TERMS = {
    "βρωμη": "oats",
    "νιφαδες βρωμης": "rolled oats",
    "γιαουρτι": "yogurt",
    "γιαουρτι στραγγιστο": "greek yogurt",
    "στραγγιστο γιαουρτι": "greek yogurt",
    "γαλα": "milk",
    "μπανανα": "banana",
    "φραουλες": "strawberries",
    "φραουλα": "strawberry",
    "μηλο": "apple",
    "μελι": "honey",
    "κανελα": "cinnamon",
    "κακαο": "cocoa",
    "φυστικοβουτυρο": "peanut butter",
    "φυστικο βουτυρο": "peanut butter",
    "ταχινι": "tahini",
    "αμυγδαλα": "almonds",
    "καρυδια": "walnuts",
    "σποροι chia": "chia seeds",
    "σποροι τσια": "chia seeds",
    "κοτοπουλο": "chicken",
    "γαλοπουλα": "turkey",
    "αυγο": "egg",
    "αυγα": "eggs",
    "ρυζι": "rice",
    "πατατα": "potato",
    "πατατες": "potatoes",
    "ψωμι": "bread",
    "τονος": "tuna",
    "σολομος": "salmon",
    "φακες": "lentils",
    "ρεβυθια": "chickpeas",
    "φασολια": "beans",
    "τυρι": "cheese",
    "φετα": "feta",
    "ελαιολαδο": "olive oil",
    "αβοκαντο": "avocado",
}


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
        products_by_key: dict[str, FoodProduct] = {}
        for candidate in self._query_candidates(query):
            for product in self._search_once(candidate, max_results=max_results):
                key = product.barcode or f"{product.name}|{product.brand or ''}"
                if key not in products_by_key:
                    products_by_key[key] = product
                if len(products_by_key) >= max_results:
                    return list(products_by_key.values())[:max_results]
        return list(products_by_key.values())[:max_results]

    def _search_once(self, query: str, max_results: int = MAX_RESULTS) -> list[FoodProduct]:
        """Run one Open Food Facts free-text search."""
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

    def _query_candidates(self, query: str) -> list[str]:
        """Return search variants, translating common Greek food terms to English."""
        cleaned = " ".join(query.strip().split())
        if not cleaned:
            return []

        candidates = [cleaned]
        normalized = self._normalize_text(cleaned)
        translated = normalized

        normalized_terms = [
            (self._normalize_text(greek), english)
            for greek, english in _GREEK_FOOD_TERMS.items()
        ]
        for greek, english in sorted(normalized_terms, key=lambda kv: len(kv[0]), reverse=True):
            translated = re.sub(rf"\b{re.escape(greek)}\b", english, translated)

        translated = " ".join(translated.split())
        if translated and translated != normalized:
            candidates.append(translated)

        # If the user typed several ingredients in Greek and only some matched,
        # the English terms alone often work better against Open Food Facts.
        matched_terms = [
            english for greek, english in normalized_terms
            if re.search(rf"\b{re.escape(greek)}\b", normalized)
        ]
        if matched_terms:
            english_only = " ".join(dict.fromkeys(matched_terms))
            if english_only not in candidates:
                candidates.append(english_only)

        return list(dict.fromkeys(candidates))

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.lower()
        text = "".join(
            ch for ch in unicodedata.normalize("NFD", text)
            if unicodedata.category(ch) != "Mn"
        )
        text = text.replace("ς", "σ")
        return re.sub(r"[^\w\s]", " ", text)

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

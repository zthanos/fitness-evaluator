"""Open Food Facts product search — free, no API key required."""
from __future__ import annotations

import asyncio
import json
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

# LLM query reformulation — translates/normalizes (often Greek) free text into
# English Open Food Facts search terms. The LLM never produces nutrition values;
# Open Food Facts remains the single source of macros.
LLM_TIMEOUT_SECONDS = 10.0
_REFORMULATE_SYSTEM = (
    "You normalize food search queries for the Open Food Facts product database. "
    "The query may be in Greek or English and may contain typos, dish names, "
    "brand names, or several ingredients. Return the best search terms "
    "(English or Latin-script) to find these foods in a product database.\n"
    "Rules:\n"
    "- TRANSLATE food words to English — do NOT phonetically transliterate them "
    "(e.g. Σνίτσελ Κοτόπουλου Πανέ -> breaded chicken schnitzel, γιαούρτι -> yogurt, "
    "πατάτες -> potatoes).\n"
    "- Transliterate to Latin ONLY brand names, keeping their official spelling "
    "(e.g. ΦΑΓΕ->FAGE, Γιώτης->Jotis, Μέλισσα->Melissa, Παυλίδης->Pavlidis, "
    "Μεβγάλ->Mevgal, ΔΕΛΤΑ->Delta). When the query has a brand, put the "
    "brand+translated-product term first, then a generic brand-free fallback.\n"
    "- For a prepared dish, return its main ingredients/components.\n"
    "- Keep each term short (1-4 words); most specific first, generic last.\n"
    'Respond ONLY with JSON: {"terms": ["term1", "term2", ...]} — up to 5 terms. '
    "No commentary."
)

# Macro estimation — used only as a fallback when Open Food Facts has no match.
# Produces an explicitly low-confidence estimate, flagged in the UI.
_ESTIMATE_SYSTEM = (
    "You estimate the nutrition of a described food using common, standard values. "
    "The description may be in Greek or English. "
    'Respond ONLY with JSON: {"calories": <kcal number>, "protein_g": <g>, '
    '"carbs_g": <g>, "fat_g": <g>, "basis": "per_100g" | "per_portion"}. '
    "If the description includes an explicit quantity or unit (e.g. '1 scoop', "
    "'2 slices', '30 g', '200 ml'), estimate the totals for THAT exact amount and "
    'set basis="per_portion". Otherwise prefer per_100g for generic foods. '
    "Numbers only — no ranges, no commentary."
)

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

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: Optional async LLM client exposing ``chat_completion``.
                When omitted, one is created lazily on first reformulation.
                Used only to translate/normalize the query — never to produce
                nutrition values.
        """
        self._llm_client = llm_client

    def _get_client(self):
        """Lazily build the LLM client for food-search calls.

        Uses the dedicated FOOD_SEARCH_* settings (which fall back to the
        tool-agent model, then the primary LLM) so these lightweight JSON calls
        can target a small, fast instruct model instead of a slow reasoner.
        Returns None if a client cannot be created.
        """
        if self._llm_client is not None:
            return self._llm_client
        try:
            from app.services.llm_client import LLMClient
            from app.config import get_settings
            settings = get_settings()
            logger.info(
                "Food search LLM: model=%s endpoint=%s",
                settings.food_search_model,
                settings.food_search_base_url,
            )
            self._llm_client = LLMClient(
                base_url=settings.food_search_base_url,
                model_name=settings.food_search_model,
            )
            return self._llm_client
        except Exception as exc:
            logger.warning("Food search: could not init LLM client: %s", exc)
            return None

    async def search_with_llm(
        self, query: str, max_results: int = MAX_RESULTS
    ) -> list[FoodProduct]:
        """LLM-reformulated search: translate/normalize the query, then query OFF.

        The LLM only widens the search terms; macros still come from Open Food
        Facts. Falls back to the deterministic path if the LLM is unavailable.
        """
        llm_terms = await self.reformulate_query(query)
        return self.search(query, max_results=max_results, extra_candidates=llm_terms)

    def search(
        self,
        query: str,
        max_results: int = MAX_RESULTS,
        extra_candidates: Optional[list[str]] = None,
    ) -> list[FoodProduct]:
        """Search Open Food Facts by free text. Returns up to max_results products.

        ``extra_candidates`` (e.g. LLM-translated terms) are tried first, then the
        deterministic dictionary-based candidates, deduplicated.
        """
        products_by_key: dict[str, FoodProduct] = {}

        candidates: list[str] = []
        for cand in (extra_candidates or []):
            cleaned = " ".join((cand or "").split())
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)
        for cand in self._query_candidates(query):
            if cand and cand not in candidates:
                candidates.append(cand)

        for candidate in candidates:
            for product in self._search_once(candidate, max_results=max_results):
                key = product.barcode or f"{product.name}|{product.brand or ''}"
                if key not in products_by_key:
                    products_by_key[key] = product
                if len(products_by_key) >= max_results:
                    return list(products_by_key.values())[:max_results]
        return list(products_by_key.values())[:max_results]

    async def reformulate_query(self, query: str) -> list[str]:
        """Use the LLM to translate/normalize the query into English search terms.

        Returns an empty list on any failure or timeout, so the caller can fall
        back to the deterministic candidates. Never raises.
        """
        cleaned = " ".join((query or "").split())
        if not cleaned:
            return []

        client = self._get_client()
        if client is None:
            return []

        try:
            resp = await asyncio.wait_for(
                client.chat_completion(
                    messages=[
                        {"role": "system", "content": _REFORMULATE_SYSTEM},
                        {"role": "user", "content": cleaned},
                    ],
                    max_tokens=120,
                    temperature=0.0,
                    source="food_search_reformulate",
                ),
                timeout=LLM_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            logger.warning("Food search: LLM reformulation failed: %s", exc)
            return []

        content = (resp or {}).get("content") or ""
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        content = (
            content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        )
        try:
            data = json.loads(content)
            raw_terms = data.get("terms", []) if isinstance(data, dict) else []
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Food search: could not parse LLM terms from %r", content[:200])
            return []

        terms: list[str] = []
        for term in raw_terms:
            if isinstance(term, str):
                norm = " ".join(term.split())
                if norm and norm.lower() not in {t.lower() for t in terms}:
                    terms.append(norm)
        return terms[:5]

    async def estimate_macros(self, name: str) -> Optional[dict]:
        """LLM fallback: estimate macros for a free-text food description.

        Returns ``{"calories", "protein_g", "carbs_g", "fat_g", "basis"}`` where
        ``basis`` is ``"per_100g"`` or ``"per_portion"``, or ``None`` on any
        failure/timeout. Never raises. Used only when Open Food Facts has no match;
        the caller must flag the result as a low-confidence estimate.
        """
        cleaned = " ".join((name or "").split())
        if not cleaned:
            return None

        client = self._get_client()
        if client is None:
            return None

        try:
            resp = await asyncio.wait_for(
                client.chat_completion(
                    messages=[
                        {"role": "system", "content": _ESTIMATE_SYSTEM},
                        {"role": "user", "content": cleaned},
                    ],
                    max_tokens=120,
                    temperature=0.0,
                    source="food_macro_estimate",
                ),
                timeout=LLM_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            logger.warning("Food search: LLM macro estimate failed: %s", exc)
            return None

        content = (resp or {}).get("content") or ""
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        content = (
            content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        )
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Food search: could not parse macro estimate from %r", content[:200])
            return None
        if not isinstance(data, dict):
            return None

        def _num(val) -> Optional[float]:
            try:
                return max(0.0, float(val))
            except (TypeError, ValueError):
                return None

        calories = _num(data.get("calories"))
        if calories is None:
            return None
        basis = data.get("basis")
        if basis not in ("per_100g", "per_portion"):
            basis = "per_100g"
        return {
            "calories": calories,
            "protein_g": _num(data.get("protein_g")) or 0.0,
            "carbs_g": _num(data.get("carbs_g")) or 0.0,
            "fat_g": _num(data.get("fat_g")) or 0.0,
            "basis": basis,
        }

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

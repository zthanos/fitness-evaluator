# Nutrition: smarter food search + macro auto-fill, cooking-oil helper, model routing

## Summary

Makes meal logging far more usable when items are entered as plain descriptions
(often in Greek) instead of precise barcodes. Adds an LLM-assisted food search,
one-tap macro resolution for description-only items, a context-aware cooking-oil
helper, and a dedicated (fast) model for these lightweight LLM calls. Also fixes
two correctness bugs found during testing.

Open Food Facts (OFF) remains the single source of structured macros; the LLM is
used only to **translate/normalize the query** and, as a clearly-flagged
fallback, to **estimate** macros when OFF has no match. Estimates are never
silently trusted — they are marked low-confidence and `needs_confirmation`.

## What's included

### Smarter food search (Greek → OFF)
- `FoodSearchService.reformulate_query()` uses the LLM to translate/normalize a
  (often Greek, possibly messy) query into English OFF search terms, replacing
  the brittle hardcoded Greek→English dictionary as the primary path.
- Brand support: brand names are kept and transliterated to their Latin/official
  spelling (ΦΑΓΕ→FAGE, Γιώτης→Jotis, …), with a generic brand-free fallback term.
- `GET /api/nutrition/search` now goes through `search_with_llm`.

### Macro auto-fill for description-only items
- `POST /api/nutrition/meals/{meal_id}/resolve-macros` — meal-level "fill missing":
  for every item without calories, look up macros from OFF (scaled by quantity);
  if no match, fall back to an LLM estimate. Items that already have calories are
  left untouched. Returns `{resolved, estimated, unresolved}`.
- `POST /api/nutrition/meals/{meal_id}/items/{item_id}/resolve-macros` — per-item
  **retry** that re-runs OFF + estimate for a single item (overwrites).
- `FoodSearchService.estimate_macros()` — LLM fallback returning structured
  `{calories, protein_g, carbs_g, fat_g, basis}`; never raises, times out safely.
- Frontend: "🔍 Θερμίδες (N)" button on meals with description-only items,
  per-item ↻ retry, spinners, and source/confidence badges (`product_search`,
  `ai`, `unconfirmed`, low-confidence %).

### Cooking-oil helper (frontend-only)
- A "🍳 +λάδι" chip appears **only** on oil-absorbing items (πανέ/σνίτσελ/
  nuggets/τηγανητά, accent-insensitive) and only if the meal has no oil item yet.
  One tap adds an editable "Ελαιόλαδο (τηγάνισμα)" item with correct macros
  (15/12/10 g defaults by category). Keeps the common case clean.

### Configurable food-search model
- New `FOOD_SEARCH_MODEL` / `FOOD_SEARCH_ENDPOINT` settings (with
  `food_search_model` / `food_search_base_url` properties). These lightweight
  JSON calls fall back to the tool-agent model, then the primary LLM — so they
  target a small, fast instruct model instead of a slow reasoning model.

### Bug fixes
- **LM Studio 400**: removed `response_format: {"type": "json_object"}` from the
  food-search calls (rejected by LM Studio for these models); rely on the prompt
  + robust JSON parsing (strips ` ```json ` fences and `<think>` blocks).
- **Unit-aware scaling**: OFF per-100 g/ml values are now applied only for
  weight/volume units. Portion units (scoop, piece, slice, …) go to a per-portion
  LLM estimate of the exact amount — fixing the bug where "1 scoop" of whey
  inherited the full per-100 g values (e.g. ~87 g protein instead of ~26 g).

### Also in this branch
- Delete chat session UI (`public/js/coach-chat.js`): hover-reveal trash button
  per conversation + confirm, with current-session handling. (Backend delete
  endpoint already existed.)
- Planning docs under `docs/`: chat-context improvement plan, cooking-oil spec,
  resolve-macros spec.

## How to test
1. Start the backend (`uv run uvicorn app.main:app --reload`) and ensure a fast
   instruct model (e.g. `meta-llama-3.1-8b-instruct`) is loaded in LM Studio.
2. Add a meal with plain descriptions (e.g. "χωριάτικη σαλάτα", "Σνίτσελ Πανέ").
3. Click "🔍 Θερμίδες (N)" → items fill from OFF or a flagged estimate.
4. On a breaded/fried item, use the "🍳 +λάδι" chip; on an unconfirmed item, use
   ↻ to retry or ✓ to confirm.
5. Log a powder as "1 scoop" → verify it estimates a single-scoop portion, not
   per-100 g.

## Notes for reviewers
- **No DB migration** — reuses existing `MealItem` fields. LLM estimates are
  stored as `source="ai"`, `confidence=0.4`, `needs_confirmation=True`; OFF
  matches as `source="product_search"`. (Values constrained to the existing
  `source` CHECK constraint.)
- New env vars are optional (sane fallbacks); settings are `@lru_cache`d, so a
  backend restart is needed to pick up `.env` changes.
- The chat-context engineering refactor is intentionally **out of scope** here
  and will land in a separate branch/PR.
- This branch may also contain unrelated line-ending (CRLF/LF) churn in
  `.kiro/specs/**` and `.env*`; consider reviewing with whitespace changes hidden.

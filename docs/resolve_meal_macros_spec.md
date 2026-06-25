# Spec: «Συμπλήρωσε θερμίδες» για description-only meal items

> Κατάσταση: spec — έτοιμο για υλοποίηση. Καμία αλλαγή κώδικα ακόμη.
> Στόχος: items που μπήκαν σαν σκέτη περιγραφή (όνομα χωρίς μακρο) να αποκτούν
> θερμίδες/μακρο αυτόματα, ώστε να βγαίνει σωστό σύνολο στο Meal.

## 1. Αρχές (locked decisions)

- **Meal-level «fill missing».** Ένα κουμπί στο meal λύνει **όλα** τα description-only items μαζί (όχι ανά item).
- **Πηγή μακρο = OFF** (δομημένα, μέσω του LLM-reformulated search που ήδη φτιάξαμε).
- **Fallback = LLM estimate, σημασμένο.** Αν το OFF δεν βρει τίποτα, το LLM δίνει πρόχειρη εκτίμηση μακρο με **χαμηλό confidence** και ορατό «~est» badge.
- **Editable & διαφανές.** Κάθε item που λύθηκε δείχνει την πηγή (OFF / ~est) και παραμένει editable· τίποτα δεν «κλειδώνει».

## 2. Τι θεωρείται «description-only»

Ένα `MealItem` με όνομα αλλά `calories is None` (ή και τα 4 μακρο `None`).
Το κουμπί εμφανίζεται μόνο όταν το meal έχει ≥1 τέτοιο item, με μετρητή: **«🔍 Συμπλήρωσε θερμίδες (N)»**.

## 3. Backend

### 3.1 Νέο endpoint

```
POST /api/nutrition/meals/{meal_id}/resolve-macros
Auth: get_current_athlete  (έλεγχος ownership του meal)
Body: none  (προαιρετικά: { "item_ids": [..] } για υποσύνολο)
```

Λογική (async):

```
meal = get meal (404 αν δεν ανήκει στον athlete)
resolved, estimated, unresolved = [], [], []
service = FoodSearchService()           # έχει ήδη LLM client lazy-init

for item in meal.items where calories is None:
    products = await service.search_with_llm(item.name, max_results=1)
    if products:
        p = products[0]
        scale = (item.quantity or 100) / 100 if item.unit in ("g", "ml") else 1.0
        item.calories  = round(p.calories_per_100g * scale)  if p.calories_per_100g else None
        item.protein_g = round(p.protein_per_100g * scale, 1) if p.protein_per_100g else None
        item.carbs_g   = round(p.carbs_per_100g   * scale, 1) if p.carbs_per_100g   else None
        item.fat_g     = round(p.fat_per_100g     * scale, 1) if p.fat_per_100g     else None
        item.source = "product_search"; item.confidence = 0.8
        item.source_ref = p.source_url
        resolved.append({item_id, matched: p.name})
    else:
        est = await service.estimate_macros(item.name)   # LLM, βλ. 3.2
        if est:
            scale = (item.quantity or 100)/100 if est.basis == "per_100g" and item.unit in ("g","ml") else 1.0
            item.calories  = round(est.calories  * scale)
            item.protein_g = round(est.protein_g * scale, 1)
            item.carbs_g   = round(est.carbs_g   * scale, 1)
            item.fat_g     = round(est.fat_g     * scale, 1)
            item.source = "llm_estimate"; item.confidence = 0.4
            estimated.append({item_id})
        else:
            unresolved.append(item_id)

db.commit()
return { "resolved": resolved, "estimated": estimated, "unresolved": unresolved }
```

> Σημείωση μονάδων: για `unit` εκτός g/ml (π.χ. τεμάχια) το per-100g scaling δεν ισχύει —
> προτιμάμε LLM estimate με `basis: "per_portion"`, ή το αφήνουμε unresolved για χειροκίνητα γραμμάρια.

### 3.2 `FoodSearchService.estimate_macros(name)` (νέα LLM μέθοδος)

Επιστρέφει δομημένη εκτίμηση ή `None` (timeout/σφάλμα → `None`, ποτέ raise). Ίδιο pattern με το `reformulate_query` (json_object, `LLM_TIMEOUT_SECONDS`).

System prompt (περίληψη):
```
"Estimate typical nutrition for the described food. Use common/standard values.
 Respond ONLY JSON: {"calories": n, "protein_g": n, "carbs_g": n, "fat_g": n,
 "basis": "per_100g" | "per_portion"}. Prefer per_100g for generic foods."
```

Επιστρεφόμενο: μικρό dataclass/dict `{calories, protein_g, carbs_g, fat_g, basis}`.

## 4. Frontend (`public/js/nutrition.js`)

- Στο render του meal: αν `meal.items` έχει ≥1 item με `calories == null`, δείξε κουμπί
  **«🔍 Συμπλήρωσε θερμίδες (N)»** στην κεφαλίδα του meal (δίπλα στο «+ Add meal» / «+ Item»).
- `onclick → resolveMealMacros(mealId)`:

```js
async function resolveMealMacros(mealId) {
  try {
    const r = await api.post(`/nutrition/meals/${mealId}/resolve-macros`);
    const msg = `Λύθηκαν ${r.resolved.length} (OFF), `
              + `${r.estimated.length} εκτιμήσεις`
              + (r.unresolved.length ? `, ${r.unresolved.length} άλυτα` : "");
    showToast(msg, r.unresolved.length ? "warning" : "success");
    await loadDay();
  } catch (err) {
    showToast("Αποτυχία: " + err.message, "error");
  }
}
```

- Σε κάθε item, badge ανά πηγή: `product_search → «OFF»`, `llm_estimate → «~est»` (διακριτικό, π.χ. amber).
  Έτσι ο χρήστης βλέπει αμέσως τι είναι μετρημένο και τι εκτίμηση. Όλα editable όπως τώρα.

## 5. Edge cases

- Item με ήδη θερμίδες → δεν αγγίζεται (μόνο `calories is None`).
- OFF top match λάθος → ο χρήστης το βλέπει (badge «OFF» + όνομα) και κάνει Edit/Delete.
- `unit` σε τεμάχια → LLM `per_portion` ή unresolved (μήνυμα να βάλει γραμμάρια).
- Πολλά items → ένα commit· το response δίνει σύνοψη ανά κατηγορία.
- LLM down → estimated κενό, τα μη-OFF μένουν unresolved (χωρίς ψευδο-νούμερα).

## 6. Επαλήθευση

- Meal με items «Fitness Granola with honey», «Alpro Vanilla Vegan» χωρίς μακρο → κουμπί δείχνει «(2)»·
  tap → γεμίζουν από OFF, σύνολο meal ενημερώνεται, badge «OFF».
- Item με εξωτικό/ασαφές όνομα που δεν έχει το OFF → γίνεται «~est» με χαμηλό confidence.
- Item με ήδη θερμίδες → δεν μετριέται στο «(N)» ούτε αλλάζει.
- LLM offline → τα description-only χωρίς OFF match μένουν unresolved, με warning toast.

## 7. Σχέση με τα υπόλοιπα

- Επαναχρησιμοποιεί το `search_with_llm` (LLM reformulation + OFF) που ήδη υλοποιήσαμε.
- Ανεξάρτητο από το cooking-oil affordance· τα δύο συνεργάζονται (πρώτα λύνεις μακρο, μετά προσθέτεις λάδι αν τηγανίστηκε).
- Μελλοντικά: barcode scan για ακριβές match αντί free-text.

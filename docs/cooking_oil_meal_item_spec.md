# Spec: Cooking-oil affordance στο meal logging

> Κατάσταση: spec — έτοιμο για υλοποίηση. Καμία αλλαγή κώδικα ακόμη.
> Στόχος: ακριβέστερες θερμίδες όταν ένα oil-absorbing τρόφιμο (πανέ/σνίτσελ/τηγανητό)
> τηγανίζεται με λάδι — χωρίς να βαραίνει την κοινή περίπτωση.

## 1. Αρχές (locked decisions)

- **Scope: μόνο στο meal.** Το affordance ζει πάνω στο **MealItem μέσα στο meal/day view**, όχι στα search results. Η αξία υπάρχει μόνο όταν το τρόφιμο γίνεται κάτι που όντως έφαγες.
- **Conditional, όχι πάντα.** Εμφανίζεται μόνο σε oil-absorbing items. Default = δεν προστίθεται τίποτα (air fryer / φούρνος = η κοινή περίπτωση μένει καθαρή).
- **One-tap, editable.** Ένα tap προσθέτει ένα editable item «ελαιόλαδο (τηγάνισμα)» στο ίδιο meal· ο χρήστης ρυθμίζει γραμμάρια ή το σβήνει.
- **Detection = keywords** (ντετερμινιστικό, μηδέν latency). LLM flag = μελλοντική βελτίωση.
- **Μηδέν αλλαγή backend.** Το oil item είναι κανονικό `MealItem` μέσω του υπάρχοντος `addMealItem`.

## 2. Detection (keywords)

Helper στο frontend, case/accent-insensitive (κανονικοποίηση όπως στο `food_search._normalize_text`):

```
const OIL_ABSORBING_KEYWORDS = [
  // breaded
  "πανε", "σνιτσελ", "schnitzel", "breaded", "cordon bleu", "milanese",
  // nuggets / croquettes / fingers
  "nuggets", "κροκετ", "croquette", "κεφτεδ", "φιλετακια", "tenders", "fingers",
  // generic fried
  "τηγανητ", "τηγανισμεν", "fried", "πατατες τηγανητες", "french fries",
];
```

Match = το (normalized) όνομα του MealItem περιέχει οποιοδήποτε keyword.

> Σημείωση: skip το affordance αν το meal **έχει ήδη** item «ελαιόλαδο (τηγάνισμα)» συνδεδεμένο (αποφυγή διπλο-μέτρησης).

## 3. Oil-absorption εκτιμήσεις (default γραμμάρια ανά μερίδα)

Προσεγγιστικά, editable από τον χρήστη:

| Κατηγορία | Keyword group | Default λάδι |
|---|---|---|
| Πανέ / σνίτσελ | πανε, σνιτσελ, schnitzel, breaded, milanese, cordon bleu | **15 g** |
| Nuggets / κροκέτες / κεφτέδες | nuggets, κροκετ, croquette, κεφτεδ, tenders, fingers | **12 g** |
| Τηγανητά λαχανικά / πατάτες | τηγανητ, fried, french fries | **10 g** |
| Γενικό fallback | (άλλο match) | **12 g** |

Default αν δεν ξεχωρίζει κατηγορία: 12 g.

## 4. Macros του oil item

Ελαιόλαδο ανά 100 g: **884 kcal, 100 g λιπαρά, 0 carb, 0 protein**.
Για `g` γραμμάρια:

```
calories = round(8.84 * g)
fat_g    = round(g * 10) / 10
carbs_g  = 0
protein_g= 0
```

Το νέο MealItem:

```js
{
  name: "Ελαιόλαδο (τηγάνισμα)",
  quantity: g,
  unit: "g",
  calories, protein_g: 0, carbs_g: 0, fat_g,
  source: "cooking_oil",     // ξεχωριστό source για να το αναγνωρίζουμε
  confidence: 0.6,           // εκτίμηση, όχι μετρημένο
  source_ref: null,
}
```

## 5. UI (frontend, `public/js/nutrition.js`)

Στη συνάρτηση render των meal items (αυτή που τρέχει το `loadDay`):

- Όταν `isOilAbsorbing(item.name)` και δεν υπάρχει ήδη cooking-oil item στο meal →
  δείξε ένα διακριτικό chip κάτω/δίπλα στο item: **«🍳 τηγανισμένο; + λάδι»**.
- `onclick` → `addCookingOil(mealId, defaultGramsFor(item.name))`.
- Νέα handler:

```js
async function addCookingOil(mealId, grams) {
  const g = grams ?? 12;
  const item = {
    name: "Ελαιόλαδο (τηγάνισμα)",
    quantity: g, unit: "g",
    calories: Math.round(8.84 * g),
    protein_g: 0, carbs_g: 0,
    fat_g: Math.round(g * 10) / 10,
    source: "cooking_oil", confidence: 0.6, source_ref: null,
  };
  try {
    await api.addMealItem(mealId, item);
    showToast(`Προστέθηκε λάδι (${g}g)`, "success");
    await loadDay();
  } catch (err) {
    showToast("Αποτυχία: " + err.message, "error");
  }
}
```

Το γραμμάρια είναι editable μετά, όπως κάθε MealItem (υπάρχει ήδη `MealItemUpdate`).

## 6. Edge cases

- Ήδη υπάρχον cooking-oil item στο meal → μην δείχνεις ξανά το chip.
- Πολλά oil-absorbing items στο ίδιο meal → το chip ανά item· ο χρήστης αποφασίζει.
- Air fryer / φούρνος → απλώς δεν πατάει το chip (default συμπεριφορά).

## 7. Επαλήθευση

- Πρόσθεσε «Σνίτσελ Κοτόπουλου Πανέ» σε meal → εμφανίζεται το chip· tap → +«Ελαιόλαδο (τηγάνισμα) 15g», θερμίδες meal ανεβαίνουν ~133 kcal.
- Πρόσθεσε «Γιαούρτι στραγγιστό» → **δεν** εμφανίζεται chip.
- Πάτα chip δύο φορές → δεύτερη φορά δεν εμφανίζεται (υπάρχει ήδη oil item).
- Edit γραμμαρίων oil item → θερμίδες/λιπαρά αναπροσαρμόζονται.

## 8. Μελλοντικά (out of scope τώρα)

- LLM flag `oil_absorbing` από το search reformulation (αντί keywords).
- Cooking-method επιλογέας (air fryer / τηγάνι / φούρνος) με preset oil ανά μέθοδο.
- Διαφορετικά έλαια (ηλιέλαιο/βούτυρο) με δικά τους macros.

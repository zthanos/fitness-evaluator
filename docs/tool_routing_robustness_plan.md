# Plan: Tool-routing / args robustness

> Κατάσταση: plan. Στόχος: ο chat να σταματήσει να «καίει» iterations σε
> malformed/μισο-σωστά tool calls από τον μικρό subagent (llama-8b), ώστε
> ερωτήσεις όπως «can you see my activities?» να επιστρέφουν δεδομένα.

## Failure modes (από τα eval runs)

1. **Unknown params → hard fail.** π.χ. `evaluate_progress` κλήθηκε με
   `target_value`, `target_date` (params του `save_athlete_goal`). Το validation
   επιστρέφει `Unknown parameter(s)` και η κλήση πεθαίνει, ενώ το tool θα έτρεχε
   μια χαρά αγνοώντας τα extra.
2. **Κενά required enums.** `suggest_meal_recipe: meal_type ''`,
   `evaluate_performance_goal: sport_group ''` → enum validation fail.
3. **Malformed structured args.** `query_activities: filters` ως μη-JSON string
   (π.χ. "sport_type eq Ride") → το coercion `json.loads` αποτυγχάνει → μένει str
   → type validation fail. Σε 3 iterations το μοντέλο δεν διορθώνεται → 0 calls.
4. **(Δευτερεύον) Weak retry feedback.** Τα validation errors είναι
   `is_retryable=False` και το corrective μήνυμα δεν βοηθά αρκετά τον μικρό model.

## Fixes (κατά προτεραιότητα)

### T1 — Lenient, self-healing coercion (φθηνό, υψηλό όφελος)
Στο `_coerce_tool_params` (πριν το validation), πρόσθεσε:
- **Strip unknown params** (με warning) αντί να αποτυγχάνει το validation —
  σχεδόν όλα τα tools αγνοούν extra args. → λύνει το #1.
- **Drop empty-string values** για μη-required params (ώστε να ισχύσει το default
  του tool). → μετριάζει το #2 για optional enums.
- **Filters DSL fallback:** αν ένα `array` param είναι string που δεν είναι JSON,
  δοκίμασε να το parse-άρεις από απλό «field op value» σε
  `[{"field":..,"op":..,"value":..}]`. → λύνει το #3 για query_activities.

### T2 — Deterministic fast-path για activity_list
Όταν το intent είναι `ACTIVITY_LIST` («show/list my activities»), **παράκαμψε τον
subagent** και κάλεσε `query_activities` απευθείας με sane defaults (recent,
limit 10, χωρίς filters). Αφαιρεί εντελώς το πιο συχνό breakage (turn 3).

### T3 — Required-enum inference / defaults
- `meal_type`: infer από ώρα ημέρας (πρωί→breakfast κ.λπ.) ή κάν' το optional.
- `sport_group` (performance goal): infer από το dominant sport του αθλητή ή
  ζήτα clarification αντί για κενό.
- Επανέλεγξε το **routing** ώστε «I want to reach 85kg» να πηγαίνει σε
  `save_athlete_goal` (όχι `evaluate_performance_goal`).

### T4 — Καλύτερο retry feedback
Όταν αποτύχει validation, επίστρεψε στο μοντέλο σύντομο, **σχηματικό** corrective
(π.χ. «filters must be a JSON array: [{"field":"sport_type","op":"eq",
"value":"Ride"}]») και επίτρεψε 1-2 στοχευμένα retries γι' αυτή την περίπτωση.

## Προτεινόμενη σειρά
1. **T1** (lenient coercion) — διορθώνει #1, μετριάζει #2/#3 με μία αλλαγή σε ένα σημείο.
2. **T2** (activity fast-path) — κλείνει το turn-3 breakage.
3. **T3 / T4** — routing + feedback, αν χρειαστεί μετά.

## Verification
- Επανάλαβε το `evals/chat_grounding_eval.py`: το turn 3 πρέπει να επιστρέφει
  δεδομένα δραστηριοτήτων (όχι «I can't see your activities»), και να μην
  εμφανίζονται «Parameter validation failed» / «Unknown parameter(s)» στα logs.
- (Ιδανικά) ένα μικρό unit test στο `_coerce_tool_params` με malformed args.

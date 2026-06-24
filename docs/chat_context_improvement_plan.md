# Πλάνο βελτίωσης chat απαντήσεων & dynamic context

> Κατάσταση: **μόνο πλάνο** — καμία αλλαγή κώδικα ακόμη.
> Στόχος: λιγότερα hallucinations, συνέπεια μεταξύ turns, πιο περιεκτικό dynamic context.
> Βάση: ανάλυση του transcript + ο τρέχων κώδικας (`chat_agent.py`, `chat_context.py`, `rag_retriever.py`, prompts, evidence cards).

---

## 1. Τι συμβαίνει σήμερα (συνοπτικά)

Το intent ταξινομείται με LLM και ο `ChatAgent.execute` διακλαδώνεται σε δύο μονοπάτια:

- **Tool path** (intent με `INTENT_TOOL_HINT`): λιτό subagent καλεί tool → re-synthesis με το primary model και πλήρες system prompt.
- **Structured path** (`GENERAL` / χωρίς hint): μία κλήση με `ChatResponseContract`, **χωρίς tools**, μόνο με injected context.

Layers που μπαίνουν στο context: `coach_persona_v1.0.0` + Athlete Profile + Current Fitness State snapshot + task prompt + domain knowledge + evidence cards + history.

Η υποδομή υπάρχει· το πρόβλημα είναι **πώς** χρησιμοποιείται.

---

## 2. Ευρήματα → αλλαγές (κατά προτεραιότητα)

### P0 — Σταματούν τα κραυγαλέα hallucinations (φθηνό, υψηλό όφελος)

| # | Εύρημα (κώδικας) | Συμπεριφορά στο transcript | Αλλαγή |
|---|---|---|---|
| 1 | `system_loader.load()` φορτώνει hardcoded `coach_persona_v{version}.j2`. Το tool-aware `coach_chat_v1.0.0.j2` **δεν φορτώνεται ποτέ**. | Λείπουν οι κανόνες «μην γεμίζεις κενά», «tools μόνο για προσωπικά δεδομένα». | Ενεργοποίηση του `coach_chat` ως system prompt (ή merge των anti-hallucination κανόνων στο persona). |
| 2 | Evidence cards κρατούν raw `id`· `_format_task_and_data` & `_synthesize_with_primary` κάνουν `json.dumps(indent=2)`. | Διέρρευσαν «ID: 18711181827» στον χρήστη. | Αφαίρεση `source_id` από το prompt-facing serialization (μένει μόνο σε logs/trace). |
| 3 | Κανένα date anchor στο context. | «August 30th, suffering score 364» ενώ είναι Ιούνιος. | Σταθερό header `as_of_date` + ρητή λίστα «known fields» σε κάθε turn. |
| 4 | Prompt λέει «base on data» αλλά χωρίς hard guard· πεδία όπως `lean mass`, `suffer_score` δεν υπάρχουν. | «2.4kg lean mass», «suffer score 364» επινοημένα. | Κανόνας: «αν δεν είναι στο evidence, πες "δεν το παρακολουθώ" — μην υπολογίζεις». |

### P0.5 — Golden transcript tests (πριν από κάθε refactor σε context/cards)

Πριν αγγίξουμε context ή evidence cards, κλειδώνουμε **6–8 test cases** που ελέγχουν *forbidden claims* — έτσι το P0/P1 προστατεύεται από regressions.

| # | Κανόνας (assertion) |
|---|---|
| 1 | **Κανένα lean mass claim** εκτός αν το evidence έχει lean mass ή derived lean mass. |
| 2 | **Κανένα suffer score** εκτός αν το activity evidence το περιέχει. |
| 3 | **Καμία future-dated activity** εκτός αν η ημερομηνία υπάρχει όντως. |
| 4 | **Κανένα source/raw ID** στην απάντηση προς τον χρήστη. |
| 5 | **Όχι 90% confidence** όταν το completeness είναι χαμηλό. |
| 6 | **Max answer length** (όριο λέξεων). |
| 7 | Σε weight-based στόχο, η απάντηση **πρέπει** να αναφέρει current weight + date. |
| 8 | Όταν measurements/logs είναι sparse, η απάντηση **πρέπει** να αναφέρει αβεβαιότητα. |

Υλοποίηση ως replay tests πάνω στο golden transcript (στόχος 85kg → «δες βάρος» → «δες activities» → νηστεία), με regex/structured assertions στο τελικό `response_text` και στα evidence που μπήκαν στο context.

### P1 — Συνέπεια μεταξύ turns

| # | Εύρημα | Συμπεριφορά | Αλλαγή |
|---|---|---|---|
| 5 | Δύο paths δίνουν ασύμμετρο context· trend μόνο μέσω tools. | «92.9kg» στο ένα turn, «δεν έχω trends» στο διπλανό. | Σταθερό **Athlete State block** (τελευταίο βάρος/BF%, ενεργοί στόχοι, `weight_slope_kg_per_week` από derived) σε **κάθε** turn, ανεξαρτήτως path/intent. |
| 6 | Το trend υπολογίζεται ad-hoc από το μοντέλο. | Λάθος φυσιολογία: «βάρος ↓ + BF% ↑ → χτίζω μυς». | Single source of truth: `body_trend.weight_slope_kg_per_week` από το derived layer, ποτέ από το μοντέλο. |

### P2 — Περιεκτικότητα του dynamic context

| # | Εύρημα | Αλλαγή |
|---|---|---|
| 7 | `_generate_metric_claim` πετά `body_fat_pct`· activity card χωρίς power/HR/suffer· κρατούν `id`. | Cards να κρατούν τα **ουσιώδη** πεδία ανά τύπο (metric: date/weight/BF%/RHR· activity: date/type/dist/dur/avgHR/power) και να πετούν IDs/nulls. |
| 8 | `token_budget=32000` default (docstring λέει 2400)· retrieval=8000. | Ένα ξεκάθαρο budget (π.χ. ~1500–2000 tokens dynamic), ευθυγράμμιση docstrings/defaults. |
| 9 | Verbose `json.dumps(indent=2)` με nulls. | Compact, μία γραμμή ανά card· χωρίς `null` πεδία. |

### P3 — Calibration & format

| # | Εύρημα | Αλλαγή |
|---|---|---|
| 10 | `confidence_score` ασύνδετο με data completeness· γράφεται ως «90%» μέσα στο κείμενο. | Σύνδεση με `completeness_scorer`· low data ⇒ low confidence· να μην εμφανίζεται ως ποσοστό στο prose. |
| 11 | `response_text` free-form· guideline 50–500 λέξεις αγνοείται. | Σκληρό όριο μήκους + δομή (headline → 2–3 προτάσεις → 1 next action), όπως ο υπάρχων `CoachSynthesizer`. |

### P4 — Αρχιτεκτονικό (μεγαλύτερο, προαιρετικό)

- **Σύγκλιση των δύο paths:** είτε το RAG δίνει μόνο «light state» και κάθε ανάλυση πάει μέσω tools, είτε το αντίστροφο — όχι και τα δύο να επικαλύπτονται/συγκρούονται.
- Ενοποίηση intent classification (τώρα LLM στο `chat_agent` + keyword στον `IntentRouter`/`builder`).

---

## 3. Προτεινόμενη σειρά υλοποίησης

1. **P0** (#1–#4): ενεργοποίηση `coach_chat`, καθάρισμα IDs, date anchor, anti-fabrication guard.
2. **P0.5**: golden transcript tests με forbidden-claim assertions — **πριν** τα επόμενα refactors.
3. **P1** (#5–#6): Athlete State block + single source of truth για trend.
4. **P2** (#7–#9): rework evidence cards + budget + compact serialization.
5. **P3** (#10–#11): confidence calibration + enforce format.
6. **P4**: αρχιτεκτονική σύγκλιση paths (ξεχωριστό milestone).

> Πρακτική πρώτη υλοποίηση: `coach_chat` prompt → prompt-safe evidence serialization → Athlete State block → compact evidence cards (με τα P0.5 tests να τρέχουν σε κάθε βήμα).

## 4. Πώς επαληθεύουμε

- Replay του ίδιου transcript (στόχος 85kg, «δες το βάρος μου», «δες activities», νηστεία) και έλεγχος ότι: (α) δεν εμφανίζονται επινοημένα πεδία, (β) δεν διαρρέουν IDs, (γ) το βάρος/trend είναι συνεπή μεταξύ turns, (δ) απαντήσεις < όριο λέξεων.
- Μέτρηση `total_context_tokens` από το trace πριν/μετά (στόχος: σημαντική μείωση).

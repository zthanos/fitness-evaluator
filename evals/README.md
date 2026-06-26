# Evals

Manual, live-model evaluations. Unlike `tests/`, these are **not** part of CI:
they need a running LLM and are non-deterministic.

## chat_grounding_eval.py

Runs the real chat pipeline over a fixed multi-turn transcript (the one that
motivated the chat-context refactor) and asserts "forbidden claim" rules on the
actual model output — e.g. no fabricated `lean mass` / `suffer score`, no leaked
DB ids, no future-dated activities, no overconfidence on sparse data, a length
cap, and required grounding (current weight + target date, uncertainty when
data is sparse).

Run it (with your local LLM up and the DB reachable):

```bash
uv run python evals/chat_grounding_eval.py
```

It seeds a throwaway athlete, runs the transcript, prints each answer with
per-check PASS/FAIL, cleans up, and exits non-zero if any check fails.

Use it as the grounding gate before/after the P0 chat-context changes: run it on
`main` to capture the baseline failures, then re-run after each P0 step to watch
them flip to PASS.

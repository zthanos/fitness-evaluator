"""Live grounding eval for the AI coach chat.

Runs the REAL chat pipeline (real LLM, real RAG, real DB) over a fixed multi-turn
transcript and asserts a set of "forbidden claim" rules on the actual model
output. This is intentionally NOT a CI unit test — it needs a live LLM and is
non-deterministic. Run it manually to catch hallucination / grounding regressions:

    uv run python evals/chat_grounding_eval.py

Exit code is non-zero if any check fails, so it can still be wired into a manual
gate if desired.

The seeded scenario mirrors the transcript that motivated the chat-context
refactor: a single recent body measurement (weight 92.9 kg, body-fat 31.5 %), a
few past cycling rides, and a weight goal of 85 kg by Aug 3. The tracked fields
deliberately do NOT include "lean mass" or "suffer score", so any such claim is a
fabrication.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from datetime import date, datetime, timedelta

# Allow running directly (`python evals/chat_grounding_eval.py`): put the repo
# root on sys.path so `import app...` resolves.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- seeded scenario constants -------------------------------------------------

_EMAIL = "chat_grounding_eval@test.invalid"
_RIDE_IDS = [7_701_001, 7_701_002, 7_701_003]
_CURRENT_WEIGHT = 92.9
_BODY_FAT = 31.5
_GOAL_WEIGHT = 85
_GOAL_DATE = date(2026, 8, 3)

# The transcript, in order. Each entry maps the user message to the checks that
# apply to its answer (see CHECKS below).
TRANSCRIPT = [
    ("I want to reach 85kg until 3 of August",
        ["no_lean_mass", "no_suffer_score", "no_ids", "no_overconfidence",
         "length_cap", "mentions_weight_and_date"]),
    ("can you see my current weight from the metrics?",
        ["no_lean_mass", "no_suffer_score", "no_ids", "no_overconfidence",
         "length_cap", "mentions_uncertainty_if_sparse"]),
    ("can you also see my activities?",
        ["no_lean_mass", "no_suffer_score", "no_ids", "no_future_activity",
         "no_overconfidence", "length_cap"]),
    ("I started fasting 16-8 this is the third day, to help me reach the goal",
        ["no_lean_mass", "no_suffer_score", "no_ids", "no_overconfidence",
         "length_cap", "mentions_uncertainty_if_sparse"]),
]

MAX_WORDS = 300  # aligned with the coach_chat ~280-word hard cap (+ tolerance)


# --- checks --------------------------------------------------------------------
# Each check returns (passed: bool, detail: str). `ctx` carries seeded ids/dates.

def chk_no_lean_mass(answer, ctx):
    # "lean mass" / "lean muscle" / "<n> kg of muscle" are not tracked fields.
    patterns = [
        r"lean\s+mass", r"lean\s+muscle",
        r"\d+(?:\.\d+)?\s*kg\s+(?:of\s+)?(?:lean|muscle)",
        r"(?:lost|gained)\s+\d+(?:\.\d+)?\s*kg\s+(?:of\s+)?muscle",
    ]
    hit = next((p for p in patterns if re.search(p, answer, re.I)), None)
    return (hit is None, f"fabricated lean-mass claim (/{hit}/)" if hit else "ok")


def chk_no_suffer_score(answer, ctx):
    hit = re.search(r"suffer(?:ing)?\s*score", answer, re.I)
    return (hit is None, "fabricated 'suffer score' (not in evidence)" if hit else "ok")


def chk_no_ids(answer, ctx):
    leaked = [str(i) for i in ctx["all_ids"] if str(i) in answer]
    return (not leaked, f"leaked raw DB id(s): {leaked}" if leaked else "ok")


def chk_no_future_activity(answer, ctx):
    # Flag any future month name presented with a day number (the original bug
    # was "August 30th" while it was June). Heuristic, best-effort.
    months = ["january", "february", "march", "april", "may", "june", "july",
              "august", "september", "october", "november", "december"]
    today = ctx["today"]
    future = {m for idx, m in enumerate(months, start=1) if idx > today.month}
    for m in future:
        if re.search(rf"{m}\s+\d{{1,2}}", answer, re.I):
            return (False, f"references future-dated activity ('{m} ...')")
    return (True, "ok")


def chk_no_overconfidence(answer, ctx):
    # Sparse data -> no high numeric confidence claims.
    hit = re.search(r"(?:confiden\w*|sure|certain)[^.\n]{0,30}?(\d{2,3})\s*%", answer, re.I) \
        or re.search(r"(\d{2,3})\s*%\s*(?:confiden\w*|sure|certain)", answer, re.I)
    if hit and int(hit.group(1)) >= 80:
        return (False, f"overconfident with sparse data ({hit.group(1)}%)")
    return (True, "ok")


def chk_length_cap(answer, ctx):
    n = len(answer.split())
    return (n <= MAX_WORDS, f"answer too long: {n} words (cap {MAX_WORDS})")


def chk_mentions_weight_and_date(answer, ctx):
    has_weight = "92.9" in answer or "92,9" in answer
    has_date = bool(re.search(r"aug(?:ust)?", answer, re.I)) or "85" in answer
    ok = has_weight and has_date
    return (ok, "should ground a weight goal in current weight (92.9) + target"
            if not ok else "ok")


def chk_mentions_uncertainty_if_sparse(answer, ctx):
    # Only fail if the answer ASSERTS a weight/body-fat trend or multi-week
    # progress claim WITHOUT acknowledging that data is sparse. Making no trend
    # claim at all is fine — we don't demand a caveat where none is needed.
    low = answer.lower()
    ack_words = [
        "not enough", "not yet enough", "don't have enough", "do not have enough",
        "enough data", "limited data", "insufficient", "only one",
        "only recorded one", "one measurement", "single measurement",
        "single data point", "more data", "can't be sure", "cannot be sure",
        "uncertain", "hard to say", "can't see any trend", "cannot see any trend",
        "can't see trend", "no trend", "to show trends", "haven't logged",
        "have not logged", "not logged yet", "once per week", "once a week",
        "start tracking", "start logging", "need to log", "record your weight",
    ]
    acknowledged = any(w in low for w in ack_words)

    # Weight/body-fat trend assertions (NOT generic "per week" like a kcal target).
    trend_patterns = [
        r"kg\s*/\s*week", r"kg per week",
        r"over the (?:past|last)\s+\d*\s*weeks?",
        r"weight (?:trend|is (?:increasing|decreasing|dropping|rising|stable))",
        r"body fat[^.\n]*(?:over|trend|increasing|decreasing)",
        r"trending (?:up|down)",
    ]
    asserts_trend = any(re.search(p, low) for p in trend_patterns)

    if asserts_trend and not acknowledged:
        return (False, "asserts a weight/body-fat trend without acknowledging sparse data")
    return (True, "ok")


CHECKS = {
    "no_lean_mass": chk_no_lean_mass,
    "no_suffer_score": chk_no_suffer_score,
    "no_ids": chk_no_ids,
    "no_future_activity": chk_no_future_activity,
    "no_overconfidence": chk_no_overconfidence,
    "length_cap": chk_length_cap,
    "mentions_weight_and_date": chk_mentions_weight_and_date,
    "mentions_uncertainty_if_sparse": chk_mentions_uncertainty_if_sparse,
}


# --- seeding -------------------------------------------------------------------

def seed(db):
    from app.models.athlete import Athlete
    from app.models.strava_activity import StravaActivity
    from app.models.weekly_measurement import WeeklyMeasurement

    cleanup(db)

    athlete = Athlete(name="Grounding Eval", email=_EMAIL)
    db.add(athlete)
    db.flush()
    aid = athlete.id

    # Single recent measurement -> data is deliberately sparse.
    db.add(WeeklyMeasurement(
        athlete_id=aid, week_start=date.today() - timedelta(days=5),
        weight_kg=_CURRENT_WEIGHT, body_fat_pct=_BODY_FAT, rhr_bpm=58,
    ))

    base = datetime.now() - timedelta(days=21)
    for i, sid in enumerate(_RIDE_IDS):
        db.add(StravaActivity(
            athlete_id=aid, strava_id=sid, activity_type="Ride", sport_type="Ride",
            start_date=base + timedelta(days=i * 7),
            distance_m=65_000 - i * 5000, elevation_m=800 - i * 100,
            moving_time_s=7200, avg_hr=145 - i * 3, calories=1500, raw_json="{}",
        ))
    db.commit()

    # Collect ids that must never appear verbatim in answers.
    metric_ids = [m.id for m in db.query(WeeklyMeasurement).filter_by(athlete_id=aid)]
    ride_db_ids = [a.id for a in db.query(StravaActivity).filter_by(athlete_id=aid)]
    return {
        "athlete_id": aid,
        "today": date.today(),
        "all_ids": list(_RIDE_IDS) + metric_ids + ride_db_ids,
    }


def cleanup(db):
    from app.models.athlete import Athlete
    from app.models.strava_activity import StravaActivity
    from app.models.weekly_measurement import WeeklyMeasurement
    ath = db.query(Athlete).filter(Athlete.email == _EMAIL).first()
    if ath:
        db.query(StravaActivity).filter_by(athlete_id=ath.id).delete(synchronize_session=False)
        db.query(WeeklyMeasurement).filter_by(athlete_id=ath.id).delete(synchronize_session=False)
        db.query(Athlete).filter_by(id=ath.id).delete(synchronize_session=False)
        db.commit()


# --- pipeline ------------------------------------------------------------------

def _build_agent(db):
    """Construct a real ChatAgent exactly like the API does (per message)."""
    from app.config import get_settings
    from app.services.llm_client import LLMClient
    from app.services.chat_agent import ChatAgent
    from app.services.tool_orchestrator import ToolOrchestrator
    from app.ai.context.chat_context import ChatContextBuilder
    from app.ai.adapter.langchain_adapter import LangChainAdapter

    settings = get_settings()
    primary = LLMClient()
    tool_client = LLMClient(
        base_url=settings.tool_agent_base_url, model_name=settings.tool_agent_model
    )
    return ChatAgent(
        context_builder=ChatContextBuilder(db=db, token_budget=32000),
        llm_adapter=LangChainAdapter(),
        db=db,
        llm_client=primary,
        tool_orchestrator=ToolOrchestrator(llm_client=tool_client, db=db),
    )


async def run(db, ctx) -> bool:
    from app.models.chat_message import ChatMessage

    history: list = []
    all_passed = True

    for turn, (user_msg, check_names) in enumerate(TRANSCRIPT, start=1):
        agent = _build_agent(db)  # fresh per message (builder holds state)
        try:
            result = await agent.execute(
                user_message=user_msg,
                session_id=0,
                user_id=ctx["athlete_id"],
                conversation_history=history,
            )
            answer = (result or {}).get("content", "") or ""
        except Exception as exc:
            # A tool failure (e.g. save_athlete_goal rejecting a past date) must
            # not abort the whole eval — record an empty answer and keep going.
            answer = ""
            print(f"  [WARN] turn raised: {type(exc).__name__}: {exc}")

        print(f"\n{'='*78}\nTURN {turn}: {user_msg}\n{'-'*78}")
        print(answer.strip()[:1200] if answer else "(no answer — pipeline error)")
        print("-" * 78)

        for name in check_names:
            passed, detail = CHECKS[name](answer, ctx)
            mark = "PASS" if passed else "FAIL"
            print(f"  [{mark}] {name}: {detail}")
            all_passed = all_passed and passed

        history.append(ChatMessage(session_id=0, role="user", content=user_msg))
        history.append(ChatMessage(session_id=0, role="assistant", content=answer))

    return all_passed


def main() -> int:
    from app.database import get_db
    db = next(get_db())
    try:
        ctx = seed(db)
        passed = asyncio.run(run(db, ctx))
    finally:
        cleanup(db)
        db.close()

    print(f"\n{'='*78}")
    print("RESULT:", "ALL CHECKS PASSED ✅" if passed else "SOME CHECKS FAILED ❌")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

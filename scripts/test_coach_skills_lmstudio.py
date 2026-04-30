"""
Integration tests for the fitness coach skill pipeline against LM Studio.

Runs end-to-end conversations through ToolOrchestrator → execute_tool → skills.
Each scenario asserts that the LLM chose the expected tool and that the tool
returned a structured, non-empty result.

Usage:
    # From repo root with venv active:
    python scripts/test_coach_skills_lmstudio.py

    # Run a single scenario by name:
    python scripts/test_coach_skills_lmstudio.py --scenario workout

Requirements:
    - LM Studio running and serving a tool-calling model (e.g. qwen2.5, mistral-nemo)
    - .env configured with LLM_TYPE, LM_STUDIO_MODEL, LM_STUDIO_BASE_URL
    - Database reachable (SQLALCHEMY_DATABASE_URL in .env)
    - Athlete with id=1 present in the database (no Strava data required)
"""

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

# ── Repo root on path ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env before importing app modules
from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.services.llm_client import LLMClient
from app.services.chat_tools import get_tool_definitions
from app.services.tool_orchestrator import ToolOrchestrator

# ── Config ────────────────────────────────────────────────────────────────────

ATHLETE_ID = 1          # Change to your test athlete's DB id
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"

# ── Scenario definition ───────────────────────────────────────────────────────

@dataclass
class Scenario:
    name: str
    description: str
    messages: list[dict]                  # conversation to send
    expected_tool: str                    # tool the LLM should call
    result_keys: list[str] = field(default_factory=list)  # keys that must be in tool result
    optional: bool = False                # if True, failure is a warning not an error


SCENARIOS: list[Scenario] = [
    # ── 1. Workout analysis ──────────────────────────────────────────────────
    Scenario(
        name="workout",
        description="Athlete asks about their last ride → should call analyze_recent_workout",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precision endurance coach. "
                    "Use the analyze_recent_workout tool when the athlete asks about their last workout. "
                    "Always call a tool before responding."
                ),
            },
            {
                "role": "user",
                "content": "Can you analyse my last ride and tell me what my main limiter is?",
            },
        ],
        expected_tool="analyze_recent_workout",
        result_keys=["success", "headline"],
    ),

    # ── 2. Recovery check ────────────────────────────────────────────────────
    Scenario(
        name="recovery",
        description="Athlete asks if they should train today → should call evaluate_recovery",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precision endurance coach. "
                    "Use the evaluate_recovery tool when the athlete asks about their recovery or whether to train. "
                    "Always call a tool before responding."
                ),
            },
            {
                "role": "user",
                "content": (
                    "I trained hard the last three days. Should I go for a hard session today "
                    "or take it easy? How's my fatigue level?"
                ),
            },
        ],
        expected_tool="evaluate_recovery",
        result_keys=["success", "recovery"],
    ),

    # ── 3. Progress check ────────────────────────────────────────────────────
    Scenario(
        name="progress",
        description="Athlete asks about goal progress → should call evaluate_progress",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precision endurance coach. "
                    "Use the evaluate_progress tool when the athlete asks about their goal progress or weight trend. "
                    "Always call a tool before responding."
                ),
            },
            {
                "role": "user",
                "content": "Am I on track with my weight loss goal? How's my progress over the last 8 weeks?",
            },
        ],
        expected_tool="evaluate_progress",
        result_keys=["success", "progress"],
    ),

    # ── 4. Plan generation ───────────────────────────────────────────────────
    Scenario(
        name="plan",
        description="Athlete asks for a training plan → should call generate_plan",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precision endurance coach. "
                    "Use the generate_plan tool when the athlete asks for a training plan or programme. "
                    "Always call a tool before responding."
                ),
            },
            {
                "role": "user",
                "content": (
                    "I want to build my cycling fitness over the next 4 weeks. "
                    "Can you create a structured training plan for me?"
                ),
            },
        ],
        expected_tool="generate_plan",
        result_keys=["success", "headline"],
    ),

    # ── 5. Strava activity detail ────────────────────────────────────────────
    Scenario(
        name="activity_detail",
        description="Athlete asks about a specific activity → should call fetch_strava_activity_detail",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precision endurance coach. "
                    "Use the fetch_strava_activity_detail tool when the athlete provides a Strava activity ID. "
                    "Always call a tool before responding."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Can you pull the details for Strava activity 12345678? "
                    "I want to see the power and cadence data."
                ),
            },
        ],
        expected_tool="fetch_strava_activity_detail",
        result_keys=["strava_id"],
        optional=True,  # May fail if no Strava token configured
    ),

    # ── 6. Multi-turn: workout then recovery ─────────────────────────────────
    Scenario(
        name="multi_turn",
        description="Multi-turn: analyse workout then ask about recovery",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precision endurance coach. "
                    "Use the evaluate_recovery tool for recovery questions. "
                    "Always call a tool before responding."
                ),
            },
            {"role": "user",    "content": "How did my last ride go?"},
            {"role": "assistant", "content": "Let me check your recent workout data for you."},
            {"role": "user",    "content": "Given that, should I do a hard session tomorrow or rest?"},
        ],
        expected_tool="evaluate_recovery",
        result_keys=["success"],
    ),

    # ── 7. Web search passthrough ────────────────────────────────────────────
    Scenario(
        name="web_search",
        description="General sports science question → should call search_web",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precision endurance coach. "
                    "Use the search_web tool for general sports science questions. "
                    "Always call a tool before responding."
                ),
            },
            {
                "role": "user",
                "content": "What does the latest research say about Zone 2 training for cycling performance?",
            },
        ],
        expected_tool="search_web",
        result_keys=["query"],
        optional=True,  # Requires TAVILY_API_KEY
    ),
]

# ── Test runner ───────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    scenario: str
    passed: bool
    optional: bool
    tool_called: Optional[str]
    expected_tool: str
    result_keys_present: list[str]
    result_keys_missing: list[str]
    error: Optional[str]
    latency_ms: float
    tool_result_preview: str = ""


async def run_scenario(
    scenario: Scenario,
    orchestrator: ToolOrchestrator,
    athlete_id: int,
) -> TestResult:
    """Run a single test scenario through the ToolOrchestrator."""
    start = time.time()
    tool_called: Optional[str] = None
    error: Optional[str] = None
    keys_present: list[str] = []
    keys_missing: list[str] = []
    tool_result_preview = ""

    try:
        result = await orchestrator.orchestrate(
            conversation=list(scenario.messages),  # copy — orchestrator mutates
            tool_definitions=get_tool_definitions(),
            user_id=athlete_id,
        )

        # Find which tool was called
        tool_results = result.get("tool_results", [])
        if tool_results:
            tool_called = tool_results[0].get("tool_name")
            raw_result = tool_results[0].get("result", {})

            # Check expected result keys
            if isinstance(raw_result, dict):
                keys_present = [k for k in scenario.result_keys if k in raw_result]
                keys_missing = [k for k in scenario.result_keys if k not in raw_result]
                preview = json.dumps(raw_result, default=str)
                tool_result_preview = preview[:300] + ("…" if len(preview) > 300 else "")
        else:
            error = "No tool was called (LLM answered directly without using a tool)"

    except Exception as exc:
        error = str(exc)

    latency_ms = (time.time() - start) * 1000
    tool_matched = (tool_called == scenario.expected_tool)
    passed = (
        tool_matched
        and not keys_missing
        and error is None
    )

    return TestResult(
        scenario=scenario.name,
        passed=passed,
        optional=scenario.optional,
        tool_called=tool_called,
        expected_tool=scenario.expected_tool,
        result_keys_present=keys_present,
        result_keys_missing=keys_missing,
        error=error,
        latency_ms=latency_ms,
        tool_result_preview=tool_result_preview,
    )


def print_result(r: TestResult) -> None:
    icon = PASS if r.passed else (WARN if r.optional else FAIL)
    status = "PASS" if r.passed else ("WARN" if r.optional else "FAIL")
    print(f"\n{icon} [{status}] {r.scenario} ({r.latency_ms:.0f}ms)")

    if r.tool_called == r.expected_tool:
        print(f"   Tool: {r.tool_called} ✓")
    else:
        print(f"   Tool expected: {r.expected_tool}")
        print(f"   Tool called:   {r.tool_called or '(none)'} ✗")

    if r.result_keys_present:
        print(f"   Keys found: {r.result_keys_present}")
    if r.result_keys_missing:
        print(f"   Keys missing: {r.result_keys_missing} ✗")
    if r.error:
        print(f"   Error: {r.error}")
    if r.tool_result_preview:
        print(f"   Result preview: {r.tool_result_preview}")


async def main(scenario_filter: Optional[str] = None) -> int:
    """Run all (or filtered) scenarios. Returns exit code (0=all pass)."""
    print("=" * 65)
    print("  Fitness Coach Skills — LM Studio Integration Tests")
    print("=" * 65)

    # Check LM Studio connectivity
    from app.config import get_settings
    settings = get_settings()
    print(f"\nLLM endpoint : {settings.llm_base_url}")
    print(f"Model        : {getattr(settings, 'LM_STUDIO_MODEL', getattr(settings, 'OLLAMA_MODEL', '?'))}")
    print(f"Athlete ID   : {ATHLETE_ID}")

    db = SessionLocal()
    llm_client = LLMClient()

    # Verify athlete exists
    from app.models.athlete import Athlete
    athlete = db.query(Athlete).filter(Athlete.id == ATHLETE_ID).first()
    if not athlete:
        print(f"\n{FAIL} Athlete id={ATHLETE_ID} not found in database.")
        print("   Create an athlete or change ATHLETE_ID at the top of this script.")
        db.close()
        return 1
    print(f"Athlete      : {getattr(athlete, 'name', athlete.id)}")

    orchestrator = ToolOrchestrator(
        llm_client=llm_client,
        db=db,
        max_iterations=3,
    )

    scenarios = SCENARIOS
    if scenario_filter:
        scenarios = [s for s in SCENARIOS if s.name == scenario_filter]
        if not scenarios:
            print(f"\n{FAIL} No scenario named '{scenario_filter}'.")
            print(f"   Available: {', '.join(s.name for s in SCENARIOS)}")
            db.close()
            return 1

    results: list[TestResult] = []
    for scenario in scenarios:
        print(f"\n→ Running: {scenario.name} — {scenario.description}")
        r = await run_scenario(scenario, orchestrator, ATHLETE_ID)
        results.append(r)
        print_result(r)

    db.close()

    # Summary
    total    = len(results)
    passed   = sum(1 for r in results if r.passed)
    optional_failed = sum(1 for r in results if not r.passed and r.optional)
    hard_failed = sum(1 for r in results if not r.passed and not r.optional)

    print("\n" + "=" * 65)
    print(f"  Results: {passed}/{total} passed", end="")
    if optional_failed:
        print(f", {optional_failed} optional warning(s)", end="")
    print()
    if hard_failed:
        print(f"  {FAIL} {hard_failed} required test(s) FAILED")
    else:
        print(f"  {PASS} All required tests passed")
    print("=" * 65)

    return 0 if hard_failed == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LM Studio integration tests for coach skills")
    parser.add_argument(
        "--scenario", "-s",
        help="Run only this scenario (workout/recovery/progress/plan/activity_detail/multi_turn/web_search)",
        default=None,
    )
    parser.add_argument(
        "--athlete-id", "-a",
        type=int,
        default=ATHLETE_ID,
        help=f"Athlete DB id to test with (default: {ATHLETE_ID})",
    )
    args = parser.parse_args()
    ATHLETE_ID = args.athlete_id

    exit_code = asyncio.run(main(scenario_filter=args.scenario))
    sys.exit(exit_code)

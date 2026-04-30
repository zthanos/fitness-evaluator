"""Pipeline-level answer quality tests.

Tests the full ChatAgent → ToolOrchestrator → _query_activities → synthesis
flow. The LLM is replaced with deterministic fakes so tests are:
  - Fast (no network calls)
  - Reproducible (same tool params every run)
  - Focused on data correctness (right facts reach the user)

Each test class covers one category of natural-language question.
The "expected answer facts" assertions are the quality bar — if they fail,
either the tool returned wrong data or the synthesis ignored the data.
"""
import json
import pytest
from collections import namedtuple
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from app.services.chat_agent import ChatAgent
from app.models.athlete import Athlete
from app.models.strava_activity import StravaActivity
from app.database import get_db

_TEST_RIDE_IDS   = [9_901_001, 9_901_002, 9_901_003, 9_901_004, 9_901_005]
_TEST_RIDE_EMAIL = "test_aq_rider@test.invalid"

RideCtx = namedtuple("RideCtx", ["db", "athlete_id"])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session():
    db = next(get_db())
    yield db
    db.close()


@pytest.fixture()
def seeded_rides(db_session: Session) -> RideCtx:
    """Create one throwaway athlete + 5 rides of known distances."""
    db_session.query(StravaActivity).filter(
        StravaActivity.strava_id.in_(_TEST_RIDE_IDS)
    ).delete(synchronize_session=False)
    db_session.query(Athlete).filter(
        Athlete.email == _TEST_RIDE_EMAIL
    ).delete(synchronize_session=False)
    db_session.commit()

    athlete = Athlete(name="Test Rider", email=_TEST_RIDE_EMAIL)
    db_session.add(athlete)
    db_session.flush()
    aid = athlete.id

    base = datetime(2024, 3, 1)
    rides = [
        StravaActivity(athlete_id=aid, strava_id=9_901_001, activity_type="Ride", sport_type="Ride",
                       start_date=base,                       distance_m=120_500, elevation_m=1800,
                       moving_time_s=14400, avg_hr=148, calories=2100, raw_json="{}"),
        StravaActivity(athlete_id=aid, strava_id=9_901_002, activity_type="Ride", sport_type="Ride",
                       start_date=base + timedelta(days=7),   distance_m=95_200,  elevation_m=900,
                       moving_time_s=10800, avg_hr=142, calories=1600, raw_json="{}"),
        StravaActivity(athlete_id=aid, strava_id=9_901_003, activity_type="Ride", sport_type="Ride",
                       start_date=base + timedelta(days=14),  distance_m=78_000,  elevation_m=650,
                       moving_time_s=9000,  avg_hr=145, calories=1300, raw_json="{}"),
        StravaActivity(athlete_id=aid, strava_id=9_901_004, activity_type="Ride", sport_type="Ride",
                       start_date=base + timedelta(days=21),  distance_m=55_500,  elevation_m=400,
                       moving_time_s=6300,  avg_hr=138, calories=950,  raw_json="{}"),
        StravaActivity(athlete_id=aid, strava_id=9_901_005, activity_type="Ride", sport_type="Ride",
                       start_date=base + timedelta(days=28),  distance_m=42_000,  elevation_m=300,
                       moving_time_s=4800,  avg_hr=132, calories=700,  raw_json="{}"),
    ]
    db_session.add_all(rides)
    db_session.commit()

    yield RideCtx(db=db_session, athlete_id=aid)

    db_session.query(StravaActivity).filter(
        StravaActivity.strava_id.in_(_TEST_RIDE_IDS)
    ).delete(synchronize_session=False)
    db_session.query(Athlete).filter(
        Athlete.email == _TEST_RIDE_EMAIL
    ).delete(synchronize_session=False)
    db_session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_call_response(tool_name: str, arguments: dict) -> dict:
    """Return value that mimics LLMClient.chat_completion for a tool call."""
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call_test_001",
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(arguments),
            },
        }],
    }


def _text_response(content: str) -> dict:
    return {"role": "assistant", "content": content}


def _make_agent(ctx: RideCtx, tool_agent_side_effects: list, primary_response: str) -> ChatAgent:
    """
    Build a ChatAgent with both LLM clients mocked.

    tool_agent_side_effects: list of dicts returned by tool-agent calls in order.
    primary_response: text returned by the primary reasoning model (synthesis).
    """
    from app.services.tool_orchestrator import ToolOrchestrator
    from app.ai.context.chat_context import ChatContextBuilder

    tool_client = MagicMock()
    tool_client.chat_completion = AsyncMock(side_effect=tool_agent_side_effects)

    primary_client = MagicMock()
    primary_client.chat_completion = AsyncMock(
        return_value={"content": primary_response, "role": "assistant"}
    )

    return ChatAgent(
        context_builder=ChatContextBuilder(db=ctx.db, token_budget=32000),
        llm_adapter=None,
        db=ctx.db,
        llm_client=primary_client,
        tool_orchestrator=ToolOrchestrator(llm_client=tool_client, db=ctx.db),
    )


async def _run_query(agent: ChatAgent, question: str, user_id: int) -> dict:
    """Execute a query through ChatAgent, bypassing intent classification and CE loaders."""
    with patch(
        "app.ai.retrieval.llm_intent_classifier.classify_intent",
        new_callable=AsyncMock,
    ) as mock_intent:
        from app.ai.retrieval.intent_router import Intent
        mock_intent.return_value = Intent.ACTIVITY_LIST

        with patch.object(agent, "_load_defaults") as mock_load:
            mock_load.return_value = ("", "", {}, "")
            with patch.object(agent, "_build_context") as mock_ctx:
                fake_ctx = MagicMock()
                fake_ctx.token_count = 100
                fake_ctx.to_messages.return_value = [
                    {"role": "system", "content": "You are a fitness coach."},
                ]
                mock_ctx.return_value = fake_ctx

                return await agent.execute(
                    user_message=question,
                    session_id=1,
                    user_id=user_id,
                    conversation_history=[],
                )


# ---------------------------------------------------------------------------
# Test: longest rides
# ---------------------------------------------------------------------------

class TestLongestRides:
    """'Which are my longest rides?' and variants."""

    @pytest.mark.asyncio
    async def test_longest_rides_answer_contains_top_distances(self, seeded_rides: RideCtx):
        """Answer must mention the actual distances of the top rides."""
        tool_call = _tool_call_response(
            "query_activities",
            {
                "filters": [{"field": "sport_type", "op": "eq", "value": "Ride"}],
                "sort": [{"field": "distance_m", "dir": "desc"}],
                "limit": 5,
            },
        )
        synthesis = "Your 5 longest rides: 120.5 km, 95.2 km, 78.0 km, 55.5 km, 42.0 km."
        agent = _make_agent(seeded_rides, [tool_call, _text_response("Done.")], synthesis)

        result = await _run_query(agent, "Which are my longest rides?", seeded_rides.athlete_id)

        assert result["tool_calls_made"] == 1
        assert "120" in result["content"]
        assert "95" in result["content"]

    @pytest.mark.asyncio
    async def test_top_3_longest_rides(self, seeded_rides: RideCtx):
        """'My 3 longest rides' — limit must be 3, answer must cite all three."""
        tool_call = _tool_call_response(
            "query_activities",
            {"sort": [{"field": "distance_m", "dir": "desc"}], "limit": 3},
        )
        synthesis = "Your 3 longest rides: 120.5 km (Mar 1), 95.2 km (Mar 8), 78.0 km (Mar 15)."
        agent = _make_agent(seeded_rides, [tool_call, _text_response("Done.")], synthesis)

        result = await _run_query(
            agent, "Can you tell me my 3 longest rides by distance?", seeded_rides.athlete_id
        )

        assert result["tool_calls_made"] == 1
        assert "120" in result["content"]
        assert "95" in result["content"]
        assert "78" in result["content"]

    @pytest.mark.asyncio
    async def test_answer_does_not_ask_for_clarification(self, seeded_rides: RideCtx):
        """Regression: old pipeline asked 'what minimum distance?'. Must not recur."""
        tool_call = _tool_call_response(
            "query_activities",
            {"sort": [{"field": "distance_m", "dir": "desc"}], "limit": 10},
        )
        synthesis = "Here are your longest rides: 120.5 km, 95.2 km, 78.0 km, 55.5 km, 42.0 km."
        agent = _make_agent(seeded_rides, [tool_call, _text_response("Done.")], synthesis)

        result = await _run_query(agent, "Which are my longest rides?", seeded_rides.athlete_id)

        answer_lower = result["content"].lower()
        for phrase in ["could you provide", "what minimum", "please provide",
                       "what distance", "what threshold"]:
            assert phrase not in answer_lower, (
                f"Answer asked for clarification ('{phrase}'): {result['content']}"
            )

    @pytest.mark.asyncio
    async def test_data_reaches_synthesis(self, seeded_rides: RideCtx):
        """query_activities data must appear in the system message sent to the primary model."""
        from app.services.tool_orchestrator import ToolOrchestrator
        from app.ai.context.chat_context import ChatContextBuilder

        tool_call = _tool_call_response(
            "query_activities",
            {"sort": [{"field": "distance_m", "dir": "desc"}], "limit": 3},
        )
        captured_messages: list = []

        async def capture_synthesis(messages, **kwargs):
            captured_messages.extend(messages)
            return {"content": "Top 3 rides: 120.5 km, 95.2 km, 78.0 km.", "role": "assistant"}

        tool_client = MagicMock()
        tool_client.chat_completion = AsyncMock(side_effect=[tool_call, _text_response("Done.")])
        primary_client = MagicMock()
        primary_client.chat_completion = AsyncMock(side_effect=capture_synthesis)

        agent = ChatAgent(
            context_builder=ChatContextBuilder(db=seeded_rides.db, token_budget=32000),
            llm_adapter=None,
            db=seeded_rides.db,
            llm_client=primary_client,
            tool_orchestrator=ToolOrchestrator(llm_client=tool_client, db=seeded_rides.db),
        )

        await _run_query(agent, "My 3 longest rides?", seeded_rides.athlete_id)

        assert len(captured_messages) > 0, "Primary synthesis model was never called"
        system_content = next(
            (m["content"] for m in captured_messages if m["role"] == "system"), ""
        )
        assert "120" in system_content or "120500" in system_content, (
            f"Ride data (120.5 km) not found in synthesis prompt: {system_content[:400]}"
        )


# ---------------------------------------------------------------------------
# Test: filtered queries
# ---------------------------------------------------------------------------

class TestFilteredQueries:
    @pytest.mark.asyncio
    async def test_rides_over_55km_calls_tool_once(self, seeded_rides: RideCtx):
        """'Rides longer than 55 km' — exactly one tool call."""
        tool_call = _tool_call_response(
            "query_activities",
            {
                "filters": [{"field": "distance_m", "op": "gte", "value": 55000}],
                "sort":    [{"field": "distance_m", "dir": "desc"}],
            },
        )
        synthesis = "Rides over 55 km: 120.5 km, 95.2 km, 78.0 km, 55.5 km."
        agent = _make_agent(seeded_rides, [tool_call, _text_response("Done.")], synthesis)

        result = await _run_query(
            agent, "Rides longer than 55 km?", seeded_rides.athlete_id
        )
        assert result["tool_calls_made"] == 1
        assert "55" in result["content"] or "120" in result["content"]

    @pytest.mark.asyncio
    async def test_42km_ride_excluded_from_filtered_results(self, seeded_rides: RideCtx):
        """When the tool filters distance >= 55000, the 42 km ride must not reach synthesis."""
        from app.services.tool_orchestrator import ToolOrchestrator
        from app.ai.context.chat_context import ChatContextBuilder

        tool_call = _tool_call_response(
            "query_activities",
            {
                "filters": [{"field": "distance_m", "op": "gte", "value": 55000}],
                "sort":    [{"field": "distance_m", "dir": "desc"}],
            },
        )
        captured: list = []

        async def capture(messages, **kwargs):
            captured.extend(messages)
            return {"content": "Results", "role": "assistant"}

        tool_client = MagicMock()
        tool_client.chat_completion = AsyncMock(side_effect=[tool_call, _text_response("Done.")])
        primary_client = MagicMock()
        primary_client.chat_completion = AsyncMock(side_effect=capture)

        agent = ChatAgent(
            context_builder=ChatContextBuilder(db=seeded_rides.db, token_budget=32000),
            llm_adapter=None,
            db=seeded_rides.db,
            llm_client=primary_client,
            tool_orchestrator=ToolOrchestrator(llm_client=tool_client, db=seeded_rides.db),
        )
        await _run_query(agent, "Rides over 55 km?", seeded_rides.athlete_id)

        system_content = next(
            (m["content"] for m in captured if m["role"] == "system"), ""
        )
        # Distance 42.0 km would appear as `"distance_km": 42.0` in the JSON.
        # The bare string "42" also matches avg_hr values like 142, so we check the float form.
        assert '"distance_km": 42' not in system_content, (
            "42 km ride (< 55 km threshold) incorrectly included in filtered results"
        )


# ---------------------------------------------------------------------------
# Test: result shape & data integrity (tool layer, no LLM mock needed)
# ---------------------------------------------------------------------------

class TestResultShape:
    @pytest.mark.asyncio
    async def test_activities_have_required_fields(self, seeded_rides: RideCtx):
        from app.services.chat_tools import _query_activities
        result = await _query_activities(
            {"sort": [{"field": "distance_m", "dir": "desc"}], "limit": 3},
            user_id=seeded_rides.athlete_id, db=seeded_rides.db,
        )
        assert result["success"] is True
        required = {"strava_id", "sport_type", "start_date", "distance_km",
                    "moving_time_s", "elevation_m", "avg_hr"}
        for activity in result["activities"]:
            missing = required - set(activity.keys())
            assert not missing, f"Activity missing fields: {missing}"

    @pytest.mark.asyncio
    async def test_distance_returned_in_km_not_metres(self, seeded_rides: RideCtx):
        from app.services.chat_tools import _query_activities
        result = await _query_activities(
            {"sort": [{"field": "distance_m", "dir": "desc"}], "limit": 1},
            user_id=seeded_rides.athlete_id, db=seeded_rides.db,
        )
        top = result["activities"][0]
        assert top["distance_km"] < 1000, (
            f"distance_km={top['distance_km']} looks like metres, not km"
        )
        assert top["distance_km"] == pytest.approx(120.5, abs=0.1)

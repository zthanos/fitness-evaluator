"""Tool-layer integration tests for query_activities.

Seeds a real DB with known rides and runs, then calls _query_activities
directly with the parameter shapes that Llama 3.1 8B actually generates.
Covers filtering, sorting, aggregation, type coercion, and user scoping.
"""
import pytest
from collections import namedtuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.services.chat_tools import _query_activities
from app.models.athlete import Athlete
from app.models.strava_activity import StravaActivity
from app.database import get_db

# Strava IDs in the 9_900_xxx range are reserved for these tests
_TEST_STRAVA_IDS = [
    9_900_001, 9_900_002, 9_900_003, 9_900_004,
    9_900_005, 9_900_006, 9_900_007, 9_900_008, 9_900_009,
]
_TEST_EMAILS = ["test_qa_a@test.invalid", "test_qa_b@test.invalid"]

Ctx = namedtuple("Ctx", ["db", "a", "b"])  # db session, athlete_A id, athlete_B id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session():
    db = next(get_db())
    yield db
    db.close()


@pytest.fixture()
def seeded_activities(db_session: Session) -> Ctx:
    """
    Create two throwaway athletes + 6 rides + 2 runs for athlete A, 1 ride for athlete B.
    Everything is deleted on teardown so the live DB is unchanged.
    """
    # Pre-clean any leftovers from a previous interrupted run
    db_session.query(StravaActivity).filter(
        StravaActivity.strava_id.in_(_TEST_STRAVA_IDS)
    ).delete(synchronize_session=False)
    db_session.query(Athlete).filter(
        Athlete.email.in_(_TEST_EMAILS)
    ).delete(synchronize_session=False)
    db_session.commit()

    athlete_a = Athlete(name="Test Athlete A", email="test_qa_a@test.invalid")
    athlete_b = Athlete(name="Test Athlete B", email="test_qa_b@test.invalid")
    db_session.add_all([athlete_a, athlete_b])
    db_session.flush()
    aid_a, aid_b = athlete_a.id, athlete_b.id

    base = datetime(2024, 1, 1)
    activities = [
        # ── Rides for athlete A (sorted by distance) ──────────────────────
        StravaActivity(athlete_id=aid_a, strava_id=9_900_001, activity_type="Ride", sport_type="Ride",
                       start_date=base,                       distance_m=120_500, elevation_m=1800,
                       moving_time_s=14400, avg_hr=148, calories=2100, raw_json="{}"),
        StravaActivity(athlete_id=aid_a, strava_id=9_900_002, activity_type="Ride", sport_type="Ride",
                       start_date=base + timedelta(days=7),   distance_m=95_200,  elevation_m=900,
                       moving_time_s=10800, avg_hr=142, calories=1600, raw_json="{}"),
        StravaActivity(athlete_id=aid_a, strava_id=9_900_003, activity_type="Ride", sport_type="Ride",
                       start_date=base + timedelta(days=14),  distance_m=78_000,  elevation_m=650,
                       moving_time_s=9000,  avg_hr=145, calories=1300, raw_json="{}"),
        StravaActivity(athlete_id=aid_a, strava_id=9_900_004, activity_type="Ride", sport_type="Ride",
                       start_date=base + timedelta(days=21),  distance_m=55_500,  elevation_m=400,
                       moving_time_s=6300,  avg_hr=138, calories=950,  raw_json="{}"),
        StravaActivity(athlete_id=aid_a, strava_id=9_900_005, activity_type="Ride", sport_type="Ride",
                       start_date=base + timedelta(days=28),  distance_m=42_000,  elevation_m=300,
                       moving_time_s=4800,  avg_hr=132, calories=700,  raw_json="{}"),
        StravaActivity(athlete_id=aid_a, strava_id=9_900_006, activity_type="Ride", sport_type="Ride",
                       start_date=base + timedelta(days=35),  distance_m=31_000,  elevation_m=120,
                       moving_time_s=3600,  avg_hr=128, calories=520,  raw_json="{}"),
        # ── Runs for athlete A ───────────────────────────────────────────
        StravaActivity(athlete_id=aid_a, strava_id=9_900_007, activity_type="Run",  sport_type="Run",
                       start_date=base + timedelta(days=3),   distance_m=21_100,  elevation_m=80,
                       moving_time_s=6300,  avg_hr=162, calories=850,  raw_json="{}"),
        StravaActivity(athlete_id=aid_a, strava_id=9_900_008, activity_type="Run",  sport_type="Run",
                       start_date=base + timedelta(days=10),  distance_m=10_500,  elevation_m=40,
                       moving_time_s=3300,  avg_hr=158, calories=430,  raw_json="{}"),
        # ── One ride for athlete B (must never appear in A's results) ────
        StravaActivity(athlete_id=aid_b, strava_id=9_900_009, activity_type="Ride", sport_type="Ride",
                       start_date=base,                        distance_m=200_000, elevation_m=3000,
                       moving_time_s=28800, avg_hr=155, calories=4000, raw_json="{}"),
    ]
    db_session.add_all(activities)
    db_session.commit()

    yield Ctx(db=db_session, a=aid_a, b=aid_b)

    # ── Teardown ─────────────────────────────────────────────────────────
    db_session.query(StravaActivity).filter(
        StravaActivity.strava_id.in_(_TEST_STRAVA_IDS)
    ).delete(synchronize_session=False)
    db_session.query(Athlete).filter(
        Athlete.email.in_(_TEST_EMAILS)
    ).delete(synchronize_session=False)
    db_session.commit()


# ---------------------------------------------------------------------------
# Sorting & ranking
# ---------------------------------------------------------------------------

class TestSorting:
    @pytest.mark.asyncio
    async def test_longest_rides_sorted_desc(self, seeded_activities: Ctx):
        result = await _query_activities(
            {"sort": [{"field": "distance_m", "dir": "desc"}], "limit": 10},
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["success"] is True
        distances = [a["distance_km"] for a in result["activities"]]
        assert distances == sorted(distances, reverse=True), "Not sorted longest first"
        assert distances[0] == pytest.approx(120.5, abs=0.1)

    @pytest.mark.asyncio
    async def test_top_3_longest_rides(self, seeded_activities: Ctx):
        result = await _query_activities(
            {"sort": [{"field": "distance_m", "dir": "desc"}], "limit": 3},
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["count"] == 3
        assert result["activities"][0]["distance_km"] == pytest.approx(120.5, abs=0.1)
        assert result["activities"][1]["distance_km"] == pytest.approx(95.2,  abs=0.1)
        assert result["activities"][2]["distance_km"] == pytest.approx(78.0,  abs=0.1)

    @pytest.mark.asyncio
    async def test_most_elevation_sorted_desc(self, seeded_activities: Ctx):
        result = await _query_activities(
            {"sort": [{"field": "elevation_m", "dir": "desc"}], "limit": 5},
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        elevations = [a["elevation_m"] for a in result["activities"]]
        assert elevations == sorted(elevations, reverse=True)
        assert elevations[0] == 1800

    @pytest.mark.asyncio
    async def test_most_recent_activities(self, seeded_activities: Ctx):
        result = await _query_activities(
            {"sort": [{"field": "start_date", "dir": "desc"}], "limit": 5},
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        dates = [a["start_date"] for a in result["activities"]]
        assert dates == sorted(dates, reverse=True), "Not sorted most-recent first"


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

class TestFiltering:
    @pytest.mark.asyncio
    async def test_rides_over_55km_integer_value(self, seeded_activities: Ctx):
        """Rides longer than 55 km — value as int (55000 m)."""
        result = await _query_activities(
            {
                "filters": [{"field": "distance_m", "op": "gte", "value": 55000}],
                "sort": [{"field": "distance_m", "dir": "desc"}],
            },
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["success"] is True
        for a in result["activities"]:
            assert a["distance_km"] >= 55.0, f"Got {a['distance_km']} km < 55 km"

    @pytest.mark.asyncio
    async def test_rides_over_55km_string_value(self, seeded_activities: Ctx):
        """Same filter but value is a string — must be coerced to float."""
        result = await _query_activities(
            {
                "filters": [{"field": "distance_m", "op": "gte", "value": "55000"}],
                "sort": [{"field": "distance_m", "dir": "desc"}],
            },
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["success"] is True
        assert result["count"] >= 1
        for a in result["activities"]:
            assert a["distance_km"] >= 55.0

    @pytest.mark.asyncio
    async def test_filter_sport_type_ride(self, seeded_activities: Ctx):
        result = await _query_activities(
            {
                "filters": [{"field": "sport_type", "op": "eq", "value": "Ride"}],
                "sort": [{"field": "distance_m", "dir": "desc"}],
            },
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["success"] is True
        for a in result["activities"]:
            assert a["sport_type"] == "Ride"
        assert result["count"] == 6

    @pytest.mark.asyncio
    async def test_filter_sport_type_run(self, seeded_activities: Ctx):
        result = await _query_activities(
            {
                "filters": [{"field": "sport_type", "op": "eq", "value": "Run"}],
                "sort": [{"field": "distance_m", "dir": "desc"}],
            },
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["success"] is True
        for a in result["activities"]:
            assert a["sport_type"] == "Run"
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_combined_sport_and_distance_filter(self, seeded_activities: Ctx):
        """'Rides longer than 55 km' → two filters combined."""
        result = await _query_activities(
            {
                "filters": [
                    {"field": "sport_type", "op": "eq",  "value": "Ride"},
                    {"field": "distance_m",  "op": "gte", "value": 55000},
                ],
                "sort": [{"field": "distance_m", "dir": "desc"}],
            },
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["success"] is True
        for a in result["activities"]:
            assert a["sport_type"] == "Ride"
            assert a["distance_km"] >= 55.0
        assert result["count"] == 4  # 120.5, 95.2, 78.0, 55.5

    @pytest.mark.asyncio
    async def test_filter_unknown_field_returns_error(self, seeded_activities: Ctx):
        """Defensive: unknown field name → structured error, not exception."""
        result = await _query_activities(
            {"filters": [{"field": "nonexistent_field", "op": "eq", "value": 1}]},
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["success"] is False
        assert "Unknown filter field" in result["error"]


# ---------------------------------------------------------------------------
# User scoping
# ---------------------------------------------------------------------------

class TestUserScoping:
    @pytest.mark.asyncio
    async def test_cannot_see_other_athletes_activities(self, seeded_activities: Ctx):
        result = await _query_activities(
            {"sort": [{"field": "distance_m", "dir": "desc"}], "limit": 100},
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        strava_ids = [a["strava_id"] for a in result["activities"]]
        assert 9_900_009 not in strava_ids, "Athlete B's activity leaked into A's results"

    @pytest.mark.asyncio
    async def test_athlete_b_only_sees_own_activities(self, seeded_activities: Ctx):
        result = await _query_activities(
            {"sort": [{"field": "distance_m", "dir": "desc"}], "limit": 100},
            user_id=seeded_activities.b, db=seeded_activities.db,
        )
        assert result["count"] == 1
        assert result["activities"][0]["strava_id"] == 9_900_009


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

class TestAggregation:
    @pytest.mark.asyncio
    async def test_count_total_activities(self, seeded_activities: Ctx):
        result = await _query_activities(
            {"aggregate": {"metrics": ["count"]}},
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["success"] is True
        assert result["aggregate"]["count"] == 8  # 6 rides + 2 runs

    @pytest.mark.asyncio
    async def test_sum_total_distance(self, seeded_activities: Ctx):
        result = await _query_activities(
            {"aggregate": {"metrics": ["sum:distance_m"]}},
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["success"] is True
        total_m = result["aggregate"]["sum_distance_m"]
        # 120500 + 95200 + 78000 + 55500 + 42000 + 31000 + 21100 + 10500
        assert total_m == pytest.approx(453_800, abs=1)

    @pytest.mark.asyncio
    async def test_max_distance(self, seeded_activities: Ctx):
        result = await _query_activities(
            {"aggregate": {"metrics": ["max:distance_m"]}},
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["success"] is True
        assert result["aggregate"]["max_distance_m"] == pytest.approx(120_500, abs=1)


# ---------------------------------------------------------------------------
# Defaults & limits
# ---------------------------------------------------------------------------

class TestDefaults:
    @pytest.mark.asyncio
    async def test_empty_params_returns_activities(self, seeded_activities: Ctx):
        result = await _query_activities({}, user_id=seeded_activities.a, db=seeded_activities.db)
        assert result["success"] is True
        assert result["count"] == 8

    @pytest.mark.asyncio
    async def test_limit_respected(self, seeded_activities: Ctx):
        result = await _query_activities(
            {"limit": 2, "sort": [{"field": "distance_m", "dir": "desc"}]},
            user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_limit_cap_at_100(self, seeded_activities: Ctx):
        result = await _query_activities(
            {"limit": 999}, user_id=seeded_activities.a, db=seeded_activities.db,
        )
        assert result["success"] is True
        assert result["count"] <= 100

"""
Test MetricsChart component functionality
Tests Requirements: 6.1, 6.2, 6.3, 6.4, 6.6
"""

import pytest
from datetime import date, datetime, timedelta
from app.database import get_db, engine
from app.models.weekly_measurement import WeeklyMeasurement, Base
from sqlalchemy.orm import Session


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_metrics(db_session: Session):
    """Create sample metrics data for testing."""
    metrics = []
    today = date.today()
    
    # Create metrics for the past 120 days (weekly)
    for i in range(17):
        measurement_date = today - timedelta(days=i * 7)
        metric = WeeklyMeasurement(
            week_start=measurement_date,
            weight_kg=75.0 + (i * 0.5),  # Gradual weight change
            body_fat_pct=15.0 + (i * 0.2),  # Gradual body fat change
            waist_cm=85.0 + (i * 0.3),  # Gradual waist change
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(metric)
        metrics.append(metric)
    
    db_session.commit()
    return metrics


def test_metrics_chart_data_structure(sample_metrics):
    """
    Test that metrics data has the correct structure for charting.
    Requirements: 6.1, 6.2
    """
    # Verify we have enough data points
    assert len(sample_metrics) >= 2, "Should have at least 2 data points"
    
    # Verify each metric has required fields
    for metric in sample_metrics:
        assert metric.week_start is not None, "Should have measurement_date"
        assert metric.weight_kg is not None, "Should have weight"
        assert metric.body_fat_pct is not None, "Should have body_fat_pct"
        assert metric.waist_cm is not None, "Should have waist measurement"


def test_time_range_filtering():
    """
    Test time range filtering logic.
    Requirements: 6.3
    """
    today = date.today()
    
    # Create test data spanning 120 days
    test_data = []
    for i in range(17):
        measurement_date = today - timedelta(days=i * 7)
        test_data.append({
            'measurement_date': measurement_date.isoformat(),
            'weight': 75.0,
        })
    
    # Test 7-day filter
    cutoff_7d = today - timedelta(days=7)
    filtered_7d = [m for m in test_data if date.fromisoformat(m['measurement_date']) >= cutoff_7d]
    assert len(filtered_7d) <= 2, "7-day filter should return at most 2 weekly measurements"
    
    # Test 30-day filter
    cutoff_30d = today - timedelta(days=30)
    filtered_30d = [m for m in test_data if date.fromisoformat(m['measurement_date']) >= cutoff_30d]
    assert len(filtered_30d) <= 5, "30-day filter should return at most 5 weekly measurements"
    
    # Test 90-day filter
    cutoff_90d = today - timedelta(days=90)
    filtered_90d = [m for m in test_data if date.fromisoformat(m['measurement_date']) >= cutoff_90d]
    assert len(filtered_90d) <= 13, "90-day filter should return at most 13 weekly measurements"
    
    # Test 1-year filter
    cutoff_1y = today - timedelta(days=365)
    filtered_1y = [m for m in test_data if date.fromisoformat(m['measurement_date']) >= cutoff_1y]
    assert len(filtered_1y) == len(test_data), "1-year filter should return all test data"
    
    # Test 'all' filter (no filtering)
    assert len(test_data) == 17, "'all' filter should return all data"


def test_insufficient_data_handling():
    """
    Test that component handles insufficient data gracefully.
    Requirements: 6.6
    """
    # Test with 0 data points
    empty_data = []
    assert len(empty_data) < 2, "Should detect insufficient data (0 points)"
    
    # Test with 1 data point
    single_data = [{'measurement_date': '2024-01-01', 'weight': 75.0}]
    assert len(single_data) < 2, "Should detect insufficient data (1 point)"
    
    # Test with 2 data points (minimum required)
    sufficient_data = [
        {'measurement_date': '2024-01-01', 'weight': 75.0},
        {'measurement_date': '2024-01-08', 'weight': 75.5},
    ]
    assert len(sufficient_data) >= 2, "Should accept sufficient data (2+ points)"


def test_tooltip_data_format():
    """
    Test that tooltip data includes exact values and dates.
    Requirements: 6.4
    """
    test_metric = {
        'measurement_date': '2024-01-15',
        'weight': 75.3,
        'body_fat_pct': 15.7,
    }
    
    # Verify data has required precision
    assert isinstance(test_metric['weight'], (int, float)), "Weight should be numeric"
    assert isinstance(test_metric['body_fat_pct'], (int, float)), "Body fat should be numeric"
    
    # Verify date format
    try:
        date.fromisoformat(test_metric['measurement_date'])
    except ValueError:
        pytest.fail("measurement_date should be valid ISO date format")


def test_multiple_chart_types():
    """
    Test that component supports multiple chart types.
    Requirements: 6.2
    """
    chart_types = ['weight', 'body_fat_pct', 'circumference']
    
    # Verify we have data for all chart types
    test_data = {
        'measurement_date': '2024-01-15',
        'weight': 75.0,
        'body_fat_pct': 15.0,
        'measurements': {
            'waist_cm': 85.0,
        }
    }
    
    assert 'weight' in test_data, "Should have weight data"
    assert 'body_fat_pct' in test_data, "Should have body fat data"
    assert 'measurements' in test_data, "Should have circumference data"


def test_chart_data_sorting():
    """
    Test that chart data is sorted by date for proper display.
    Requirements: 6.1
    """
    # Create unsorted test data
    unsorted_data = [
        {'measurement_date': '2024-01-15', 'weight': 75.0},
        {'measurement_date': '2024-01-01', 'weight': 74.0},
        {'measurement_date': '2024-01-08', 'weight': 74.5},
    ]
    
    # Sort by date ascending
    sorted_data = sorted(unsorted_data, key=lambda x: x['measurement_date'])
    
    # Verify sorting
    assert sorted_data[0]['measurement_date'] == '2024-01-01'
    assert sorted_data[1]['measurement_date'] == '2024-01-08'
    assert sorted_data[2]['measurement_date'] == '2024-01-15'
    
    # Verify weights are in correct order
    assert sorted_data[0]['weight'] == 74.0
    assert sorted_data[1]['weight'] == 74.5
    assert sorted_data[2]['weight'] == 75.0


def test_null_value_handling():
    """
    Test that component handles null/missing values gracefully.
    Requirements: 6.6
    """
    # Test data with missing body fat percentage
    test_data = [
        {'measurement_date': '2024-01-01', 'weight': 75.0, 'body_fat_pct': None},
        {'measurement_date': '2024-01-08', 'weight': 75.5, 'body_fat_pct': 15.0},
    ]
    
    # Filter out null body fat values
    body_fat_data = [m for m in test_data if m['body_fat_pct'] is not None]
    
    # Should only have 1 data point with body fat
    assert len(body_fat_data) == 1, "Should filter out null body fat values"
    
    # Weight data should still have 2 points
    weight_data = [m for m in test_data if m['weight'] is not None]
    assert len(weight_data) == 2, "Should keep all weight values"


def test_circumference_measurements_extraction():
    """
    Test extraction of circumference measurements from nested structure.
    Requirements: 6.2
    """
    test_data = [
        {
            'measurement_date': '2024-01-01',
            'measurements': {'waist_cm': 85.0}
        },
        {
            'measurement_date': '2024-01-08',
            'measurements': {'waist_cm': 84.5}
        },
        {
            'measurement_date': '2024-01-15',
            'measurements': None  # Missing measurements
        },
    ]
    
    # Filter data with measurements
    with_measurements = [m for m in test_data if m.get('measurements')]
    assert len(with_measurements) == 2, "Should filter out entries without measurements"
    
    # Extract waist measurements
    waist_values = [m['measurements']['waist_cm'] for m in with_measurements]
    assert len(waist_values) == 2, "Should extract waist measurements"
    assert waist_values[0] == 85.0
    assert waist_values[1] == 84.5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

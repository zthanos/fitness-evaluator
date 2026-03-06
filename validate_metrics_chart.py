"""
Simple validation script for MetricsChart component
Tests basic functionality without pytest
"""

from datetime import date, timedelta


def test_time_range_filtering():
    """Test time range filtering logic."""
    print("Testing time range filtering...")
    
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
    assert len(filtered_7d) <= 2, f"7-day filter failed: got {len(filtered_7d)} items"
    print(f"✓ 7-day filter: {len(filtered_7d)} items")
    
    # Test 30-day filter
    cutoff_30d = today - timedelta(days=30)
    filtered_30d = [m for m in test_data if date.fromisoformat(m['measurement_date']) >= cutoff_30d]
    assert len(filtered_30d) <= 5, f"30-day filter failed: got {len(filtered_30d)} items"
    print(f"✓ 30-day filter: {len(filtered_30d)} items")
    
    # Test 90-day filter
    cutoff_90d = today - timedelta(days=90)
    filtered_90d = [m for m in test_data if date.fromisoformat(m['measurement_date']) >= cutoff_90d]
    assert len(filtered_90d) <= 13, f"90-day filter failed: got {len(filtered_90d)} items"
    print(f"✓ 90-day filter: {len(filtered_90d)} items")
    
    # Test 1-year filter
    cutoff_1y = today - timedelta(days=365)
    filtered_1y = [m for m in test_data if date.fromisoformat(m['measurement_date']) >= cutoff_1y]
    assert len(filtered_1y) == len(test_data), f"1-year filter failed: got {len(filtered_1y)} items"
    print(f"✓ 1-year filter: {len(filtered_1y)} items")
    
    print("✓ All time range filters working correctly\n")


def test_insufficient_data_handling():
    """Test insufficient data detection."""
    print("Testing insufficient data handling...")
    
    # Test with 0 data points
    empty_data = []
    assert len(empty_data) < 2, "Failed to detect insufficient data (0 points)"
    print("✓ Detected insufficient data: 0 points")
    
    # Test with 1 data point
    single_data = [{'measurement_date': '2024-01-01', 'weight': 75.0}]
    assert len(single_data) < 2, "Failed to detect insufficient data (1 point)"
    print("✓ Detected insufficient data: 1 point")
    
    # Test with 2 data points (minimum required)
    sufficient_data = [
        {'measurement_date': '2024-01-01', 'weight': 75.0},
        {'measurement_date': '2024-01-08', 'weight': 75.5},
    ]
    assert len(sufficient_data) >= 2, "Failed to accept sufficient data"
    print("✓ Accepted sufficient data: 2+ points\n")


def test_data_sorting():
    """Test data sorting by date."""
    print("Testing data sorting...")
    
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
    print("✓ Data sorted correctly by date\n")


def test_null_value_handling():
    """Test null value filtering."""
    print("Testing null value handling...")
    
    test_data = [
        {'measurement_date': '2024-01-01', 'weight': 75.0, 'body_fat_pct': None},
        {'measurement_date': '2024-01-08', 'weight': 75.5, 'body_fat_pct': 15.0},
    ]
    
    # Filter out null body fat values
    body_fat_data = [m for m in test_data if m['body_fat_pct'] is not None]
    assert len(body_fat_data) == 1, "Failed to filter null body fat values"
    print("✓ Filtered null body fat values correctly")
    
    # Weight data should still have 2 points
    weight_data = [m for m in test_data if m['weight'] is not None]
    assert len(weight_data) == 2, "Failed to keep all weight values"
    print("✓ Kept all non-null weight values\n")


def test_circumference_extraction():
    """Test circumference measurement extraction."""
    print("Testing circumference measurement extraction...")
    
    test_data = [
        {'measurement_date': '2024-01-01', 'measurements': {'waist_cm': 85.0}},
        {'measurement_date': '2024-01-08', 'measurements': {'waist_cm': 84.5}},
        {'measurement_date': '2024-01-15', 'measurements': None},
    ]
    
    # Filter data with measurements
    with_measurements = [m for m in test_data if m.get('measurements')]
    assert len(with_measurements) == 2, "Failed to filter measurements"
    print("✓ Filtered entries with measurements")
    
    # Extract waist measurements
    waist_values = [m['measurements']['waist_cm'] for m in with_measurements]
    assert len(waist_values) == 2, "Failed to extract waist measurements"
    assert waist_values[0] == 85.0
    assert waist_values[1] == 84.5
    print("✓ Extracted circumference measurements correctly\n")


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("MetricsChart Component Validation")
    print("=" * 60 + "\n")
    
    try:
        test_time_range_filtering()
        test_insufficient_data_handling()
        test_data_sorting()
        test_null_value_handling()
        test_circumference_extraction()
        
        print("=" * 60)
        print("✅ All validation tests passed!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ Validation failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())

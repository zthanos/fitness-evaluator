"""
Test metrics form validation
Tests Requirements 5.2, 5.3, 5.7
"""

from app.schemas.log_schemas import WeeklyMeasurementCreate
from pydantic import ValidationError
from datetime import date


def test_weight_validation_minimum():
    """Test that weight below 30kg is rejected (Requirement 5.2)"""
    try:
        WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=29.9  # Below minimum
        )
        print("❌ Weight minimum validation FAILED - should have raised error")
        return False
    except ValidationError as e:
        errors = e.errors()
        if any('weight_kg' in str(error) for error in errors):
            print("✅ Weight minimum validation works")
            return True
        else:
            print("❌ Weight minimum validation FAILED - wrong error")
            return False


def test_weight_validation_maximum():
    """Test that weight above 300kg is rejected (Requirement 5.2)"""
    try:
        WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=300.1  # Above maximum
        )
        print("❌ Weight maximum validation FAILED - should have raised error")
        return False
    except ValidationError as e:
        errors = e.errors()
        if any('weight_kg' in str(error) for error in errors):
            print("✅ Weight maximum validation works")
            return True
        else:
            print("❌ Weight maximum validation FAILED - wrong error")
            return False


def test_weight_validation_valid():
    """Test that valid weight is accepted (Requirement 5.2)"""
    try:
        measurement = WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=75.5  # Valid weight
        )
        if measurement.weight_kg == 75.5:
            print("✅ Valid weight accepted")
            return True
        else:
            print("❌ Valid weight test FAILED")
            return False
    except ValidationError as e:
        print(f"❌ Valid weight test FAILED - unexpected error: {e}")
        return False


def test_body_fat_validation_minimum():
    """Test that body fat below 3% is rejected (Requirement 5.3)"""
    try:
        WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=75.0,
            body_fat_pct=2.9  # Below minimum
        )
        print("❌ Body fat minimum validation FAILED - should have raised error")
        return False
    except ValidationError as e:
        errors = e.errors()
        if any('body_fat_pct' in str(error) for error in errors):
            print("✅ Body fat minimum validation works")
            return True
        else:
            print("❌ Body fat minimum validation FAILED - wrong error")
            return False


def test_body_fat_validation_maximum():
    """Test that body fat above 60% is rejected (Requirement 5.3)"""
    try:
        WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=75.0,
            body_fat_pct=60.1  # Above maximum
        )
        print("❌ Body fat maximum validation FAILED - should have raised error")
        return False
    except ValidationError as e:
        errors = e.errors()
        if any('body_fat_pct' in str(error) for error in errors):
            print("✅ Body fat maximum validation works")
            return True
        else:
            print("❌ Body fat maximum validation FAILED - wrong error")
            return False


def test_body_fat_validation_valid():
    """Test that valid body fat is accepted (Requirement 5.3)"""
    try:
        measurement = WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=75.0,
            body_fat_pct=15.5  # Valid body fat
        )
        if measurement.body_fat_pct == 15.5:
            print("✅ Valid body fat accepted")
            return True
        else:
            print("❌ Valid body fat test FAILED")
            return False
    except ValidationError as e:
        print(f"❌ Valid body fat test FAILED - unexpected error: {e}")
        return False


def test_edge_case_weight_30kg():
    """Test edge case: exactly 30kg should be valid"""
    try:
        measurement = WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=30.0
        )
        if measurement.weight_kg == 30.0:
            print("✅ Edge case: 30kg accepted")
            return True
        else:
            print("❌ Edge case 30kg FAILED")
            return False
    except ValidationError as e:
        print(f"❌ Edge case 30kg FAILED - unexpected error: {e}")
        return False


def test_edge_case_weight_300kg():
    """Test edge case: exactly 300kg should be valid"""
    try:
        measurement = WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=300.0
        )
        if measurement.weight_kg == 300.0:
            print("✅ Edge case: 300kg accepted")
            return True
        else:
            print("❌ Edge case 300kg FAILED")
            return False
    except ValidationError as e:
        print(f"❌ Edge case 300kg FAILED - unexpected error: {e}")
        return False


def test_edge_case_body_fat_3_percent():
    """Test edge case: exactly 3% should be valid"""
    try:
        measurement = WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=75.0,
            body_fat_pct=3.0
        )
        if measurement.body_fat_pct == 3.0:
            print("✅ Edge case: 3% body fat accepted")
            return True
        else:
            print("❌ Edge case 3% FAILED")
            return False
    except ValidationError as e:
        print(f"❌ Edge case 3% FAILED - unexpected error: {e}")
        return False


def test_edge_case_body_fat_60_percent():
    """Test edge case: exactly 60% should be valid"""
    try:
        measurement = WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=75.0,
            body_fat_pct=60.0
        )
        if measurement.body_fat_pct == 60.0:
            print("✅ Edge case: 60% body fat accepted")
            return True
        else:
            print("❌ Edge case 60% FAILED")
            return False
    except ValidationError as e:
        print(f"❌ Edge case 60% FAILED - unexpected error: {e}")
        return False


def test_optional_fields():
    """Test that optional fields work correctly"""
    try:
        measurement = WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=75.0,
            waist_cm=85.5
        )
        if (measurement.weight_kg == 75.0 and 
            measurement.waist_cm == 85.5 and 
            measurement.body_fat_pct is None):
            print("✅ Optional fields work correctly")
            return True
        else:
            print("❌ Optional fields test FAILED")
            return False
    except ValidationError as e:
        print(f"❌ Optional fields test FAILED - unexpected error: {e}")
        return False


def test_complete_measurement():
    """Test a complete measurement with all fields"""
    try:
        measurement = WeeklyMeasurementCreate(
            week_start=date.today(),
            weight_kg=75.5,
            body_fat_pct=15.5,
            waist_cm=85.0
        )
        if (measurement.weight_kg == 75.5 and 
            measurement.body_fat_pct == 15.5 and 
            measurement.waist_cm == 85.0):
            print("✅ Complete measurement accepted")
            return True
        else:
            print("❌ Complete measurement test FAILED")
            return False
    except ValidationError as e:
        print(f"❌ Complete measurement test FAILED - unexpected error: {e}")
        return False


if __name__ == "__main__":
    print("\n🧪 Testing Metrics Form Validation\n")
    print("=" * 50)
    
    # Run all tests
    results = []
    results.append(test_weight_validation_minimum())
    results.append(test_weight_validation_maximum())
    results.append(test_weight_validation_valid())
    results.append(test_body_fat_validation_minimum())
    results.append(test_body_fat_validation_maximum())
    results.append(test_body_fat_validation_valid())
    results.append(test_edge_case_weight_30kg())
    results.append(test_edge_case_weight_300kg())
    results.append(test_edge_case_body_fat_3_percent())
    results.append(test_edge_case_body_fat_60_percent())
    results.append(test_optional_fields())
    results.append(test_complete_measurement())
    
    print("=" * 50)
    
    if all(results):
        print("\n✅ All validation tests passed!\n")
    else:
        print(f"\n❌ Some tests failed: {sum(results)}/{len(results)} passed\n")

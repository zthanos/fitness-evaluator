"""Test validation for metrics schemas."""

from app.schemas.metrics_schemas import BodyMetricCreate
from pydantic import ValidationError

def test_weight_validation():
    """Test weight validation boundaries."""
    
    # Test weight too low
    try:
        metric = BodyMetricCreate(measurement_date='2024-01-15', weight=25.0)
        print("❌ FAILED: Weight < 30kg should be rejected")
        return False
    except ValidationError as e:
        print("✓ Weight < 30kg correctly rejected")
        print(f"  Error: {e.errors()[0]['msg']}")
    
    # Test weight too high
    try:
        metric = BodyMetricCreate(measurement_date='2024-01-15', weight=350.0)
        print("❌ FAILED: Weight > 300kg should be rejected")
        return False
    except ValidationError as e:
        print("✓ Weight > 300kg correctly rejected")
        print(f"  Error: {e.errors()[0]['msg']}")
    
    # Test valid weight
    try:
        metric = BodyMetricCreate(measurement_date='2024-01-15', weight=75.5)
        print("✓ Valid weight (75.5kg) accepted")
    except ValidationError as e:
        print(f"❌ FAILED: Valid weight rejected: {e}")
        return False
    
    return True

def test_body_fat_validation():
    """Test body fat percentage validation boundaries."""
    
    # Test body fat too low
    try:
        metric = BodyMetricCreate(measurement_date='2024-01-15', weight=75.0, body_fat_pct=2.0)
        print("❌ FAILED: Body fat < 3% should be rejected")
        return False
    except ValidationError as e:
        print("✓ Body fat < 3% correctly rejected")
        print(f"  Error: {e.errors()[0]['msg']}")
    
    # Test body fat too high
    try:
        metric = BodyMetricCreate(measurement_date='2024-01-15', weight=75.0, body_fat_pct=65.0)
        print("❌ FAILED: Body fat > 60% should be rejected")
        return False
    except ValidationError as e:
        print("✓ Body fat > 60% correctly rejected")
        print(f"  Error: {e.errors()[0]['msg']}")
    
    # Test valid body fat
    try:
        metric = BodyMetricCreate(measurement_date='2024-01-15', weight=75.0, body_fat_pct=18.5)
        print("✓ Valid body fat (18.5%) accepted")
    except ValidationError as e:
        print(f"❌ FAILED: Valid body fat rejected: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("Testing Metrics Schema Validation")
    print("=" * 50)
    
    print("\n1. Weight Validation Tests:")
    weight_ok = test_weight_validation()
    
    print("\n2. Body Fat Validation Tests:")
    body_fat_ok = test_body_fat_validation()
    
    print("\n" + "=" * 50)
    if weight_ok and body_fat_ok:
        print("✓ All validation tests passed!")
    else:
        print("❌ Some validation tests failed")

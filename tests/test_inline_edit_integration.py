"""Integration test for daily log inline editing functionality."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import create_app
from datetime import date, timedelta

def test_daily_log_inline_edit():
    """Test the complete inline edit workflow."""
    
    print("\n" + "=" * 60)
    print("Testing Daily Log Inline Edit Integration")
    print("=" * 60)
    
    # Create test client
    app = create_app()
    client = TestClient(app)
    
    # Test 1: Create a daily log
    print("\n1. Creating a test daily log...")
    test_date = (date.today() - timedelta(days=2)).isoformat()
    create_data = {
        "log_date": test_date,
        "calories_in": 2000,
        "protein_g": 150.0,
        "carbs_g": 200.0,
        "fat_g": 70.0,
        "adherence_score": 80,
        "notes": "Original notes"
    }
    
    response = client.post("/api/logs/daily", json=create_data)
    assert response.status_code == 200, f"Failed to create log: {response.text}"
    created_log = response.json()
    log_id = created_log["id"]
    print(f"   ✓ Created log with ID: {log_id}")
    print(f"   ✓ Original: calories={created_log['calories_in']}, protein={created_log['protein_g']}")
    
    # Test 2: Update the log (simulating inline edit)
    print("\n2. Updating log via PUT endpoint (inline edit)...")
    update_data = {
        "log_date": test_date,
        "calories_in": 2200,  # Changed
        "protein_g": 160.0,   # Changed
        "carbs_g": 200.0,
        "fat_g": 70.0,
        "adherence_score": 85,  # Changed
        "notes": "Updated via inline edit"
    }
    
    response = client.put(f"/api/logs/daily/{log_id}", json=update_data)
    assert response.status_code == 200, f"Failed to update log: {response.text}"
    updated_log = response.json()
    print(f"   ✓ Updated successfully")
    print(f"   ✓ New values: calories={updated_log['calories_in']}, protein={updated_log['protein_g']}")
    
    # Test 3: Verify changes persisted
    print("\n3. Verifying changes persisted...")
    response = client.get(f"/api/logs/daily/{test_date}")
    assert response.status_code == 200
    fetched_log = response.json()
    
    assert fetched_log['calories_in'] == 2200, "Calories not updated correctly"
    assert fetched_log['protein_g'] == 160.0, "Protein not updated correctly"
    assert fetched_log['adherence_score'] == 85, "Adherence not updated correctly"
    assert fetched_log['notes'] == "Updated via inline edit", "Notes not updated correctly"
    print("   ✓ All changes verified!")
    
    # Test 4: Test validation (Requirement 9.3)
    print("\n4. Testing validation rules...")
    
    # Test calories exceeding max
    invalid_data = update_data.copy()
    invalid_data['calories_in'] = 15000  # Exceeds 10000
    response = client.put(f"/api/logs/daily/{log_id}", json=invalid_data)
    assert response.status_code == 422, "Should reject calories > 10000"
    print("   ✓ Rejected calories > 10000")
    
    # Test protein exceeding max
    invalid_data = update_data.copy()
    invalid_data['protein_g'] = 1500  # Exceeds 1000
    response = client.put(f"/api/logs/daily/{log_id}", json=invalid_data)
    assert response.status_code == 422, "Should reject protein > 1000"
    print("   ✓ Rejected protein > 1000")
    
    # Test adherence exceeding max
    invalid_data = update_data.copy()
    invalid_data['adherence_score'] = 150  # Exceeds 100
    response = client.put(f"/api/logs/daily/{log_id}", json=invalid_data)
    assert response.status_code == 422, "Should reject adherence > 100"
    print("   ✓ Rejected adherence > 100")
    
    # Test 5: Test updating individual fields
    print("\n5. Testing individual field updates...")
    
    # Update only calories
    partial_update = {
        "log_date": test_date,
        "calories_in": 2500,
        "protein_g": 160.0,
        "carbs_g": 200.0,
        "fat_g": 70.0,
        "adherence_score": 85,
        "notes": "Updated via inline edit"
    }
    response = client.put(f"/api/logs/daily/{log_id}", json=partial_update)
    assert response.status_code == 200
    result = response.json()
    assert result['calories_in'] == 2500
    print("   ✓ Individual field update works")
    
    # Test 6: List logs and verify order (Requirement 8.7)
    print("\n6. Testing log list order (reverse chronological)...")
    
    # Create another log for tomorrow
    tomorrow = (date.today() - timedelta(days=1)).isoformat()
    response = client.post("/api/logs/daily", json={
        "log_date": tomorrow,
        "calories_in": 1800,
        "protein_g": 140.0,
        "carbs_g": 180.0,
        "fat_g": 60.0,
        "adherence_score": 90,
        "notes": "Newer log"
    })
    assert response.status_code == 200
    
    # List all logs
    response = client.get("/api/logs/daily")
    assert response.status_code == 200
    logs = response.json()
    
    # Verify reverse chronological order
    assert len(logs) >= 2
    dates = [log['log_date'] for log in logs]
    assert dates == sorted(dates, reverse=True), "Logs not in reverse chronological order"
    print("   ✓ Logs displayed in reverse chronological order")
    
    print("\n" + "=" * 60)
    print("✓ All integration tests passed!")
    print("=" * 60 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        test_daily_log_inline_edit()
        print("\n✓ SUCCESS: All tests passed!\n")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

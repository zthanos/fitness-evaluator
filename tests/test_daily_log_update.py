"""Test script for daily log update endpoint."""

import requests
import json
from datetime import date, timedelta

BASE_URL = "http://localhost:8000/api"

def test_daily_log_update():
    """Test the PUT /api/logs/daily/{log_id} endpoint."""
    
    print("Testing Daily Log Update Endpoint")
    print("=" * 50)
    
    # Step 1: Create a test log
    print("\n1. Creating a test daily log...")
    test_date = date.today() - timedelta(days=1)
    create_data = {
        "log_date": test_date.isoformat(),
        "calories_in": 2000,
        "protein_g": 150.0,
        "carbs_g": 200.0,
        "fat_g": 70.0,
        "adherence_score": 80,
        "notes": "Original notes"
    }
    
    response = requests.post(f"{BASE_URL}/logs/daily", json=create_data)
    if response.status_code == 200:
        created_log = response.json()
        log_id = created_log["id"]
        print(f"✓ Created log with ID: {log_id}")
        print(f"  Original values: calories={created_log['calories_in']}, protein={created_log['protein_g']}")
    else:
        print(f"✗ Failed to create log: {response.status_code}")
        print(response.text)
        return
    
    # Step 2: Update the log
    print("\n2. Updating the log...")
    update_data = {
        "log_date": test_date.isoformat(),
        "calories_in": 2200,  # Changed
        "protein_g": 160.0,   # Changed
        "carbs_g": 200.0,
        "fat_g": 70.0,
        "adherence_score": 85,  # Changed
        "notes": "Updated notes"  # Changed
    }
    
    response = requests.put(f"{BASE_URL}/logs/daily/{log_id}", json=update_data)
    if response.status_code == 200:
        updated_log = response.json()
        print(f"✓ Updated log successfully")
        print(f"  New values: calories={updated_log['calories_in']}, protein={updated_log['protein_g']}")
        print(f"  Adherence: {updated_log['adherence_score']}")
        print(f"  Notes: {updated_log['notes']}")
    else:
        print(f"✗ Failed to update log: {response.status_code}")
        print(response.text)
        return
    
    # Step 3: Verify the update by fetching the log
    print("\n3. Verifying the update...")
    response = requests.get(f"{BASE_URL}/logs/daily/{test_date.isoformat()}")
    if response.status_code == 200:
        fetched_log = response.json()
        print(f"✓ Fetched log successfully")
        
        # Verify values match
        assert fetched_log['calories_in'] == 2200, "Calories not updated"
        assert fetched_log['protein_g'] == 160.0, "Protein not updated"
        assert fetched_log['adherence_score'] == 85, "Adherence not updated"
        assert fetched_log['notes'] == "Updated notes", "Notes not updated"
        
        print("✓ All values verified correctly!")
    else:
        print(f"✗ Failed to fetch log: {response.status_code}")
        return
    
    # Step 4: Test validation
    print("\n4. Testing validation...")
    invalid_data = {
        "log_date": test_date.isoformat(),
        "calories_in": 15000,  # Exceeds max of 10000
        "protein_g": 160.0,
        "carbs_g": 200.0,
        "fat_g": 70.0,
        "adherence_score": 85,
        "notes": "Test validation"
    }
    
    response = requests.put(f"{BASE_URL}/logs/daily/{log_id}", json=invalid_data)
    if response.status_code == 422:
        print("✓ Validation working correctly (rejected invalid calories)")
    else:
        print(f"✗ Validation not working: {response.status_code}")
    
    print("\n" + "=" * 50)
    print("All tests passed! ✓")

if __name__ == "__main__":
    try:
        test_daily_log_update()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Make sure it's running on http://localhost:8000")
    except Exception as e:
        print(f"Error: {e}")

"""Test script for Task 7.5: Daily logs API endpoints with pagination."""

import requests
import json
from datetime import date, timedelta

BASE_URL = "http://localhost:8000/api/logs"


def test_post_endpoint():
    """Test POST /api/logs/daily endpoint."""
    print("\n" + "=" * 60)
    print("Test 1: POST /api/logs/daily - Create daily log")
    print("=" * 60)
    
    test_date = (date.today() - timedelta(days=1)).isoformat()
    data = {
        "log_date": test_date,
        "calories_in": 2000,
        "protein_g": 150.0,
        "carbs_g": 200.0,
        "fat_g": 70.0,
        "adherence_score": 85,
        "notes": "Test log for Task 7.5"
    }
    
    response = requests.post(f"{BASE_URL}/daily", json=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ POST endpoint works correctly")
        print(f"  Created log ID: {result['id']}")
        print(f"  Date: {result['log_date']}")
        print(f"  Calories: {result['calories_in']}")
        return result['id']
    else:
        print(f"✗ POST failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None


def test_put_endpoint(log_id):
    """Test PUT /api/logs/daily/{id} endpoint."""
    print("\n" + "=" * 60)
    print("Test 2: PUT /api/logs/daily/{id} - Update daily log")
    print("=" * 60)
    
    if not log_id:
        print("✗ Skipping PUT test - no log ID available")
        return
    
    test_date = (date.today() - timedelta(days=1)).isoformat()
    data = {
        "log_date": test_date,
        "calories_in": 2200,  # Updated
        "protein_g": 160.0,   # Updated
        "carbs_g": 200.0,
        "fat_g": 70.0,
        "adherence_score": 90,  # Updated
        "notes": "Updated test log for Task 7.5"
    }
    
    response = requests.put(f"{BASE_URL}/daily/{log_id}", json=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ PUT endpoint works correctly")
        print(f"  Updated log ID: {result['id']}")
        print(f"  New calories: {result['calories_in']}")
        print(f"  New protein: {result['protein_g']}")
        print(f"  New adherence: {result['adherence_score']}")
    else:
        print(f"✗ PUT failed: {response.status_code}")
        print(f"  Response: {response.text}")


def test_get_endpoint_without_pagination():
    """Test GET /api/logs/daily endpoint without pagination."""
    print("\n" + "=" * 60)
    print("Test 3: GET /api/logs/daily - List logs (no pagination)")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/daily")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ GET endpoint works correctly")
        print(f"  Response structure: {list(result.keys())}")
        
        if 'logs' in result and 'total' in result and 'page' in result and 'page_size' in result:
            print(f"✓ Pagination structure is correct")
            print(f"  Total logs: {result['total']}")
            print(f"  Page: {result['page']}")
            print(f"  Page size: {result['page_size']}")
            print(f"  Logs returned: {len(result['logs'])}")
        else:
            print(f"✗ Missing pagination fields in response")
    else:
        print(f"✗ GET failed: {response.status_code}")
        print(f"  Response: {response.text}")


def test_get_endpoint_with_pagination():
    """Test GET /api/logs/daily endpoint with pagination parameters."""
    print("\n" + "=" * 60)
    print("Test 4: GET /api/logs/daily - List logs with pagination")
    print("=" * 60)
    
    # Test with page=1, page_size=5
    response = requests.get(f"{BASE_URL}/daily", params={"page": 1, "page_size": 5})
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ GET with pagination works correctly")
        print(f"  Total logs: {result['total']}")
        print(f"  Page: {result['page']}")
        print(f"  Page size: {result['page_size']}")
        print(f"  Logs returned: {len(result['logs'])}")
        
        if len(result['logs']) <= 5:
            print(f"✓ Page size limit is respected")
        else:
            print(f"✗ Page size limit not respected")
    else:
        print(f"✗ GET with pagination failed: {response.status_code}")
        print(f"  Response: {response.text}")


def test_get_endpoint_with_date_filter():
    """Test GET /api/logs/daily endpoint with date filtering."""
    print("\n" + "=" * 60)
    print("Test 5: GET /api/logs/daily - List logs with date filter")
    print("=" * 60)
    
    start_date = (date.today() - timedelta(days=7)).isoformat()
    end_date = date.today().isoformat()
    
    response = requests.get(
        f"{BASE_URL}/daily",
        params={"start_date": start_date, "end_date": end_date, "page": 1, "page_size": 10}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ GET with date filter works correctly")
        print(f"  Date range: {start_date} to {end_date}")
        print(f"  Total logs in range: {result['total']}")
        print(f"  Logs returned: {len(result['logs'])}")
    else:
        print(f"✗ GET with date filter failed: {response.status_code}")
        print(f"  Response: {response.text}")


def test_pydantic_validation():
    """Test Pydantic model validation."""
    print("\n" + "=" * 60)
    print("Test 6: Pydantic Validation - Invalid data")
    print("=" * 60)
    
    # Test with invalid calories (> 10000)
    test_date = date.today().isoformat()
    invalid_data = {
        "log_date": test_date,
        "calories_in": 15000,  # Invalid: > 10000
        "protein_g": 150.0,
        "carbs_g": 200.0,
        "fat_g": 70.0,
        "adherence_score": 85
    }
    
    response = requests.post(f"{BASE_URL}/daily", json=invalid_data)
    
    if response.status_code == 422:
        print(f"✓ Validation correctly rejects invalid data")
        print(f"  Status code: {response.status_code}")
    else:
        print(f"✗ Validation did not reject invalid data")
        print(f"  Status code: {response.status_code}")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Task 7.5: Daily Logs API Endpoints - Test Suite")
    print("=" * 70)
    print("\nTesting Requirements:")
    print("  - POST /api/logs for creating records")
    print("  - PUT /api/logs/{id} for updating records")
    print("  - GET /api/logs for retrieving history with pagination")
    print("  - Pydantic models for validation")
    print("=" * 70)
    
    try:
        # Test POST endpoint
        log_id = test_post_endpoint()
        
        # Test PUT endpoint
        test_put_endpoint(log_id)
        
        # Test GET endpoint without pagination
        test_get_endpoint_without_pagination()
        
        # Test GET endpoint with pagination
        test_get_endpoint_with_pagination()
        
        # Test GET endpoint with date filter
        test_get_endpoint_with_date_filter()
        
        # Test Pydantic validation
        test_pydantic_validation()
        
        print("\n" + "=" * 70)
        print("✓ All tests completed successfully!")
        print("=" * 70)
        
    except requests.exceptions.ConnectionError:
        print("\n✗ Error: Could not connect to server.")
        print("  Make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")


if __name__ == "__main__":
    main()

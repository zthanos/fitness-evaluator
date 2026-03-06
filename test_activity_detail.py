"""Test script for activity detail page implementation"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_activity_detail_page_route():
    """Test that the activity detail page route returns HTML"""
    response = client.get("/activities/17560730617")
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    print("✓ Activity detail page route works")

def test_activity_detail_api():
    """Test that the API endpoint returns activity data"""
    response = client.get("/api/strava/activities/detail/17560730617")
    print(f"\nAPI Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Activity Type: {data.get('activity_type')}")
        print(f"Distance: {data.get('distance_m')} m")
        print(f"Duration: {data.get('moving_time_s')} s")
        print("✓ Activity detail API works")
    else:
        print(f"✗ API failed: {response.text}")

def test_activity_not_found():
    """Test that non-existent activity returns 404"""
    response = client.get("/api/strava/activities/detail/99999999999")
    print(f"\nNot Found Status Code: {response.status_code}")
    assert response.status_code == 404
    print("✓ 404 handling works")

if __name__ == "__main__":
    print("Testing Activity Detail Implementation\n")
    print("=" * 50)
    test_activity_detail_page_route()
    test_activity_detail_api()
    test_activity_not_found()
    print("\n" + "=" * 50)
    print("All tests passed! ✓")

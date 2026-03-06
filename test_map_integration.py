"""Test for Leaflet.js map integration (Task 4.3)"""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.strava_activity import StravaActivity
import json

client = TestClient(app)

def test_leaflet_library_included():
    """Test that Leaflet.js library is included in activity detail page"""
    print("\n1. Testing Leaflet.js library inclusion...")
    response = client.get("/activities/12345")
    content = response.text
    
    # Check for Leaflet CSS
    assert "leaflet.css" in content, "Leaflet CSS not found"
    assert "unpkg.com/leaflet@1.9.4" in content, "Leaflet CDN not found"
    
    # Check for Leaflet JS
    assert "leaflet.js" in content, "Leaflet JS not found"
    
    print("   ✓ Leaflet.js library properly included")

def test_map_container_exists():
    """Test that map container element exists"""
    print("\n2. Testing map container element...")
    response = client.get("/activities/12345")
    content = response.text
    
    assert 'id="activity-map"' in content, "Map container not found"
    assert 'id="map-section"' in content, "Map section not found"
    
    print("   ✓ Map container elements present")

def test_map_section_hidden_by_default():
    """Test that map section is hidden by default (shown only when data available)"""
    print("\n3. Testing map section visibility...")
    response = client.get("/activities/12345")
    content = response.text
    
    # Map section should have 'hidden' class initially
    assert 'id="map-section" class="card bg-base-100 shadow-xl mb-6 hidden"' in content, \
        "Map section should be hidden by default"
    
    print("   ✓ Map section properly hidden by default")

def test_activity_detail_js_has_map_methods():
    """Test that activity-detail.js contains map rendering methods"""
    print("\n4. Testing JavaScript map methods...")
    
    with open("public/js/activity-detail.js", "r") as f:
        js_content = f.read()
    
    # Check for renderMap method
    assert "renderMap()" in js_content, "renderMap method not found"
    
    # Check for decodePolyline method
    assert "decodePolyline(" in js_content, "decodePolyline method not found"
    
    # Check for Leaflet map initialization
    assert "L.map(" in js_content, "Leaflet map initialization not found"
    
    # Check for tile layer
    assert "L.tileLayer(" in js_content, "Tile layer not found"
    
    # Check for polyline rendering
    assert "L.polyline(" in js_content, "Polyline rendering not found"
    
    # Check for markers
    assert "L.circleMarker(" in js_content, "Circle markers not found"
    
    # Check for zoom and pan controls
    assert "zoomControl: true" in js_content, "Zoom control not enabled"
    assert "scrollWheelZoom: true" in js_content, "Scroll wheel zoom not enabled"
    
    print("   ✓ All required map methods present")

def test_polyline_decoder_algorithm():
    """Test that polyline decoder follows Google's algorithm"""
    print("\n5. Testing polyline decoder algorithm...")
    
    with open("public/js/activity-detail.js", "r") as f:
        js_content = f.read()
    
    # Check for key parts of the decoding algorithm
    assert "charCodeAt(index++) - 63" in js_content, "Polyline decoding algorithm incomplete"
    assert "result |= (b & 0x1f) << shift" in js_content, "Bit manipulation missing"
    assert "lat / 1e5" in js_content, "Coordinate scaling missing"
    assert "lng / 1e5" in js_content, "Coordinate scaling missing"
    
    print("   ✓ Polyline decoder algorithm correctly implemented")

def test_map_handles_missing_data():
    """Test that map gracefully handles missing map data"""
    print("\n6. Testing graceful handling of missing map data...")
    
    with open("public/js/activity-detail.js", "r") as f:
        js_content = f.read()
    
    # Check for null/undefined checks
    assert "if (!this.activity.raw_json)" in js_content, "Missing raw_json check"
    assert "if (!map || (!map.summary_polyline && !map.polyline))" in js_content, \
        "Missing map data check"
    
    # Check that method returns early if no data
    assert "return;" in js_content, "Early return not implemented"
    
    print("   ✓ Map gracefully handles missing data")

def test_map_markers_for_start_and_end():
    """Test that start and end markers are added to the map"""
    print("\n7. Testing start and end markers...")
    
    with open("public/js/activity-detail.js", "r") as f:
        js_content = f.read()
    
    # Check for start marker (green)
    assert "#10b981" in js_content, "Start marker color not found"
    assert "bindPopup('Start')" in js_content, "Start marker popup not found"
    
    # Check for end marker (red)
    assert "#ef4444" in js_content, "End marker color not found"
    assert "bindPopup('Finish')" in js_content, "End marker popup not found"
    
    # Check that markers use first and last coordinates
    assert "coordinates[0]" in js_content, "Start coordinate not used"
    assert "coordinates[coordinates.length - 1]" in js_content, "End coordinate not used"
    
    print("   ✓ Start and end markers properly configured")

def test_map_auto_fits_bounds():
    """Test that map automatically fits bounds to show entire route"""
    print("\n8. Testing map bounds fitting...")
    
    with open("public/js/activity-detail.js", "r") as f:
        js_content = f.read()
    
    # Check for fitBounds call
    assert "fitBounds(" in js_content, "fitBounds not called"
    assert "polyline.getBounds()" in js_content, "Polyline bounds not used"
    assert "padding:" in js_content, "Padding not configured"
    
    print("   ✓ Map auto-fits bounds to route")

def test_map_instance_cleanup():
    """Test that map instance is properly cleaned up on re-render"""
    print("\n9. Testing map instance cleanup...")
    
    with open("public/js/activity-detail.js", "r") as f:
        js_content = f.read()
    
    # Check for map instance tracking
    assert "this.mapInstance" in js_content, "Map instance not tracked"
    
    # Check for cleanup before creating new map
    assert "if (this.mapInstance)" in js_content, "Map instance check missing"
    assert "this.mapInstance.remove()" in js_content, "Map cleanup not implemented"
    
    print("   ✓ Map instance properly cleaned up")

def test_openstreetmap_attribution():
    """Test that OpenStreetMap attribution is included"""
    print("\n10. Testing OpenStreetMap attribution...")
    
    with open("public/js/activity-detail.js", "r") as f:
        js_content = f.read()
    
    # Check for OSM tile layer
    assert "tile.openstreetmap.org" in js_content, "OpenStreetMap tiles not used"
    
    # Check for attribution
    assert "OpenStreetMap" in js_content, "OpenStreetMap attribution missing"
    
    print("   ✓ OpenStreetMap properly attributed")

def run_all_tests():
    """Run all map integration tests"""
    print("\n" + "="*60)
    print("LEAFLET.JS MAP INTEGRATION TESTS (Task 4.3)")
    print("="*60)
    
    tests = [
        test_leaflet_library_included,
        test_map_container_exists,
        test_map_section_hidden_by_default,
        test_activity_detail_js_has_map_methods,
        test_polyline_decoder_algorithm,
        test_map_handles_missing_data,
        test_map_markers_for_start_and_end,
        test_map_auto_fits_bounds,
        test_map_instance_cleanup,
        test_openstreetmap_attribution,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"   ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"   ✗ ERROR: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

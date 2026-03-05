"""
Bug Condition Exploration Test for OAuth UI Flow

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists.
**DO NOT attempt to fix the test or the code when it fails.**

This test validates requirements 1.1, 1.2, 1.3 from bugfix.md:
- 1.1: Missing "Connect Strava" button in UI
- 1.2: Missing proper GET endpoint for authorization
- 1.3: Callback not redirecting with success message

**Validates: Requirements 1.1, 1.2, 1.3**
"""

import re
from pathlib import Path
from hypothesis import given, strategies as st, settings, Phase
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, follow_redirects=False)


@settings(phases=[Phase.generate, Phase.target])
@given(
    button_id=st.sampled_from([
        "connect-strava-btn",
        "strava-connect",
        "btn-strava-auth",
        "strava-auth-button"
    ])
)
def test_property_missing_connect_strava_button(button_id):
    """
    Property 1: Fault Condition - Missing OAuth UI Elements
    
    EXPECTED OUTCOME: This test FAILS (proves bug exists)
    
    Tests that index.html lacks a "Connect Strava" button element.
    The button should have an identifiable ID or class for user interaction.
    
    **Validates: Requirements 1.1**
    """
    # Read the index.html file
    index_path = Path("public/index.html")
    assert index_path.exists(), "index.html should exist"
    
    html_content = index_path.read_text(encoding="utf-8")
    
    # Check for button with ANY of the possible IDs
    possible_ids = [
        "connect-strava-btn",
        "strava-connect",
        "btn-strava-auth",
        "strava-auth-button"
    ]
    
    has_any_button = False
    for bid in possible_ids:
        button_pattern = rf'<button[^>]*id="{bid}"[^>]*>.*?[Cc]onnect.*?[Ss]trava.*?</button>'
        if re.search(button_pattern, html_content, re.DOTALL):
            has_any_button = True
            break
        
        link_pattern = rf'<a[^>]*id="{bid}"[^>]*>.*?[Cc]onnect.*?[Ss]trava.*?</a>'
        if re.search(link_pattern, html_content, re.DOTALL):
            has_any_button = True
            break
    
    # EXPECTED TO FAIL: The button should exist but currently doesn't
    assert has_any_button, (
        f"Missing 'Connect Strava' button with any of the expected IDs in index.html. "
        f"This confirms bug 1.1: UI lacks OAuth authorization button."
    )


@settings(phases=[Phase.generate, Phase.target])
@given(
    endpoint_path=st.just("/api/auth/strava")
)
def test_property_get_endpoint_returns_authorization_url(endpoint_path):
    """
    Property 1: Fault Condition - Missing OAuth UI Elements
    
    EXPECTED OUTCOME: This test FAILS (proves bug exists)
    
    Tests that GET /api/auth/strava endpoint returns proper authorization URL.
    The endpoint should return a JSON response with authorization_url field.
    
    **Validates: Requirements 1.2**
    """
    # Make GET request to the endpoint
    response = client.get(endpoint_path)
    
    # EXPECTED TO FAIL: Endpoint should exist and return 200
    assert response.status_code == 200, (
        f"GET {endpoint_path} returned {response.status_code}. "
        f"Expected 200 with authorization URL. "
        f"This confirms bug 1.2: Missing proper GET endpoint for OAuth flow."
    )
    
    # Check response structure
    data = response.json()
    assert "authorization_url" in data, (
        f"Response missing 'authorization_url' field. "
        f"This confirms bug 1.2: Endpoint doesn't return proper authorization URL."
    )
    
    # Validate the authorization URL format
    auth_url = data["authorization_url"]
    assert "strava.com/oauth/authorize" in auth_url, (
        f"Authorization URL doesn't point to Strava OAuth endpoint. "
        f"Got: {auth_url}"
    )
    
    # Check for required OAuth parameters
    assert "client_id=" in auth_url, "Missing client_id parameter"
    assert "redirect_uri=" in auth_url, "Missing redirect_uri parameter"
    assert "response_type=code" in auth_url, "Missing response_type=code parameter"
    assert "scope=" in auth_url, "Missing scope parameter"


@settings(phases=[Phase.generate, Phase.target], deadline=None)
@given(
    auth_code=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
        min_size=20,
        max_size=40
    )
)
def test_property_callback_redirects_with_success_message(auth_code):
    """
    Property 1: Fault Condition - Missing OAuth UI Elements
    
    EXPECTED OUTCOME: This test FAILS (proves bug exists)
    
    Tests that POST /api/auth/strava/callback redirects to UI with success message.
    The callback should exchange the code for tokens and redirect to index.html
    with success parameters including athlete information.
    
    **Validates: Requirements 1.3**
    """
    # Note: This test will fail because we can't actually exchange a fake code
    # But we're testing the STRUCTURE of the response, not the actual OAuth flow
    
    # Make GET request to callback endpoint (as Strava would redirect)
    response = client.get(f"/api/auth/strava/callback?code={auth_code}")
    
    # EXPECTED TO FAIL: Should redirect (3xx) to index.html with success message
    # Currently returns JSON instead of redirecting
    assert response.status_code in [301, 302, 303, 307, 308], (
        f"Callback returned {response.status_code} instead of redirect. "
        f"Expected redirect to index.html with success message. "
        f"This confirms bug 1.3: Callback doesn't redirect to UI."
    )
    
    # Check redirect location
    location = response.headers.get("location", "")
    assert "index.html" in location or location == "/", (
        f"Callback doesn't redirect to index.html. "
        f"Got location: {location}. "
        f"This confirms bug 1.3: Missing redirect to UI."
    )
    
    # Check for success parameters in redirect URL
    assert "success=" in location or "connected=" in location, (
        f"Redirect URL missing success parameter. "
        f"This confirms bug 1.3: No success confirmation in redirect."
    )


def test_concrete_missing_connect_button():
    """
    Concrete test case: Verify index.html lacks Connect Strava button.
    
    This is a focused test that checks the specific bug condition.
    
    **Validates: Requirements 1.1**
    """
    index_path = Path("public/index.html")
    html_content = index_path.read_text(encoding="utf-8")
    
    # Check for any button or link mentioning "Connect Strava"
    has_connect_strava = bool(re.search(
        r'(?:button|a)[^>]*>.*?[Cc]onnect.*?[Ss]trava',
        html_content,
        re.DOTALL
    ))
    
    # EXPECTED TO FAIL: Button should exist but doesn't
    assert has_connect_strava, (
        "index.html is missing a 'Connect Strava' button or link. "
        "This confirms bug 1.1: No UI element for OAuth authorization."
    )


def test_concrete_get_endpoint_exists():
    """
    Concrete test case: Verify GET /api/auth/strava endpoint exists and works.
    
    **Validates: Requirements 1.2**
    """
    response = client.get("/api/auth/strava")
    
    # EXPECTED TO FAIL: Should return 200 with authorization URL
    assert response.status_code == 200, (
        f"GET /api/auth/strava returned {response.status_code}. "
        "This confirms bug 1.2: GET endpoint not working properly."
    )
    
    data = response.json()
    assert "authorization_url" in data, (
        "Response missing authorization_url field. "
        "This confirms bug 1.2: Endpoint doesn't return proper structure."
    )


def test_concrete_callback_returns_json_not_redirect():
    """
    Concrete test case: Verify callback currently returns JSON instead of redirecting.
    
    This test documents the CURRENT (buggy) behavior to prove the bug exists.
    
    **Validates: Requirements 1.3**
    """
    # Use a fake code - this will fail at the Strava API level
    # But we're testing the response structure, not the actual OAuth flow
    response = client.get("/api/auth/strava/callback?code=fake_code_for_testing")
    
    # Current buggy behavior: Returns JSON (200 or 400) instead of redirect
    # EXPECTED TO FAIL: Should be a redirect (3xx), not JSON response
    assert response.status_code in [301, 302, 303, 307, 308], (
        f"Callback returned {response.status_code} (JSON response) instead of redirect. "
        f"This confirms bug 1.3: Callback doesn't redirect to UI with success message."
    )

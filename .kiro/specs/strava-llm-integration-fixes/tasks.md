# Implementation Plan

## Bug 1: Strava OAuth UI Flow

- [x] 1. Write bug condition exploration test for OAuth UI flow
  - **Property 1: Fault Condition** - Missing OAuth UI Elements
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to concrete failing cases - UI missing "Connect Strava" button, GET endpoint not returning authorization URL, callback not redirecting with success message
  - Test that index.html lacks a "Connect Strava" button element
  - Test that GET /api/auth/strava endpoint does not exist or does not return authorization URL
  - Test that POST /api/auth/strava/callback does not redirect to UI with success message
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found to understand root cause
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Write preservation property tests for OAuth flow (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing OAuth Token Exchange
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for existing OAuth functionality
  - Test that POST /api/auth/strava/callback successfully exchanges authorization code for tokens
  - Test that token refresh flow continues to work correctly
  - Test that Strava activity sync continues to fetch and store data correctly
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2_

- [x] 3. Fix for Strava OAuth UI Flow

  - [x] 3.1 Add "Connect Strava" button to index.html
    - Add button element with id "connect-strava-btn" in the UI
    - Add status display element to show connection state
    - Add JavaScript to handle button click and fetch authorization URL
    - Add display logic for athlete information after successful connection
    - _Bug_Condition: User attempts to connect Strava through UI (1.1, 1.2)_
    - _Expected_Behavior: Visible "Connect Strava" button that redirects to Strava authorization (2.1, 2.2)_
    - _Preservation: Existing OAuth token exchange and activity sync (3.1, 3.2)_
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.4_

  - [x] 3.2 Implement GET /api/auth/strava endpoint
    - Add GET handler to auth.py that returns Strava authorization URL
    - Include proper OAuth parameters (client_id, redirect_uri, scope, response_type)
    - Return JSON response with authorization_url field
    - _Bug_Condition: User clicks "Connect Strava" button (1.2)_
    - _Expected_Behavior: System returns authorization URL for redirect (2.2)_
    - _Preservation: Existing POST callback endpoint functionality (3.2)_
    - _Requirements: 1.2, 2.2_

  - [x] 3.3 Fix callback redirect to show success message
    - Modify POST /api/auth/strava/callback to redirect to index.html with success parameter
    - Include athlete information in redirect (name, id)
    - Update frontend to parse URL parameters and display success message
    - Display athlete information in the UI
    - _Bug_Condition: OAuth callback returns with authorization code (1.3)_
    - _Expected_Behavior: Redirect to UI with success confirmation and athlete info (2.3, 2.4)_
    - _Preservation: Token exchange and storage functionality (3.2)_
    - _Requirements: 1.3, 2.3, 2.4_

  - [x] 3.4 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - OAuth UI Elements Present
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.5 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing OAuth Functionality
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

## Bug 2: LLM Docker Endpoint

- [x] 4. Write bug condition exploration test for LLM endpoint construction
  - **Property 1: Fault Condition** - Incorrect LLM Endpoint URL
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: Scope the property to concrete failing cases - OLLAMA_ENDPOINT with `/api` suffix or trailing slashes
  - Test that when OLLAMA_ENDPOINT is `http://ollama:11434/api`, the constructed URL is `http://ollama:11434/api/chat/completions` (incorrect)
  - Test that evaluation requests fail with 404 Not Found error
  - Test various base URL formats: with `/api`, with trailing slash, with both
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found (e.g., "URL construction produces http://ollama:11434/api/chat/completions instead of http://ollama:11434/v1/chat/completions")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.4, 1.5, 1.6_

- [x] 5. Write preservation property tests for LLM client (BEFORE implementing fix)
  - **Property 2: Preservation** - LM Studio Local Connection
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for LM Studio local endpoint
  - Test that when OLLAMA_ENDPOINT is `http://localhost:1234` (no `/api` suffix), the client connects successfully
  - Test that evaluation generation works correctly with properly formatted endpoints
  - Test that JSON response validation continues to work
  - Test that retry logic on connection errors continues to function
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.3, 3.5_

- [x] 6. Fix for LLM Docker Endpoint

  - [x] 6.1 Implement URL normalization in llm_client.py
    - Add function to normalize base URL: strip trailing slashes
    - Add function to remove `/api` suffix if present
    - Update URL construction to use normalized base URL + `/v1/chat/completions`
    - Handle edge cases: multiple trailing slashes, `/api/` with trailing slash
    - _Bug_Condition: OLLAMA_ENDPOINT contains `/api` suffix or trailing slashes (1.4, 1.5)_
    - _Expected_Behavior: Construct correct OpenAI-compatible endpoint `/v1/chat/completions` (2.5, 2.6, 2.7)_
    - _Preservation: LM Studio local connection continues to work (3.3)_
    - _Requirements: 1.4, 1.5, 2.5, 2.6, 2.7_

  - [x] 6.2 Update docker-compose.yml environment variables
    - Change OLLAMA_ENDPOINT from `http://ollama:11434/api` to `http://ollama:11434`
    - Ensure the endpoint format is consistent with the new URL construction logic
    - _Bug_Condition: Docker environment uses incorrect endpoint format (1.4)_
    - _Expected_Behavior: Docker configuration uses base URL without `/api` suffix (2.7)_
    - _Preservation: Existing database and activity data (3.6)_
    - _Requirements: 1.4, 2.7_

  - [x] 6.3 Update .env.template documentation
    - Document the correct endpoint format: base URL without `/api` suffix
    - Add examples: `http://ollama:11434` for Docker, `http://localhost:1234` for LM Studio
    - Add comment explaining that `/v1/chat/completions` is appended automatically
    - _Bug_Condition: Users configure endpoint incorrectly (1.5)_
    - _Expected_Behavior: Clear documentation of correct endpoint format (2.6, 2.7)_
    - _Preservation: Existing configuration options (3.3)_
    - _Requirements: 2.6, 2.7_

  - [x] 6.4 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Correct LLM Endpoint URL
    - **IMPORTANT**: Re-run the SAME test from task 4 - do NOT write a new test
    - The test from task 4 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 4
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - _Requirements: 2.5, 2.6, 2.7, 2.8_

  - [x] 6.5 Verify preservation tests still pass
    - **Property 2: Preservation** - LM Studio and Existing Functionality
    - **IMPORTANT**: Re-run the SAME tests from task 5 - do NOT write new tests
    - Run preservation property tests from step 5
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [x] 7. Checkpoint - Ensure all tests pass
  - Run all exploration tests (tasks 1 and 4) - should PASS
  - Run all preservation tests (tasks 2 and 5) - should PASS
  - Verify OAuth UI flow works end-to-end in browser
  - Verify LLM evaluation generation works in Docker environment
  - Ensure all tests pass, ask the user if questions arise

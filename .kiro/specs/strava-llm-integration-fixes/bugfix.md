# Bugfix Requirements Document

## Introduction

This document addresses two critical integration issues in the fitness evaluation system:

1. **Strava OAuth Authorization Flow**: The current implementation lacks a proper user-facing authorization flow. Users must manually execute POST requests to initiate Strava authorization, which is not user-friendly and prevents seamless integration.

2. **LLM Integration in Docker**: The LLM client fails to connect to the dockerized Ollama service due to incorrect endpoint URL construction. The client appends `/chat/completions` to the base URL, but the configuration provides `http://ollama:11434/api`, resulting in the invalid URL `http://ollama:11434/api/chat/completions` instead of the correct OpenAI-compatible endpoint `http://ollama:11434/v1/chat/completions`.

These issues prevent users from properly connecting their Strava accounts and generating AI-powered evaluations when running the application in Docker.

## Bug Analysis

### Current Behavior (Defect)

#### Bug 1: Strava OAuth Authorization Flow

1.1 WHEN a user attempts to connect their Strava account through the UI THEN the system does not provide a clickable authorization link or button

1.2 WHEN a user wants to authorize Strava access THEN the system requires manual execution of POST requests to `/api/auth/strava` endpoint

1.3 WHEN the Strava OAuth callback returns with an authorization code THEN the system does not redirect the user back to the application with a success message

#### Bug 2: LLM Integration in Docker

1.4 WHEN the application runs in Docker and attempts to generate an evaluation THEN the system makes a request to `http://ollama:11434/api/chat/completions` which returns 404 Not Found

1.5 WHEN the LLM client constructs the endpoint URL THEN the system appends `/chat/completions` to `OLLAMA_ENDPOINT` value `http://ollama:11434/api`, creating an incorrect path

1.6 WHEN the evaluation fails due to LLM connection error THEN the system returns "Client error '404 Not Found' for url 'http://ollama:11434/chat/completions'" to the frontend

### Expected Behavior (Correct)

#### Bug 1: Strava OAuth Authorization Flow

2.1 WHEN a user wants to connect their Strava account THEN the system SHALL provide a visible "Connect Strava" button or link in the UI

2.2 WHEN a user clicks the Strava authorization button THEN the system SHALL redirect them to Strava's authorization page with proper OAuth parameters

2.3 WHEN the Strava OAuth callback returns with an authorization code THEN the system SHALL exchange the code for tokens and redirect the user back to the application with a success confirmation

2.4 WHEN Strava authorization is successful THEN the system SHALL display the connection status to the user (e.g., "Connected to Strava" with athlete information)

#### Bug 2: LLM Integration in Docker

2.5 WHEN the application runs in Docker and attempts to generate an evaluation THEN the system SHALL successfully connect to the Ollama service at `http://ollama:11434/v1/chat/completions`

2.6 WHEN the LLM client constructs the endpoint URL THEN the system SHALL use the correct OpenAI-compatible endpoint format `/v1/chat/completions` regardless of the base URL configuration

2.7 WHEN the OLLAMA_ENDPOINT is configured as `http://ollama:11434` THEN the system SHALL construct the full URL as `http://ollama:11434/v1/chat/completions`

2.8 WHEN an evaluation is requested THEN the system SHALL successfully generate the evaluation using the dockerized Ollama service without connection errors

### Unchanged Behavior (Regression Prevention)

3.1 WHEN Strava activities are synced for a specific week THEN the system SHALL CONTINUE TO fetch and store activity data correctly

3.2 WHEN Strava tokens need to be refreshed THEN the system SHALL CONTINUE TO use the refresh token flow properly

3.3 WHEN the application runs locally (outside Docker) with LM Studio THEN the system SHALL CONTINUE TO connect to LM Studio at the configured endpoint

3.4 WHEN weekly aggregates are computed from Strava activities THEN the system SHALL CONTINUE TO calculate run_km, ride_km, strength_sessions, and total_moving_time_min correctly

3.5 WHEN the LLM generates an evaluation response THEN the system SHALL CONTINUE TO validate the JSON response and handle retries on connection errors

3.6 WHEN existing database data exists THEN the system SHALL CONTINUE TO preserve all stored activities, logs, measurements, and evaluations

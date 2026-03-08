# Bugfix Requirements Document

## Introduction

LM Studio users currently lack access to data retrieval tools (save_athlete_goal, get_my_goals, get_my_recent_activities, get_my_weekly_metrics) because the application uses a separate LMStudioChatService implementation instead of the unified LangChainChatService. This creates inconsistent behavior across LLM providers, where Ollama and OpenAI users have full tool access while LM Studio users do not. Since LangChain's ChatOpenAI already supports LM Studio's OpenAI-compatible endpoint, the fix involves removing the conditional service selection and using LangChainChatService for all providers.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN LLM_TYPE is set to "lm-studio" THEN the system uses LMStudioChatService which lacks data retrieval tools

1.2 WHEN LLM_TYPE is set to "lm-studio" THEN the system provides inconsistent behavior compared to other LLM providers

1.3 WHEN app/api/chat.py selects a chat service THEN the system uses conditional logic that routes LM Studio to a separate implementation

### Expected Behavior (Correct)

2.1 WHEN LLM_TYPE is set to "lm-studio" THEN the system SHALL use LangChainChatService with all 4 data retrieval tools available

2.2 WHEN LLM_TYPE is set to "lm-studio" THEN the system SHALL provide identical behavior to Ollama and OpenAI providers

2.3 WHEN app/api/chat.py selects a chat service THEN the system SHALL use LangChainChatService for all LLM providers without conditional routing

### Unchanged Behavior (Regression Prevention)

3.1 WHEN LLM_TYPE is set to "ollama" THEN the system SHALL CONTINUE TO use LangChainChatService with all 4 data retrieval tools

3.2 WHEN LLM_TYPE is set to "openai" THEN the system SHALL CONTINUE TO use LangChainChatService with all 4 data retrieval tools

3.3 WHEN any LLM provider is used THEN the system SHALL CONTINUE TO provide access to save_athlete_goal, get_my_goals, get_my_recent_activities, and get_my_weekly_metrics tools

3.4 WHEN chat requests are processed THEN the system SHALL CONTINUE TO return responses in the same format and structure

3.5 WHEN LangChain's ChatOpenAI is configured THEN the system SHALL CONTINUE TO support OpenAI-compatible endpoints including LM Studio

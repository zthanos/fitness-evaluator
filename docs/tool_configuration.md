# Tool Configuration Documentation

## Overview

The Context Engineering system provides a flexible tool configuration mechanism that allows enabling/disabling different categories of tools. This is particularly important for security and control over external data access.

## Configuration File

Tool configuration is managed in `app/ai/config/model_profiles.yaml` under the `tools` section.

### Structure

```yaml
tools:
  # Enable/disable tool categories
  enabled_categories:
    - "data_retrieval"  # Internal data access tools
    # - "web_search"    # External web search (commented out = disabled)
  
  # Web search configuration (for future intent-gated use)
  web_search:
    enabled: false  # Disabled by default for security
    intent_gating: true  # Require explicit intent classification
    allowed_intents: []  # Empty = no intents allow web search
  
  # Data retrieval tools configuration
  data_retrieval:
    enabled: true
    max_results_per_query: 20
    timeout_seconds: 5
```

## Tool Categories

### Data Retrieval Tools (Enabled by Default)

These tools access internal database records:

- **GetRecentActivities**: Retrieves athlete activities from the database
- **GetAthleteGoals**: Retrieves active goals for an athlete
- **GetWeeklyMetrics**: Retrieves weekly body measurements

### Web Search Tools (Disabled by Default)

Web search tools are **disabled by default** for security reasons. They can be enabled in the future with intent-gating.

## Usage

### Getting Enabled Tools

```python
from app.ai.tools import get_enabled_tools

# Get all enabled tools (no web search)
tools = get_enabled_tools()

# Get tools for a specific intent (future: may enable web search for certain intents)
tools = get_enabled_tools(intent="research")
```

### Checking Web Search Status

```python
from app.ai.tools import is_web_search_enabled

# Check if web search is enabled
if is_web_search_enabled():
    # Web search is available
    pass

# Check if web search is enabled for a specific intent
if is_web_search_enabled(intent="research"):
    # Web search is available for research intent
    pass
```

## Security Considerations

### Why Web Search is Disabled

1. **Data Privacy**: Prevents accidental leakage of athlete data to external services
2. **Cost Control**: Web search APIs often have usage costs
3. **Response Quality**: Internal data is more relevant and reliable for fitness coaching
4. **Compliance**: Easier to maintain GDPR/privacy compliance with internal-only data

### Future Intent-Gated Web Search

The configuration supports future enabling of web search for specific intents:

```yaml
web_search:
  enabled: true  # Enable web search
  intent_gating: true  # Require intent classification
  allowed_intents:
    - "research"  # Allow for research queries
    - "external_info"  # Allow for external information queries
```

With this configuration:
- Web search would only be available when the intent is classified as "research" or "external_info"
- All other intents would still use internal data only
- This provides fine-grained control over when external data access is appropriate

## Testing

The tool configuration is validated by tests in `test_tool_configuration.py`:

- ✅ Web search is disabled by default
- ✅ Web search tools are not in the enabled tools list
- ✅ Web search is not enabled for any intent by default
- ✅ Data retrieval tools are enabled by default
- ✅ Configuration structure supports future intent-gating

Run tests with:
```bash
pytest test_tool_configuration.py -v
```

## Implementation Details

### Tool Registry

Tools are organized in `app/ai/tools/__init__.py`:

```python
TOOL_CATEGORIES = {
    "data_retrieval": [
        get_recent_activities,
        get_athlete_goals,
        get_weekly_metrics,
    ],
    "web_search": [
        # Web search tools would go here
        # Currently empty (disabled)
    ],
}
```

### Configuration Loading

The `load_tool_config()` function loads configuration from `model_profiles.yaml` with sensible defaults if the file doesn't exist.

### Tool Filtering

The `get_enabled_tools()` function filters tools based on:
1. Enabled categories from configuration
2. Web search enabled flag
3. Intent-gating rules (if web search is enabled)

## Requirements Validation

This implementation validates **Requirement 5.1.7**:

> THE Context_Engineering_System SHALL disable web search tools by default (require explicit intent-gating for future use)

✅ **Validated**: Web search tools are disabled by default, and the configuration supports future intent-gated enabling.

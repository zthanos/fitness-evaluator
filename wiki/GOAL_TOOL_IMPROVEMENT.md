# Goal Tool Improvement

## Problem
The LLM was confused about the `target_value` parameter when saving weight loss goals. When a user said "I want to lose 5kg", the LLM didn't know whether to pass:
- The amount to lose (5)
- The target weight (current weight - 5)
- Or leave it as None

This caused tool execution errors and the LLM apologizing to the user.

## Root Cause
The tool's parameter description was ambiguous:
```python
target_value: Optional[float] = Field(
    None,
    description="Numeric target (e.g., target weight, distance, time)"
)
```

This didn't clearly explain:
- For weight goals, it should be the TARGET WEIGHT, not the amount to lose/gain
- It's optional and can be None if the current weight is unknown
- The description field should contain all the context

## Solution

### Updated `app/ai/tools/save_athlete_goal.py`

1. **Improved parameter description:**
```python
target_value: Optional[float] = Field(
    None,
    description=(
        "Numeric target value. For weight goals, this should be the TARGET WEIGHT in kg (not the amount to lose/gain). "
        "For performance goals, this could be distance (km), time (minutes), or other metrics. "
        "Can be None if the goal doesn't have a specific numeric target."
    )
)
```

2. **Enhanced tool docstring:**
```python
"""
IMPORTANT: For weight goals (weight_loss or weight_gain):
- target_value should be the TARGET WEIGHT in kg (not the amount to lose/gain)
- If the athlete says "lose 5kg" and their current weight is 80kg, target_value should be 75
- If you don't know the current weight, you can omit target_value and include the weight change in the description
"""
```

3. **Better description field guidance:**
```python
description: str = Field(
    ...,
    description="Detailed goal description from conversation (e.g., 'Lose 5kg for Posidonia Tour cycling event on May 30, 2026')"
)
```

## How It Works Now

### Scenario 1: User provides current weight
- User: "I want to lose 5kg. I currently weigh 80kg"
- LLM calculates: target_value = 80 - 5 = 75
- Tool call: `save_athlete_goal(goal_type="weight_loss", target_value=75, description="Lose 5kg for event")`

### Scenario 2: User doesn't provide current weight
- User: "I want to lose 5kg for my cycling event"
- LLM doesn't know current weight
- Tool call: `save_athlete_goal(goal_type="weight_loss", target_value=None, description="Lose 5kg for Posidonia Tour cycling event on May 30, 2026")`
- The description contains all the context, and the LLM can ask for current weight later

### Scenario 3: Performance goal
- User: "I want to complete a 70km ride"
- Tool call: `save_athlete_goal(goal_type="performance", target_value=70, description="Complete Posidonia Tour 70km cycling event")`

## Benefits
1. Clear guidance for the LLM on how to use the tool
2. Handles cases where current weight is unknown
3. Reduces tool execution errors
4. Better user experience - no confusing error messages
5. Description field captures full context even without numeric target

## Testing
After restarting the server, test with:
1. "I want to lose 5kg" (without current weight) → Should save with target_value=None
2. "I want to lose 5kg, I currently weigh 80kg" → Should save with target_value=75
3. "I want to complete a 100km ride" → Should save with target_value=100

The LLM should now handle all these cases correctly without errors.

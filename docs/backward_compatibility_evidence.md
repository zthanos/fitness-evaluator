# Backward Compatibility for Evidence Data

## Overview

This document describes the backward compatibility implementation for the `evidence_map_json` field in `WeeklyEval` records, ensuring that existing records without evidence tracking continue to work seamlessly.

## Implementation

### Database Schema

The `evidence_map_json` field in the `weekly_evals` table is nullable:

```python
evidence_map_json: dict = Column(JSON, nullable=True)
```

This allows:
- Old records to have `NULL` values (created before evidence tracking was implemented)
- New records to have evidence data stored as JSON

### Model Property

The `WeeklyEval` model includes an `evidence_cards` property that provides backward compatibility:

```python
@property
def evidence_cards(self) -> list:
    """
    Get evidence cards with backward compatibility.
    
    Returns empty list if evidence_map_json is null (for old records).
    This ensures backward compatibility with existing WeeklyEval records
    that were created before evidence tracking was implemented.
    
    Returns:
        List of evidence card dictionaries
    """
    if self.evidence_map_json is None:
        return []
    return self.evidence_map_json.get("evidence_cards", [])
```

### Behavior

| Scenario | `evidence_map_json` Value | `evidence_cards` Property Returns |
|----------|---------------------------|-----------------------------------|
| Old record (pre-evidence tracking) | `NULL` | `[]` (empty list) |
| New record with evidence | `{"evidence_cards": [...]}` | List of evidence cards |
| New record without evidence | `{"evidence_cards": []}` | `[]` (empty list) |
| Malformed data (missing key) | `{"other_key": "value"}` | `[]` (empty list) |

## Usage

### Reading Evidence Cards

Always use the `evidence_cards` property instead of accessing `evidence_map_json` directly:

```python
# ✅ Correct - uses property with backward compatibility
weekly_eval = eval_service.get_evaluation(week_id)
evidence = weekly_eval.evidence_cards  # Always returns a list

# ❌ Incorrect - may return None for old records
evidence = weekly_eval.evidence_map_json["evidence_cards"]  # May raise KeyError or TypeError
```

### API Responses

The API endpoints automatically handle backward compatibility through the model property:

```python
@router.get("/{week_id}", response_model=WeeklyEval)
async def get_evaluation(week_id: str, eval_service: EvaluationService = Depends(get_evaluation_service)) -> WeeklyEval:
    evaluation = eval_service.get_evaluation(week_id)
    # evaluation.evidence_cards will always return a list, even for old records
    return evaluation
```

### Writing Evidence Cards

When creating or updating evaluations, always store evidence in the standard format:

```python
# Store evidence cards
weekly_eval.evidence_map_json = {"evidence_cards": evidence_cards}

# For evaluations without evidence (e.g., errors during collection)
weekly_eval.evidence_map_json = {"evidence_cards": []}
```

## Testing

Comprehensive tests verify backward compatibility:

1. **Old records with null evidence_map_json** - Ensures old records are readable and return empty list
2. **New records with evidence** - Verifies evidence cards are stored and retrieved correctly
3. **Empty evidence** - Tests records with empty evidence arrays
4. **Malformed data** - Handles records with missing or incorrect keys gracefully
5. **Mixed records** - Verifies old and new records can coexist

Run tests:
```bash
python -m pytest test_backward_compatibility_evidence.py -v
```

## Migration Notes

- **No database migration required** - The field was already nullable
- **No code changes required** - Existing code continues to work
- **Gradual rollout** - New evaluations will have evidence, old ones remain unchanged
- **No data loss** - All existing records remain accessible

## Requirements Validated

This implementation validates **Requirement 4.1.6**:
- ✅ Handle null evidence_data in existing records
- ✅ Provide default empty list when evidence_data is null
- ✅ Maintain backward compatibility with existing WeeklyEval records

## Future Considerations

If you need to backfill evidence for old records:

1. Query old records: `SELECT * FROM weekly_evals WHERE evidence_map_json IS NULL`
2. Re-run evaluation with evidence collection enabled
3. Update records with new evidence data

However, this is **not required** for the system to function correctly.

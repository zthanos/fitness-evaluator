# Goals Dashboard Fix

## Problem
Goals were being saved successfully to the database (confirmed via API and direct database query), but they weren't displaying in the Settings page dashboard.

## Root Cause
The settings page had TWO `DOMContentLoaded` event handlers:
1. One in `settings.html` that created a local `settings` variable
2. One in `settings.js` that tried to assign to the global `settingsPage` variable

This caused:
- The page to initialize properly and load goals
- But the global `settingsPage` variable remained undefined
- The onclick handlers in the dropdown menus (mark completed, delete, etc.) failed because they referenced the undefined global variable

## Fix Applied

### 1. Updated `settings.html`
Changed the DOMContentLoaded handler to assign to the global variable:
```javascript
// Before:
const settings = new SettingsPage();
await settings.init();

// After:
settingsPage = new SettingsPage();
await settingsPage.init();
```

### 2. Updated `settings.js`
Removed the duplicate DOMContentLoaded handler and added a comment explaining the setup:
```javascript
// Global instance for onclick handlers
let settingsPage;

// Note: DOMContentLoaded handler is in settings.html, not here
// The global settingsPage variable is set there
```

## Verification

### Check Goal in Database
```bash
python -c "from sqlalchemy import create_engine; from sqlalchemy.orm import sessionmaker; from app.models.athlete_goal import AthleteGoal; engine = create_engine('sqlite:///./fitness_eval.db'); Session = sessionmaker(bind=engine); db = Session(); goals = db.query(AthleteGoal).all(); print(f'Total goals: {len(goals)}'); [print(f'- {g.id}: {g.goal_type} - {g.status}') for g in goals]"
```

### Check API Endpoint
```bash
curl http://localhost:8000/api/goals
```

### Check Frontend
1. Open http://localhost:8000/settings.html
2. Goals should now display in the "Goals" section
3. Dropdown menus (mark completed, delete) should work

## Files Modified
1. `public/settings.html` - Fixed global variable assignment
2. `public/js/settings.js` - Removed duplicate event handler

## Expected Behavior
- Active goals display in the "Goals" section with:
  - Goal type emoji and label
  - Description
  - Target value (if applicable)
  - Target date and days remaining (if applicable)
  - Dropdown menu with actions (mark completed, mark abandoned, delete)
- "Set New Goal with Coach" button navigates to chat
- Goal history shows completed/abandoned goals in collapsible section

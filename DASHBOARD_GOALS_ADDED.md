# Dashboard Goals Section Added

## Changes Made

Added an "Active Goals" section to the main dashboard (index.html) that displays all active goals set through the AI coach.

### Location
The goals section appears on the dashboard between the Quick Stats and Action Cards sections.

### Features

1. **Goals Display**
   - Shows all active goals in a grid layout (2 columns on desktop, 1 on mobile)
   - Each goal card shows:
     - Goal type emoji and label (Weight Loss, Performance, etc.)
     - Description
     - Target value (if applicable, e.g., 85kg)
     - Days remaining until target date with color-coded badge:
       - Green: More than 7 days left
       - Yellow: 1-7 days left
       - Red: Overdue
     - "Manage" button linking to settings page

2. **Empty State**
   - Shows helpful message when no goals exist
   - Prompts user to click "Set New Goal" button

3. **Error Handling**
   - Shows error message if goals fail to load
   - Suggests refreshing the page

4. **Loading State**
   - Shows spinner while goals are being loaded

### UI Components

**Header:**
- Title: "🎯 Active Goals"
- "Set New Goal" button (links to chat.html)

**Goal Cards:**
- Emoji-based goal type indicators
- Clean, card-based layout
- Hover effects for better UX
- Responsive grid layout

### Integration

The goals section integrates with:
- `/api/goals?status=active` endpoint
- Existing API client (api.js)
- Settings page for goal management

### Files Modified

1. `public/index.html`
   - Added goals section HTML
   - Added `loadActiveGoals()` function
   - Added `renderGoalCard()` function
   - Integrated goals loading into `loadDashboardData()`

## Testing

1. Open http://localhost:8000/
2. Goals section should appear below Quick Stats
3. Your active goal should display with:
   - ⬇️ Weight Loss
   - Description: "Loose weight for the bike Posidonia Tour"
   - Target: 85kg
   - Days remaining badge
   - "Manage" button

## Next Steps

Users can now:
1. See their active goals on the main dashboard
2. Click "Set New Goal" to chat with AI coach
3. Click "Manage" to go to settings for goal actions (mark completed, delete, etc.)

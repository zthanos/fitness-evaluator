# Fitness Evaluator - Web UI Guide

## Overview

The Fitness Evaluator web interface provides a modern, DaisyUI-based dashboard for managing fitness data and receiving AI-powered evaluations.

## Quick Start

### Prerequisites
- Backend API running on `http://localhost:8000`
- Python environment with dependencies installed

### Starting the Application

```bash
# Install dependencies (if not already done)
uv sync

# Run database migrations
uv run alembic upgrade head

# Start the FastAPI server
uv run uvicorn app.main:app --reload
```

Then open your browser to:
- **Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Architecture

### Frontend Structure
```
public/
├── index.html              # Dashboard landing page
├── logs.html               # Daily logging form
├── measurements.html       # Weekly measurements tracker
├── targets.html            # Plan targets management  
├── evaluation.html         # Evaluation results & reporting
├── js/
│   ├── api.js             # REST API client
│   └── utils.js           # Utility functions
└── css/                   # Custom stylesheets (uses DaisyUI via CDN)
```

### Pages

#### 1. Dashboard (index.html)
**Purpose**: Main landing page with quick stats and action cards

**Features**:
- Quick stats: Latest score, total logs, activities, active plans
- Action cards linking to all major features
- Recent activity timeline
- Evaluation modal with week picker
- Theme toggle (light/dark mode)

**Key Components**:
- Hero banner with welcome message
- Stats cards (4-column grid)
- Action cards (2x2 grid)
- Recent activity list

#### 2. Daily Logs (logs.html)
**Purpose**: Track daily nutrition, adherence, and recovery metrics

**Form Fields**:
- Date (required)
- Calories In (kcal)
- Adherence Score (0-10 slider)
- Sleep Hours
- Energy Level (1-10 slider)
- Notes

**Features**:
- Real-time score display on sliders
- Recent entries sidebar
- Weekly statistics (averages)
- Form validation

**Data Submitted**:
```javascript
{
  log_date: "2024-12-16",
  calories_in: 2000,
  adherence_score: 8,
  sleep_hours: 7.5,
  energy_level: 7,
  notes: "Good day overall"
}
```

#### 3. Weekly Measurements (measurements.html)
**Purpose**: Record body composition, recovery metrics, and wellness data

**Form Fields**:
- Week Starting (Monday)
- Weight (lbs)
- Body Fat %
- Measurements: Chest, Waist, Hips, Thigh (inches)
- Resting Heart Rate (bpm)
- Avg Sleep Hours
- Avg Energy Level (1-10)
- Sleep Quality Score (1-10)
- Notes

**Features**:
- Grouped form sections (Body Metrics, Recovery & Wellness)
- Measurement history sidebar
- Progress tracker (weight/fat changes)
- Week picker for retrospective entries

#### 4. Plan Targets (targets.html)
**Purpose**: Create and manage weekly fitness goals

**Form Fields**:
- Target Week (Monday)
- Target Name
- Category (Nutrition, Training, Recovery, Body Composition, Performance)
- Target Value
- Unit
- Min/Max Values (optional)
- Description

**Features**:
- Category-based organization
- Min/max range support
- Target count by category
- Active targets list

#### 5. Evaluation Results (evaluation.html)
**Purpose**: Display AI-generated fitness analysis and recommendations

**Features**:
- Overall score display with badge
- Summary analysis text
- Detailed analysis cards by category
- Score breakdown with progress bars
- Key metrics from this week
- Recommendations section
- Supporting evidence section:
  - Daily logs evidence
  - Strava activities evidence
  - Weekly measurements evidence
- Actions: Refresh, Download Report, Back Home

**Dynamic Elements**:
- Fetches data from URL parameter: `?week=2024-12-16`
- Loads related data (logs, activities, measurements)
- Displays evaluation details from API

## JavaScript API Client

### APIClient Class (api.js)

The `APIClient` class provides a clean interface to all backend endpoints.

**Initialization**:
```javascript
const api = new APIClient(); // Automatically detects origin + /api
```

**Available Methods**:

#### Daily Logs
- `createDailyLog(data)` - POST /api/logs/daily
- `getDailyLog(date)` - GET /api/logs/daily/{date}
- `listDailyLogs()` - GET /api/logs/daily

#### Weekly Measurements
- `createWeeklyMeasurement(data)` - POST /api/logs/metrics
- `getWeeklyMeasurement(weekStart)` - GET /api/logs/metrics/{week}
- `listWeeklyMeasurements()` - GET /api/logs/metrics

#### Plan Targets
- `createPlanTarget(data)` - POST /api/logs/targets
- `getPlanTarget(weekStart)` - GET /api/logs/targets/{week}
- `listPlanTargets()` - GET /api/logs/targets
- `getCurrentPlanTarget()` - GET /api/logs/targets/current

#### Strava Integration
- `syncStravaActivities(weekStart)` - POST /api/strava/sync
- `getStravaActivities()` - GET /api/strava/activities
- `getStravaAggregates(weekStart)` - GET /api/strava/aggregates/{week}

#### Evaluations
- `evaluateWeek(weekStart)` - POST /api/evaluate/{week}
- `getEvaluation(weekStart)` - GET /api/evaluate/{week}
- `listEvaluations()` - GET /api/evaluate
- `refreshEvaluation(weekStart)` - POST /api/evaluate/{week}/refresh

## Utility Functions (utils.js)

### Date Utilities
- `getWeekStart(date?)` - Get Monday of current/given week
- `formatDate(date)` - Format as YYYY-MM-DD
- `formatDateDisplay(dateStr)` - Format as "Mon, Dec 16"
- `getWeekRange(date?)` - Get Monday-Sunday range

### UI/UX Utilities
- `showToast(message, type)` - Show toast notification
- `showSuccess(message)` - Success toast
- `showError(error)` - Error toast
- `closeAllModals()` - Close all dialogs
- `formatDuration(minutes)` - Convert minutes to "2h 30m"
- `formatDistance(miles)` - Format with 1 decimal place

### Styling Utilities
- `getScoreColor(score)` - Get color class (red/warning/success)
- `getScoreBadge(score)` - Get HTML badge element

## Data Flow

```
┌─────────────────────────────────────────┐
│      Browser (DaisyUI Pages)            │
│  ├─ index.html (Dashboard)              │
│  ├─ logs.html (Daily Entry)             │
│  ├─ measurements.html (Weekly)          │
│  ├─ targets.html (Goals)                │
│  └─ evaluation.html (Results)           │
└──────────────┬──────────────────────────┘
               │ fetch() with api.js
               ↓
┌─────────────────────────────────────────┐
│      FastAPI Backend (/api/*)           │
│  ├─ /api/logs/* (CRUD logs)             │
│  ├─ /api/strava/* (Sync activities)     │
│  ├─ /api/evaluate/* (AI analysis)       │
│  └─ /api/auth/* (OAuth)                 │
└──────────────┬──────────────────────────┘
               │ SQLAlchemy ORM
               ↓
┌─────────────────────────────────────────┐
│      SQLite Database                    │
│  ├─ daily_logs (nutrition, adherence)   │
│  ├─ weekly_measurements (body metrics)  │
│  ├─ strava_activities (synced workouts) │
│  ├─ plan_targets (goals)                │
│  └─ weekly_evals (AI analysis)          │
└─────────────────────────────────────────┘
```

## Styling & Theming

### DaisyUI Components Used
- **Layout**: navbar, card, hero, container
- **Forms**: input, select, textarea, range, checkbox
- **Navigation**: btn, dropdown, menu
- **Data Display**: stat, badge, progress, divider
- **Feedback**: skeleton, loading, tooltip
- **Modal**: dialog (HTML5 standard)

### Themes
The app supports light/dark themes via DaisyUI. Toggle with theme button in navbar.

### Responsive Design
- Mobile-first approach
- Breakpoints: sm (640px), md (768px), lg (1024px)
- Grid layouts adapt: 1-col on mobile, 2-3 cols on desktop

## Common Workflows

### 1. Daily Logging Workflow
```
User → logs.html → Fill form → Submit
       ↓
API → Create daily_log → Database
       ↓
UI → Show success toast → Update recent list
```

### 2. Evaluation Generation Workflow
```
User → index.html → Click "Generate Evaluation" → Pick week
       ↓
API → Create evaluation + call LLM → Parse response
       ↓
UI → Redirect to evaluation.html?week=X → Show results
```

### 3. Measurement Entry Workflow
```
User → measurements.html → Fill form → Submit
       ↓
API → Create weekly_measurement → Database
       ↓
UI → Update history & progress trackers
```

## Error Handling

All pages use consistent error handling:
- API errors → Red toast with error message
- Missing data → Graceful fallbacks (e.g., "--" values)
- Network errors → Retry buttons and status messages

## Performance

### Optimization Strategies
- **Lazy loading**: Pages load data on demand
- **Caching**: Recent data cached in sidebar
- **Minimal dependencies**: DaisyUI via CDN only
- **Modular JS**: Separate api.js and utils.js files

### Bundle Size
- `api.js`: ~4KB (unminified)
- `utils.js`: ~3KB (unminified)
- DaisyUI: ~20KB (via CDN)
- Total: Minimal, suitable for all connections

## Development

### Adding a New Page

1. Create `public/new-page.html`
2. Import `<script src="js/api.js"></script>`
3. Import `<script src="js/utils.js"></script>`
4. Use APIClient methods to fetch/post data
5. Add navigation link in navbar dropdown

### Customizing Styles

Edit `public/css/custom.css` (if needed) or override DaisyUI classes inline.

### Testing API Endpoints

Use the interactive Swagger UI at `/docs` or ReDoc at `/redoc`.

## Troubleshooting

### API Returns 404 on /api routes
- **Fix**: Ensure FastAPI server is running on port 8000
- Check that routes are registered with `/api` prefix in `app/main.py`

### Static files not serving (404 on index.html)
- **Fix**: Verify `public/` directory exists with HTML files
- Check StaticFiles is mounted in `app/main.py`

### Strava sync returns error
- **Fix**: Verify Strava OAuth credentials in `.env`
- Check LM Studio endpoint in `.env`

### Theme toggle not working
- **Fix**: Check browser DevTools for JS errors
- Verify DaisyUI is loading from CDN

## Browser Support

- Chrome/Edge: ✅ (v90+)
- Firefox: ✅ (v88+)
- Safari: ✅ (v14+)
- Mobile browsers: ✅

## Future Enhancements

Potential improvements:
1. Add chart libraries (Chart.js) for data visualization
2. Implement data export (CSV, PDF)
3. Add mobile app using React Native
4. Real-time notifications via WebSocket
5. Progressive Web App (PWA) support
6. Offline capability with IndexedDB
7. Advanced filtering and search
8. Customizable dashboards

## API Reference

See `/docs` (Swagger UI) or `/redoc` (ReDoc) for complete API documentation.

## Support

For issues or feature requests, check the GitHub repository or contact the development team.

---

**Last Updated**: 2024-12  
**Version**: 1.0.0  
**Status**: Ready for deployment

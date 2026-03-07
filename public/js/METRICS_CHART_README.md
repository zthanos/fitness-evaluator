# MetricsChart Component

## Overview

The `MetricsChart` component provides interactive visualization of body metrics data using Chart.js. It displays line charts for weight, body fat percentage, and circumference measurements with time range filtering capabilities.

**Requirements Implemented:** 6.1, 6.2, 6.3, 6.4, 6.6

## Features

### 1. Multiple Chart Types (Requirement 6.2)
- **Weight Trend Chart**: Displays weight measurements over time in kilograms
- **Body Fat Percentage Chart**: Shows body fat percentage trends
- **Circumference Measurements Chart**: Visualizes multiple circumference measurements (waist, etc.)

### 2. Time Range Selection (Requirement 6.3)
Interactive time range selector with the following options:
- **7 Days**: Last week of data
- **30 Days**: Last month of data
- **90 Days**: Last quarter of data
- **1 Year**: Last year of data
- **All Time**: Complete history

### 3. Interactive Tooltips (Requirement 6.4)
Hover over data points to see:
- Exact measurement value (with appropriate precision)
- Measurement date
- Metric type (for circumference charts)

### 4. Insufficient Data Handling (Requirement 6.6)
When fewer than 2 data points are available for a metric:
- Displays an informative message
- Shows an icon indicating no data
- Provides guidance on how many measurements are needed

### 5. Chart.js Integration (Requirement 6.1)
- Uses Chart.js for rendering
- Leverages `chart-config.js` utilities for consistent styling
- Applies design tokens for brand consistency
- Responsive sizing and smooth animations

## Usage

### Basic Implementation

```javascript
// Initialize the component
const metricsChart = new MetricsChart('container-id', apiClient);

// Render the charts
await metricsChart.render();
```

### With Custom API Client

```javascript
// Create custom API client
const customApi = new APIClient('https://api.example.com');

// Initialize with custom client
const metricsChart = new MetricsChart('charts-container', customApi);
await metricsChart.render();
```

### Updating Charts After New Data

```javascript
// After adding a new measurement
metricsForm.onSuccess(async (result) => {
    // Refresh charts with new data
    await metricsChart.update();
});
```

### Cleanup

```javascript
// Destroy charts when component is removed
metricsChart.destroy();
```

## API Requirements

The component expects the API client to provide a `listMetrics()` method that returns an array of metric objects:

```javascript
[
    {
        id: "metric-id",
        measurement_date: "2024-01-15",  // ISO date string
        weight: 75.5,                     // kg (required)
        body_fat_pct: 15.2,              // percentage (optional)
        measurements: {                   // optional
            waist_cm: 85.0,
            // ... other circumference measurements
        },
        created_at: "2024-01-15T10:30:00Z",
        updated_at: "2024-01-15T10:30:00Z"
    },
    // ... more metrics
]
```

## Component Structure

### HTML Structure

The component generates the following structure:

```html
<div id="container">
    <!-- Time Range Selector -->
    <div class="btn-group">
        <button data-range="7d">7 Days</button>
        <button data-range="30d">30 Days</button>
        <button data-range="90d">90 Days</button>
        <button data-range="1y">1 Year</button>
        <button data-range="all">All Time</button>
    </div>
    
    <!-- Charts Grid -->
    <div class="grid">
        <!-- Weight Chart -->
        <div class="card">
            <canvas id="weight-chart"></canvas>
        </div>
        
        <!-- Body Fat Chart -->
        <div class="card">
            <canvas id="bodyfat-chart"></canvas>
        </div>
        
        <!-- Circumference Chart -->
        <div class="card">
            <canvas id="circumference-chart"></canvas>
        </div>
    </div>
</div>
```

### Class Methods

#### Constructor
```javascript
constructor(containerId, apiClient = window.api)
```
- `containerId`: ID of the container element
- `apiClient`: API client instance (defaults to global `window.api`)

#### Public Methods

**`render()`**
- Initializes and renders the component
- Fetches data from API
- Renders UI and charts
- Returns: `Promise<void>`

**`setTimeRange(range)`**
- Changes the active time range
- Updates button states
- Re-renders charts with filtered data
- Parameters: `range` - One of: '7d', '30d', '90d', '1y', 'all'

**`update()`**
- Reloads data from API
- Re-renders all charts
- Use after adding new measurements
- Returns: `Promise<void>`

**`destroy()`**
- Destroys all Chart.js instances
- Cleans up resources
- Call before removing component from DOM

#### Private Methods

**`loadData()`**
- Fetches metrics from API
- Sorts data by date ascending

**`renderUI()`**
- Generates HTML structure
- Attaches event listeners

**`getFilteredData()`**
- Filters data based on current time range
- Returns: `Array` of filtered metrics

**`renderCharts()`**
- Renders all three chart types
- Handles insufficient data

**`renderWeightChart(data)`**
- Renders weight trend chart
- Shows message if < 2 data points

**`renderBodyFatChart(data)`**
- Renders body fat percentage chart
- Shows message if < 2 data points

**`renderCircumferenceChart(data)`**
- Renders circumference measurements chart
- Supports multiple measurement types
- Shows message if < 2 data points

**`renderError(message)`**
- Displays error alert

## Data Handling

### Time Range Filtering

The component filters data based on the selected time range:

```javascript
timeRanges = {
    '7d': 7,      // Last 7 days
    '30d': 30,    // Last 30 days
    '90d': 90,    // Last 90 days
    '1y': 365,    // Last 365 days
    'all': null   // All data (no filtering)
}
```

### Null Value Handling

The component gracefully handles missing data:
- Filters out null/undefined values before charting
- Displays "insufficient data" message when < 2 valid points
- Uses `spanGaps: true` for circumference charts to connect points with missing values

### Data Sorting

All data is sorted by `measurement_date` in ascending order before rendering to ensure proper chart display.

## Styling

The component uses:
- **DaisyUI**: For cards, buttons, and layout
- **Tailwind CSS**: For utility classes
- **Design Tokens**: From `design-tokens.css`
- **Chart Config**: From `chart-config.js` for consistent chart styling

### Chart Colors

- **Weight**: Primary color (vibrant purple/blue)
- **Body Fat**: Secondary color (vibrant pink)
- **Circumferences**: Auto-generated color palette

## Browser Compatibility

- Modern browsers with ES6+ support
- Chart.js 4.4.1+
- Requires `fetch` API support

## Testing

Run validation tests:

```bash
python validate_metrics_chart.py
```

Tests cover:
- Time range filtering logic
- Insufficient data detection
- Data sorting
- Null value handling
- Circumference measurement extraction

## Example Integration

See `public/metrics.html` for a complete integration example:

```javascript
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize metrics form
    const metricsForm = new MetricsForm('metrics-form-container');
    metricsForm.render();
    
    // Initialize metrics charts
    const metricsChart = new MetricsChart('metrics-charts-container');
    await metricsChart.render();
    
    // Refresh charts when new data is added
    metricsForm.onSuccess(async (result) => {
        await metricsChart.update();
    });
});
```

## Performance Considerations

- Charts render within 500ms for up to 365 data points (Requirement 6.5)
- Data is fetched once and cached in component state
- Only filtered data is passed to Chart.js for rendering
- Charts are destroyed and recreated when time range changes (prevents memory leaks)

## Accessibility

- Semantic HTML structure
- Keyboard-accessible time range buttons
- ARIA labels on interactive elements
- High contrast colors for readability
- Responsive design for all screen sizes

## Future Enhancements

Potential improvements for future iterations:
- Export chart as image
- Compare multiple metrics on same chart
- Trend line overlays
- Goal markers on charts
- Zoom and pan controls
- Custom date range picker

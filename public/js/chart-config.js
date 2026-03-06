/**
 * Chart.js Configuration Utilities
 * 
 * Provides reusable chart configurations with brand colors for the Fitness Platform.
 * Uses design tokens from design-tokens.css for consistent styling.
 * 
 * Requirements: 6
 */

/**
 * Brand color palette for charts
 * Energetic and motivating colors matching the Fitness Platform logo
 */
const ChartColors = {
  // Primary data colors - vibrant and energetic
  primary: '#570df8',      // Vibrant purple/blue
  secondary: '#f000b8',    // Vibrant pink
  accent: '#37cdbe',       // Teal/cyan
  
  // Trend colors
  positive: '#36d399',     // Green for positive trends
  negative: '#f87272',     // Red/orange for alerts
  warning: '#fbbd23',      // Yellow for warnings
  info: '#3abff8',         // Blue for info
  
  // Activity type colors
  run: '#ef4444',          // Red
  ride: '#3b82f6',         // Blue
  swim: '#06b6d4',         // Cyan
  strength: '#8b5cf6',     // Purple
  other: '#6b7280',        // Gray
  
  // Chart-specific colors
  grid: 'rgba(0, 0, 0, 0.1)',
  gridDark: 'rgba(255, 255, 255, 0.1)',
  tooltipBg: 'rgba(0, 0, 0, 0.8)',
  tooltipText: '#ffffff',
};

/**
 * Generate an array of colors for multi-dataset charts
 * @param {number} count - Number of colors needed
 * @returns {string[]} Array of color hex codes
 */
function generateColorPalette(count) {
  const baseColors = [
    ChartColors.primary,
    ChartColors.accent,
    ChartColors.secondary,
    ChartColors.positive,
    ChartColors.info,
    ChartColors.warning,
    ChartColors.strength,
    ChartColors.ride,
  ];
  
  const colors = [];
  for (let i = 0; i < count; i++) {
    colors.push(baseColors[i % baseColors.length]);
  }
  
  return colors;
}

/**
 * Get color with alpha transparency
 * @param {string} color - Hex color code
 * @param {number} alpha - Alpha value (0-1)
 * @returns {string} RGBA color string
 */
function colorWithAlpha(color, alpha) {
  // Convert hex to RGB
  const r = parseInt(color.slice(1, 3), 16);
  const g = parseInt(color.slice(3, 5), 16);
  const b = parseInt(color.slice(5, 7), 16);
  
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * Default Chart.js configuration
 * Provides consistent styling across all charts
 */
const defaultChartConfig = {
  responsive: true,
  maintainAspectRatio: true,
  aspectRatio: 2,
  interaction: {
    mode: 'index',
    intersect: false,
  },
  plugins: {
    legend: {
      display: true,
      position: 'top',
      labels: {
        usePointStyle: true,
        padding: 15,
        font: {
          size: 12,
          family: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
        },
      },
    },
    tooltip: {
      enabled: true,
      backgroundColor: ChartColors.tooltipBg,
      titleColor: ChartColors.tooltipText,
      bodyColor: ChartColors.tooltipText,
      borderColor: ChartColors.primary,
      borderWidth: 1,
      padding: 12,
      displayColors: true,
      callbacks: {
        // Default callbacks can be overridden
      },
    },
  },
  scales: {
    x: {
      grid: {
        display: true,
        color: ChartColors.grid,
        drawBorder: false,
      },
      ticks: {
        font: {
          size: 11,
        },
      },
    },
    y: {
      grid: {
        display: true,
        color: ChartColors.grid,
        drawBorder: false,
      },
      ticks: {
        font: {
          size: 11,
        },
      },
      beginAtZero: false,
    },
  },
};

/**
 * Create a line chart configuration for body metrics
 * @param {Object} options - Configuration options
 * @param {string} options.label - Dataset label
 * @param {string} options.color - Line color (defaults to primary)
 * @param {boolean} options.fill - Whether to fill area under line
 * @param {string} options.yAxisLabel - Y-axis label
 * @param {Function} options.tooltipCallback - Custom tooltip formatter
 * @returns {Object} Chart.js configuration object
 */
function createLineChartConfig(options = {}) {
  const {
    label = 'Metric',
    color = ChartColors.primary,
    fill = true,
    yAxisLabel = '',
    tooltipCallback = null,
  } = options;
  
  const config = JSON.parse(JSON.stringify(defaultChartConfig)); // Deep clone
  
  // Line-specific styling
  config.elements = {
    line: {
      tension: 0.4, // Smooth curves
      borderWidth: 3,
    },
    point: {
      radius: 4,
      hoverRadius: 6,
      hitRadius: 10,
    },
  };
  
  // Dataset template
  config.datasetDefaults = {
    label,
    borderColor: color,
    backgroundColor: fill ? colorWithAlpha(color, 0.1) : 'transparent',
    fill,
    pointBackgroundColor: color,
    pointBorderColor: '#fff',
    pointBorderWidth: 2,
    pointHoverBackgroundColor: '#fff',
    pointHoverBorderColor: color,
    pointHoverBorderWidth: 3,
  };
  
  // Y-axis label
  if (yAxisLabel) {
    config.scales.y.title = {
      display: true,
      text: yAxisLabel,
      font: {
        size: 12,
        weight: 'bold',
      },
    };
  }
  
  // Custom tooltip callback
  if (tooltipCallback) {
    config.plugins.tooltip.callbacks.label = tooltipCallback;
  }
  
  return config;
}

/**
 * Create a bar chart configuration
 * @param {Object} options - Configuration options
 * @param {string} options.label - Dataset label
 * @param {string|string[]} options.color - Bar color(s)
 * @param {string} options.yAxisLabel - Y-axis label
 * @param {Function} options.tooltipCallback - Custom tooltip formatter
 * @returns {Object} Chart.js configuration object
 */
function createBarChartConfig(options = {}) {
  const {
    label = 'Metric',
    color = ChartColors.primary,
    yAxisLabel = '',
    tooltipCallback = null,
  } = options;
  
  const config = JSON.parse(JSON.stringify(defaultChartConfig)); // Deep clone
  
  // Bar-specific styling
  config.elements = {
    bar: {
      borderWidth: 0,
      borderRadius: 4,
    },
  };
  
  // Dataset template
  config.datasetDefaults = {
    label,
    backgroundColor: Array.isArray(color) ? color : color,
    hoverBackgroundColor: Array.isArray(color) 
      ? color.map(c => colorWithAlpha(c, 0.8))
      : colorWithAlpha(color, 0.8),
  };
  
  // Y-axis label
  if (yAxisLabel) {
    config.scales.y.title = {
      display: true,
      text: yAxisLabel,
      font: {
        size: 12,
        weight: 'bold',
      },
    };
  }
  
  // Y-axis starts at zero for bar charts
  config.scales.y.beginAtZero = true;
  
  // Custom tooltip callback
  if (tooltipCallback) {
    config.plugins.tooltip.callbacks.label = tooltipCallback;
  }
  
  return config;
}

/**
 * Create a multi-line chart configuration for comparing metrics
 * @param {Object} options - Configuration options
 * @param {string[]} options.labels - Dataset labels
 * @param {string[]} options.colors - Line colors (auto-generated if not provided)
 * @param {string} options.yAxisLabel - Y-axis label
 * @returns {Object} Chart.js configuration object
 */
function createMultiLineChartConfig(options = {}) {
  const {
    labels = [],
    colors = null,
    yAxisLabel = '',
  } = options;
  
  const config = JSON.parse(JSON.stringify(defaultChartConfig)); // Deep clone
  
  // Generate colors if not provided
  const chartColors = colors || generateColorPalette(labels.length);
  
  // Line-specific styling
  config.elements = {
    line: {
      tension: 0.4,
      borderWidth: 2,
    },
    point: {
      radius: 3,
      hoverRadius: 5,
      hitRadius: 10,
    },
  };
  
  // Create dataset templates for each line
  config.datasetTemplates = labels.map((label, index) => ({
    label,
    borderColor: chartColors[index],
    backgroundColor: 'transparent',
    fill: false,
    pointBackgroundColor: chartColors[index],
    pointBorderColor: '#fff',
    pointBorderWidth: 2,
    pointHoverBackgroundColor: '#fff',
    pointHoverBorderColor: chartColors[index],
    pointHoverBorderWidth: 2,
  }));
  
  // Y-axis label
  if (yAxisLabel) {
    config.scales.y.title = {
      display: true,
      text: yAxisLabel,
      font: {
        size: 12,
        weight: 'bold',
      },
    };
  }
  
  return config;
}

/**
 * Format date for chart labels
 * @param {string|Date} date - Date to format
 * @param {string} format - Format type ('short', 'medium', 'long')
 * @returns {string} Formatted date string
 */
function formatDateLabel(date, format = 'short') {
  const d = new Date(date);
  
  const options = {
    short: { month: 'short', day: 'numeric' },
    medium: { month: 'short', day: 'numeric', year: 'numeric' },
    long: { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' },
  };
  
  return d.toLocaleDateString('en-US', options[format] || options.short);
}

/**
 * Create tooltip formatter for weight data
 * @param {Object} context - Chart.js tooltip context
 * @returns {string} Formatted tooltip label
 */
function weightTooltipFormatter(context) {
  const value = context.parsed.y;
  const date = context.label;
  return `${date}: ${value.toFixed(1)} kg`;
}

/**
 * Create tooltip formatter for body fat percentage
 * @param {Object} context - Chart.js tooltip context
 * @returns {string} Formatted tooltip label
 */
function bodyFatTooltipFormatter(context) {
  const value = context.parsed.y;
  const date = context.label;
  return `${date}: ${value.toFixed(1)}%`;
}

/**
 * Create tooltip formatter for circumference measurements
 * @param {Object} context - Chart.js tooltip context
 * @returns {string} Formatted tooltip label
 */
function circumferenceTooltipFormatter(context) {
  const value = context.parsed.y;
  const label = context.dataset.label;
  return `${label}: ${value.toFixed(1)} cm`;
}

/**
 * Detect dark theme and adjust chart colors
 * @returns {boolean} True if dark theme is active
 */
function isDarkTheme() {
  return document.documentElement.getAttribute('data-theme') === 'dark';
}

/**
 * Get grid color based on current theme
 * @returns {string} Grid color
 */
function getGridColor() {
  return isDarkTheme() ? ChartColors.gridDark : ChartColors.grid;
}

/**
 * Update chart colors for theme changes
 * @param {Chart} chart - Chart.js instance
 */
function updateChartTheme(chart) {
  const gridColor = getGridColor();
  
  if (chart.options.scales.x) {
    chart.options.scales.x.grid.color = gridColor;
  }
  
  if (chart.options.scales.y) {
    chart.options.scales.y.grid.color = gridColor;
  }
  
  chart.update();
}

// Export utilities
window.ChartConfig = {
  colors: ChartColors,
  generateColorPalette,
  colorWithAlpha,
  createLineChartConfig,
  createBarChartConfig,
  createMultiLineChartConfig,
  formatDateLabel,
  weightTooltipFormatter,
  bodyFatTooltipFormatter,
  circumferenceTooltipFormatter,
  isDarkTheme,
  getGridColor,
  updateChartTheme,
};

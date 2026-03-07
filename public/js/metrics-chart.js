/**
 * MetricsChart Component
 * 
 * Renders interactive line charts for body metrics with time range selection.
 * Uses Chart.js for visualization and chart-config.js for styling.
 * 
 * Requirements: 6.1, 6.2, 6.3, 6.4, 6.6
 */

class MetricsChart {
  /**
   * Create a MetricsChart instance
   * @param {string} containerId - ID of the container element
   * @param {APIClient} apiClient - API client instance for fetching data
   */
  constructor(containerId, apiClient) {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      throw new Error(`Container element with id "${containerId}" not found`);
    }
    
    // Use provided API client or fall back to global api instance
    this.api = apiClient || (typeof window !== 'undefined' && window.api) || null;
    
    if (!this.api) {
      throw new Error('API client is required. Please provide an APIClient instance or ensure window.api is available.');
    }
    
    this.charts = {}; // Store Chart.js instances
    this.metricsData = []; // Raw metrics data from API
    this.currentTimeRange = 'all'; // Default time range
    
    // Time range configurations (in days)
    this.timeRanges = {
      '7d': 7,
      '30d': 30,
      '90d': 90,
      '1y': 365,
      'all': null, // null means all data
    };
  }
  
  /**
   * Initialize and render the component
   * Requirements: 6.1, 6.2, 7.4, 7.5
   */
  async render() {
    try {
      // Fetch metrics data
      await this.loadData();
      
      // Render UI structure
      this.renderUI();
      
      // Render charts
      this.renderCharts();
      
      // Render trend analysis (Requirements 7.4, 7.5)
      await this.renderTrendAnalysis();
    } catch (error) {
      console.error('Error rendering metrics charts:', error);
      this.renderError(error.message);
    }
  }
  
  /**
   * Load metrics data from API
   */
  async loadData() {
    this.metricsData = await this.api.listMetrics();
    
    // Sort by date ascending for proper chart display
    this.metricsData.sort((a, b) => 
      new Date(a.measurement_date) - new Date(b.measurement_date)
    );
  }
  
  /**
   * Render the UI structure with time range selector
   * Requirements: 6.3, 7.4
   */
  renderUI() {
    this.container.innerHTML = `
      <!-- Time Range Selector -->
      <div class="flex justify-end mb-4">
        <div class="btn-group">
          <button class="btn btn-sm ${this.currentTimeRange === '7d' ? 'btn-active' : ''}" data-range="7d">7 Days</button>
          <button class="btn btn-sm ${this.currentTimeRange === '30d' ? 'btn-active' : ''}" data-range="30d">30 Days</button>
          <button class="btn btn-sm ${this.currentTimeRange === '90d' ? 'btn-active' : ''}" data-range="90d">90 Days</button>
          <button class="btn btn-sm ${this.currentTimeRange === '1y' ? 'btn-active' : ''}" data-range="1y">1 Year</button>
          <button class="btn btn-sm ${this.currentTimeRange === 'all' ? 'btn-active' : ''}" data-range="all">All Time</button>
        </div>
      </div>
      
      <!-- AI Trend Analysis Section (Requirements 7.4, 7.5) -->
      <div id="trend-analysis-container" class="mb-6">
        <!-- Trend analysis will be rendered here -->
      </div>
      
      <!-- Charts Grid - Responsive: 1 column on mobile, 3 columns on desktop -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Weight Chart -->
        <div class="card bg-base-100 border border-base-300">
          <div class="card-body">
            <h3 class="card-title text-lg">Weight Trend</h3>
            <div id="weight-chart-wrapper" class="min-h-[300px] flex items-center justify-center">
              <canvas id="weight-chart"></canvas>
            </div>
          </div>
        </div>
        
        <!-- Body Fat Percentage Chart -->
        <div class="card bg-base-100 border border-base-300">
          <div class="card-body">
            <h3 class="card-title text-lg">Body Fat %</h3>
            <div id="bodyfat-chart-wrapper" class="min-h-[300px] flex items-center justify-center">
              <canvas id="bodyfat-chart"></canvas>
            </div>
          </div>
        </div>
        
        <!-- Circumference Measurements Chart -->
        <div class="card bg-base-100 border border-base-300">
          <div class="card-body">
            <h3 class="card-title text-lg">Circumferences</h3>
            <div id="circumference-chart-wrapper" class="min-h-[300px] flex items-center justify-center">
              <canvas id="circumference-chart"></canvas>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Attach event listeners to time range buttons
    const buttons = this.container.querySelectorAll('[data-range]');
    buttons.forEach(button => {
      button.addEventListener('click', (e) => {
        const range = e.target.dataset.range;
        this.setTimeRange(range);
      });
    });
  }
  
  /**
   * Set the time range and update charts
   * Requirements: 6.3
   * @param {string} range - Time range key ('7d', '30d', '90d', '1y', 'all')
   */
  setTimeRange(range) {
    if (this.currentTimeRange === range) return;
    
    this.currentTimeRange = range;
    
    // Update button states
    const buttons = this.container.querySelectorAll('[data-range]');
    buttons.forEach(button => {
      if (button.dataset.range === range) {
        button.classList.add('btn-active');
      } else {
        button.classList.remove('btn-active');
      }
    });
    
    // Re-render charts with new time range
    this.renderCharts();
  }
  
  /**
   * Filter metrics data based on current time range
   * @returns {Array} Filtered metrics data
   */
  getFilteredData() {
    const days = this.timeRanges[this.currentTimeRange];
    
    if (days === null) {
      // Return all data
      return this.metricsData;
    }
    
    // Calculate cutoff date
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - days);
    
    // Filter data
    return this.metricsData.filter(metric => 
      new Date(metric.measurement_date) >= cutoffDate
    );
  }
  
  /**
   * Render all charts
   * Requirements: 6.1, 6.2, 6.4, 6.6
   */
  renderCharts() {
    const filteredData = this.getFilteredData();
    
    // Render weight chart
    this.renderWeightChart(filteredData);
    
    // Render body fat chart
    this.renderBodyFatChart(filteredData);
    
    // Render circumference chart
    this.renderCircumferenceChart(filteredData);
  }
  
  /**
   * Render weight trend chart
   * Requirements: 6.1, 6.2, 6.4, 6.6
   * @param {Array} data - Filtered metrics data
   */
  renderWeightChart(data) {
    const wrapper = document.getElementById('weight-chart-wrapper');
    const canvas = document.getElementById('weight-chart');
    
    // Check for sufficient data (Requirement 6.6)
    const weightData = data.filter(m => m.weight !== null && m.weight !== undefined);
    
    if (weightData.length < 2) {
      wrapper.innerHTML = `
        <div class="text-center text-base-content/70 py-8">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 mx-auto mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p class="text-lg font-medium">Not enough data to display weight trend</p>
          <p class="text-sm mt-2">Log at least 2 measurements to see your progress</p>
        </div>
      `;
      return;
    }
    
    // Destroy existing chart if it exists
    if (this.charts.weight) {
      this.charts.weight.destroy();
    }
    
    // Prepare chart data
    const labels = weightData.map(m => 
      window.ChartConfig.formatDateLabel(m.measurement_date, 'short')
    );
    const values = weightData.map(m => m.weight);
    
    // Create chart configuration (Requirement 6.1)
    const config = window.ChartConfig.createLineChartConfig({
      label: 'Weight',
      color: window.ChartConfig.colors.primary,
      fill: true,
      yAxisLabel: 'Weight (kg)',
    });
    
    // Customize tooltip (Requirement 6.4)
    config.plugins.tooltip.callbacks.label = (context) => {
      const value = context.parsed.y;
      const date = weightData[context.dataIndex].measurement_date;
      return `${date}: ${value.toFixed(1)} kg`;
    };
    
    // Create chart
    const ctx = canvas.getContext('2d');
    this.charts.weight = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          ...config.datasetDefaults,
          data: values,
        }],
      },
      options: config,
    });
  }
  
  /**
   * Render body fat percentage chart
   * Requirements: 6.1, 6.2, 6.4, 6.6
   * @param {Array} data - Filtered metrics data
   */
  renderBodyFatChart(data) {
    const wrapper = document.getElementById('bodyfat-chart-wrapper');
    const canvas = document.getElementById('bodyfat-chart');
    
    // Check for sufficient data (Requirement 6.6)
    const bodyFatData = data.filter(m => m.body_fat_pct !== null && m.body_fat_pct !== undefined);
    
    if (bodyFatData.length < 2) {
      wrapper.innerHTML = `
        <div class="text-center text-base-content/70 py-8">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 mx-auto mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p class="text-lg font-medium">Not enough data to display body fat trend</p>
          <p class="text-sm mt-2">Log at least 2 measurements with body fat percentage to see your progress</p>
        </div>
      `;
      return;
    }
    
    // Destroy existing chart if it exists
    if (this.charts.bodyFat) {
      this.charts.bodyFat.destroy();
    }
    
    // Prepare chart data
    const labels = bodyFatData.map(m => 
      window.ChartConfig.formatDateLabel(m.measurement_date, 'short')
    );
    const values = bodyFatData.map(m => m.body_fat_pct);
    
    // Create chart configuration (Requirement 6.1)
    const config = window.ChartConfig.createLineChartConfig({
      label: 'Body Fat %',
      color: window.ChartConfig.colors.secondary,
      fill: true,
      yAxisLabel: 'Body Fat (%)',
    });
    
    // Customize tooltip (Requirement 6.4)
    config.plugins.tooltip.callbacks.label = (context) => {
      const value = context.parsed.y;
      const date = bodyFatData[context.dataIndex].measurement_date;
      return `${date}: ${value.toFixed(1)}%`;
    };
    
    // Create chart
    const ctx = canvas.getContext('2d');
    this.charts.bodyFat = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          ...config.datasetDefaults,
          data: values,
        }],
      },
      options: config,
    });
  }
  
  /**
   * Render circumference measurements chart
   * Requirements: 6.1, 6.2, 6.4, 6.6
   * @param {Array} data - Filtered metrics data
   */
  renderCircumferenceChart(data) {
    const wrapper = document.getElementById('circumference-chart-wrapper');
    const canvas = document.getElementById('circumference-chart');
    
    // Extract circumference data
    const circumferenceData = data.filter(m => 
      m.measurements && Object.keys(m.measurements).length > 0
    );
    
    // Check for sufficient data (Requirement 6.6)
    if (circumferenceData.length < 2) {
      wrapper.innerHTML = `
        <div class="text-center text-base-content/70 py-8">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 mx-auto mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p class="text-lg font-medium">Not enough data to display circumference trends</p>
          <p class="text-sm mt-2">Log at least 2 measurements with circumference data to see your progress</p>
        </div>
      `;
      return;
    }
    
    // Destroy existing chart if it exists
    if (this.charts.circumference) {
      this.charts.circumference.destroy();
    }
    
    // Identify all measurement types
    const measurementTypes = new Set();
    circumferenceData.forEach(m => {
      if (m.measurements) {
        Object.keys(m.measurements).forEach(key => measurementTypes.add(key));
      }
    });
    
    if (measurementTypes.size === 0) {
      wrapper.innerHTML = `
        <div class="text-center text-base-content/70 py-8">
          <p class="text-lg font-medium">No circumference measurements available</p>
        </div>
      `;
      return;
    }
    
    // Prepare chart data
    const labels = circumferenceData.map(m => 
      window.ChartConfig.formatDateLabel(m.measurement_date, 'short')
    );
    
    // Create datasets for each measurement type
    const colors = window.ChartConfig.generateColorPalette(measurementTypes.size);
    const datasets = [];
    let colorIndex = 0;
    
    measurementTypes.forEach(type => {
      const values = circumferenceData.map(m => 
        m.measurements && m.measurements[type] !== undefined ? m.measurements[type] : null
      );
      
      // Only add dataset if it has at least some data
      if (values.some(v => v !== null)) {
        const label = type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        
        datasets.push({
          label: label,
          data: values,
          borderColor: colors[colorIndex],
          backgroundColor: 'transparent',
          fill: false,
          pointBackgroundColor: colors[colorIndex],
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          pointHoverBackgroundColor: '#fff',
          pointHoverBorderColor: colors[colorIndex],
          pointHoverBorderWidth: 3,
          tension: 0.4,
          spanGaps: true, // Connect points even if there are null values
        });
        
        colorIndex++;
      }
    });
    
    // Create chart configuration (Requirement 6.1)
    const config = window.ChartConfig.createLineChartConfig({
      yAxisLabel: 'Circumference (cm)',
    });
    
    // Customize tooltip (Requirement 6.4)
    config.plugins.tooltip.callbacks.label = (context) => {
      const value = context.parsed.y;
      const label = context.dataset.label;
      const date = circumferenceData[context.dataIndex].measurement_date;
      return `${label}: ${value.toFixed(1)} cm (${date})`;
    };
    
    // Create chart
    const ctx = canvas.getContext('2d');
    this.charts.circumference = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: datasets,
      },
      options: config,
    });
  }
  
  /**
   * Render error message
   * @param {string} message - Error message to display
   */
  renderError(message) {
    this.container.innerHTML = `
      <div class="alert alert-error">
        <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>Error loading metrics charts: ${message}</span>
      </div>
    `;
  }
  
  /**
   * Render AI-powered weight trend analysis
   * Requirements: 7.4, 7.5, 7.6
   */
  async renderTrendAnalysis() {
    const container = document.getElementById('trend-analysis-container');
    
    if (!container) {
      console.warn('Trend analysis container not found');
      return;
    }
    
    // Check if we have enough data (at least 4 weeks)
    if (this.metricsData.length < 4) {
      // Don't show anything if insufficient data
      container.innerHTML = '';
      return;
    }
    
    // Check time span
    const sortedData = [...this.metricsData].sort((a, b) => 
      new Date(a.measurement_date) - new Date(b.measurement_date)
    );
    const firstDate = new Date(sortedData[0].measurement_date);
    const lastDate = new Date(sortedData[sortedData.length - 1].measurement_date);
    const daysElapsed = (lastDate - firstDate) / (1000 * 60 * 60 * 24);
    
    if (daysElapsed < 28) {
      // Don't show anything if data doesn't span 4 weeks
      container.innerHTML = '';
      return;
    }
    
    // Show loading state
    container.innerHTML = `
      <div class="card bg-gradient-to-br from-primary/10 to-secondary/10 border border-primary/20">
        <div class="card-body">
          <div class="flex items-center gap-3">
            <span class="loading loading-spinner loading-md text-primary"></span>
            <h3 class="card-title text-lg">Generating AI Weight Trend Analysis...</h3>
          </div>
        </div>
      </div>
    `;
    
    try {
      // Fetch trend analysis from API (Requirements 7.4, 7.5)
      const analysis = await this.api.getTrendAnalysis();
      
      // Determine trend icon and color
      let trendIcon = '📊';
      let trendColorClass = 'text-info';
      
      if (analysis.trend_direction === 'increasing') {
        trendIcon = '📈';
        trendColorClass = 'text-success';
      } else if (analysis.trend_direction === 'decreasing') {
        trendIcon = '📉';
        trendColorClass = 'text-warning';
      }
      
      // Determine confidence badge color
      let confidenceBadgeClass = 'badge-info';
      if (analysis.confidence_level === 'high') {
        confidenceBadgeClass = 'badge-success';
      } else if (analysis.confidence_level === 'low') {
        confidenceBadgeClass = 'badge-warning';
      }
      
      // Render analysis (Requirement 7.4)
      container.innerHTML = `
        <div class="card bg-gradient-to-br from-primary/10 to-secondary/10 border border-primary/20">
          <div class="card-body">
            <div class="flex items-start justify-between mb-4">
              <div class="flex items-center gap-3">
                <span class="text-4xl">${trendIcon}</span>
                <div>
                  <h3 class="card-title text-lg">AI Weight Trend Analysis</h3>
                  <div class="flex gap-2 mt-1">
                    <span class="badge ${confidenceBadgeClass} badge-sm">
                      ${analysis.confidence_level} confidence
                    </span>
                    <span class="badge badge-ghost badge-sm">
                      ${analysis.data_points_analyzed} measurements
                    </span>
                  </div>
                </div>
              </div>
              <button 
                class="btn btn-sm btn-ghost btn-circle" 
                onclick="document.getElementById('trend-analysis-container').querySelector('.card').remove()"
                title="Dismiss analysis"
              >
                ✕
              </button>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div class="stat bg-base-100 rounded-lg p-4">
                <div class="stat-title">Weekly Change Rate</div>
                <div class="stat-value text-2xl ${trendColorClass}">
                  ${analysis.weekly_change_rate >= 0 ? '+' : ''}${analysis.weekly_change_rate.toFixed(3)} kg/week
                </div>
                <div class="stat-desc capitalize">${analysis.trend_direction}</div>
              </div>
              
              <div class="stat bg-base-100 rounded-lg p-4">
                <div class="stat-title">Goal Alignment</div>
                <div class="stat-desc text-sm mt-2">${analysis.goal_alignment}</div>
              </div>
            </div>
            
            <div class="space-y-3">
              <div>
                <h4 class="font-semibold text-sm mb-2">📝 Summary</h4>
                <p class="text-sm text-base-content/80">${analysis.summary}</p>
              </div>
              
              <div>
                <h4 class="font-semibold text-sm mb-2">💡 Recommendations</h4>
                <p class="text-sm text-base-content/80">${analysis.recommendations}</p>
              </div>
            </div>
            
            ${analysis.error ? `
              <div class="alert alert-warning mt-4">
                <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span class="text-sm">Note: ${analysis.error}</span>
              </div>
            ` : ''}
          </div>
        </div>
      `;
      
    } catch (error) {
      // Handle generation failures gracefully (Requirement 7.6)
      console.error('Error generating trend analysis:', error);
      
      // Check if it's an insufficient data error
      if (error.message && error.message.includes('At least 4 weeks')) {
        // Don't show anything for insufficient data
        container.innerHTML = '';
      } else {
        // Show error message for other failures
        container.innerHTML = `
          <div class="alert alert-info">
            <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <div class="font-semibold">AI Trend Analysis Unavailable</div>
              <div class="text-sm">Unable to generate trend analysis at this time. Continue tracking your metrics.</div>
            </div>
          </div>
        `;
      }
    }
  }
  
  /**
   * Update charts with new data
   * Call this method after new metrics are added
   * Requirements: 7.5
   */
  async update() {
    await this.loadData();
    this.renderCharts();
    // Regenerate trend analysis when new data is added (Requirement 7.5)
    await this.renderTrendAnalysis();
  }
  
  /**
   * Destroy all charts and clean up
   */
  destroy() {
    Object.values(this.charts).forEach(chart => {
      if (chart) chart.destroy();
    });
    this.charts = {};
  }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
  window.MetricsChart = MetricsChart;
}

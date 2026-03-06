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
   * Requirements: 6.1, 6.2
   */
  async render() {
    try {
      // Fetch metrics data
      await this.loadData();
      
      // Render UI structure
      this.renderUI();
      
      // Render charts
      this.renderCharts();
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
   * Requirements: 6.3
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
   * Update charts with new data
   * Call this method after new metrics are added
   */
  async update() {
    await this.loadData();
    this.renderCharts();
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

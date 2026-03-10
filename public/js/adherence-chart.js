/**
 * AdherenceChart Component
 * Renders line chart showing weekly adherence percentages
 * Requirement: 13.5
 */

class AdherenceChart {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      throw new Error(`Container with id "${containerId}" not found`);
    }
    
    this.data = options.data || [];
    this.overallAdherence = options.overallAdherence || 0;
    this.chart = null;
  }

  /**
   * Render the adherence chart
   */
  render() {
    if (this.data.length === 0) {
      this.renderEmptyState();
      return;
    }

    // Find canvas element
    const canvas = this.container.querySelector('canvas');
    if (!canvas) {
      console.error('Canvas element not found in container');
      return;
    }

    // Destroy existing chart if it exists
    if (this.chart) {
      this.chart.destroy();
    }

    // Prepare chart data
    const labels = this.data.map(d => `Week ${d.week}`);
    const values = this.data.map(d => d.adherence);

    // Create chart configuration using ChartConfig utility
    const config = window.ChartConfig.createLineChartConfig({
      label: 'Weekly Adherence',
      color: window.ChartConfig.colors.primary,
      fill: true,
      yAxisLabel: 'Adherence (%)',
    });

    // Customize for adherence data
    config.scales.y.min = 0;
    config.scales.y.max = 100;
    config.scales.y.ticks.callback = (value) => `${value}%`;

    // Add reference line for overall adherence
    config.plugins.annotation = {
      annotations: {
        overallLine: {
          type: 'line',
          yMin: this.overallAdherence,
          yMax: this.overallAdherence,
          borderColor: window.ChartConfig.colors.secondary,
          borderWidth: 2,
          borderDash: [5, 5],
          label: {
            display: true,
            content: `Overall: ${this.overallAdherence.toFixed(1)}%`,
            position: 'end',
            backgroundColor: window.ChartConfig.colors.secondary,
            color: '#fff',
            font: {
              size: 11,
              weight: 'bold'
            }
          }
        }
      }
    };

    // Customize tooltip
    config.plugins.tooltip.callbacks.label = (context) => {
      const value = context.parsed.y;
      return `Adherence: ${value.toFixed(1)}%`;
    };

    // Add color zones based on adherence levels
    const backgroundColors = values.map(v => {
      if (v >= 80) return window.ChartConfig.colorWithAlpha(window.ChartConfig.colors.positive, 0.2);
      if (v >= 60) return window.ChartConfig.colorWithAlpha(window.ChartConfig.colors.warning, 0.2);
      return window.ChartConfig.colorWithAlpha(window.ChartConfig.colors.negative, 0.2);
    });

    // Create chart
    const ctx = canvas.getContext('2d');
    this.chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          ...config.datasetDefaults,
          data: values,
          segment: {
            borderColor: (ctx) => {
              const value = ctx.p1.parsed.y;
              if (value >= 80) return window.ChartConfig.colors.positive;
              if (value >= 60) return window.ChartConfig.colors.warning;
              return window.ChartConfig.colors.negative;
            }
          }
        }]
      },
      options: config
    });
  }

  /**
   * Render empty state when no data available
   */
  renderEmptyState() {
    this.container.innerHTML = `
      <div class="text-center text-base-content/60 py-8">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 mx-auto mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <p class="text-lg font-medium">No adherence data available</p>
        <p class="text-sm mt-2">Complete some sessions to see your adherence trend</p>
      </div>
    `;
  }

  /**
   * Update chart with new data
   */
  update(data, overallAdherence) {
    this.data = data;
    this.overallAdherence = overallAdherence;
    this.render();
  }

  /**
   * Destroy chart and clean up
   */
  destroy() {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }
}

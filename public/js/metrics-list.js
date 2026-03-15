/**
 * MetricsList Component
 * Displays body metrics with inline editing functionality
 * Requirements: 5.4, 5.5, 5.6
 */

class MetricsList {
  constructor(containerId, extendedMode = false) {
    this.container = document.getElementById(containerId);
    this.metrics = [];
    this.editingState = {}; // Track which fields are being edited
    this.extendedMode = extendedMode;
    
    // Validation rules (same as MetricsForm - Requirement 5.2, 5.3)
    this.validationRules = {
      weight: { min: 30, max: 300, label: 'Weight' },
      body_fat_pct: { min: 3, max: 60, label: 'Body Fat %' },
      sleep_avg_hrs: { min: 0, max: 24, label: 'Sleep' },
      rhr_bpm: { min: 30, max: 220, label: 'RHR' },
      energy_level_avg: { min: 1, max: 10, label: 'Energy Level' }
    };
  }

  /**
   * Set extended mode
   */
  setExtendedMode(enabled) {
    this.extendedMode = enabled;
  }

  /**
   * Load and render metrics
   */
  async load() {
    try {
      this.metrics = await api.listMetrics();
      this.render();
    } catch (error) {
      console.error('Error loading metrics:', error);
      this.showError('Failed to load measurements');
    }
  }

  /**
   * Render the metrics list (Requirement 5.4: reverse chronological order)
   */
  render() {
    if (!this.container) {
      console.error('Container not found');
      return;
    }

    if (this.metrics.length === 0) {
      this.container.innerHTML = `
        <div class="text-center py-8 text-base-content/60">
          <p>No measurements yet. Add your first entry above!</p>
        </div>
      `;
      return;
    }

    // Sort by date descending
    const sortedMetrics = [...this.metrics].sort((a, b) => 
      new Date(b.measurement_date) - new Date(a.measurement_date)
    );

    const metricsHtml = sortedMetrics.map(metric => this.renderMetricRow(metric)).join('');

    const headers = this.extendedMode ? `
      <tr>
        <th>Date</th>
        <th>Weight (kg)</th>
        <th>Body Fat (%)</th>
        <th>Waist (cm)</th>
        <th>Sleep (hrs)</th>
        <th>RHR (bpm)</th>
        <th>Energy (1-10)</th>
      </tr>
    ` : `
      <tr>
        <th>Date</th>
        <th>Weight (kg)</th>
        <th>Body Fat (%)</th>
        <th>Waist (cm)</th>
      </tr>
    `;

    this.container.innerHTML = `
      <div class="overflow-x-auto">
        <table class="table table-zebra w-full">
          <thead>
            ${headers}
          </thead>
          <tbody>
            ${metricsHtml}
          </tbody>
        </table>
      </div>
    `;

    this.attachEventListeners();
  }

  /**
   * Render a single metric row
   */
  renderMetricRow(metric) {
    const metricId = metric.id;
    const isEditing = this.editingState[metricId];
    const canEdit = this.canEdit(metric);

    const basicCells = `
      <td class="font-semibold">${this.formatDate(metric.measurement_date)}</td>
      <td>${this.renderEditableField(metricId, 'weight', metric.weight, isEditing, canEdit)}</td>
      <td>${this.renderEditableField(metricId, 'body_fat_pct', metric.body_fat_pct, isEditing, canEdit)}</td>
      <td>${this.renderEditableField(metricId, 'waist_cm', metric.measurements?.waist_cm, isEditing, canEdit)}</td>
    `;

    const extendedCells = this.extendedMode ? `
      <td>${this.renderEditableField(metricId, 'sleep_avg_hrs', metric.measurements?.sleep_avg_hrs, isEditing, canEdit)}</td>
      <td>${this.renderEditableField(metricId, 'rhr_bpm', metric.measurements?.rhr_bpm, isEditing, canEdit, 'number')}</td>
      <td>${this.renderEditableField(metricId, 'energy_level_avg', metric.measurements?.energy_level_avg, isEditing, canEdit)}</td>
    ` : '';

    return `
      <tr data-metric-id="${metricId}">
        ${basicCells}${extendedCells}
      </tr>
    `;
  }

  /**
   * Check if metric can be edited (Requirement 5.6: within 24 hours)
   */
  canEdit(metric) {
    if (!metric.created_at) return false;
    
    const createdAt = new Date(metric.created_at);
    const now = new Date();
    const hoursSinceCreation = (now - createdAt) / (1000 * 60 * 60);
    
    return hoursSinceCreation <= 24;
  }

  /**
   * Render an editable field
   */
  renderEditableField(metricId, fieldName, value, isEditing, canEdit, type = 'number') {
    const editKey = `${metricId}-${fieldName}`;
    const displayValue = value !== null && value !== undefined ? 
      (type === 'number' ? Number(value).toFixed(1) : value) : '--';
    
    if (isEditing && isEditing.field === fieldName) {
      // Show input with save/cancel buttons
      return `
        <div class="flex items-center gap-2">
          <input 
            type="${type}" 
            class="input input-sm input-bordered w-24"
            id="edit-${editKey}"
            value="${value || ''}"
            ${type === 'number' ? 'step="0.1"' : ''}
          />
          <button 
            class="btn btn-xs btn-success"
            data-action="save"
            data-metric-id="${metricId}"
            data-field="${fieldName}"
            aria-label="Save"
          >
            ✓
          </button>
          <button 
            class="btn btn-xs btn-ghost"
            data-action="cancel"
            data-metric-id="${metricId}"
            data-field="${fieldName}"
            aria-label="Cancel"
          >
            ✕
          </button>
        </div>
        <div class="text-xs text-error mt-1" id="error-${editKey}"></div>
      `;
    }

    // Show clickable value (only if editable)
    if (canEdit) {
      return `
        <span 
          class="cursor-pointer hover:bg-base-200 px-2 py-1 rounded inline-block"
          data-action="edit"
          data-metric-id="${metricId}"
          data-field="${fieldName}"
          tabindex="0"
          role="button"
          aria-label="Click to edit ${fieldName}"
        >
          ${displayValue}
        </span>
      `;
    } else {
      // Not editable (older than 24 hours)
      return `<span class="text-base-content/70">${displayValue}</span>`;
    }
  }

  /**
   * Attach event listeners for inline editing
   */
  attachEventListeners() {
    this.container.addEventListener('click', (e) => {
      const action = e.target.dataset.action;
      const metricId = e.target.dataset.metricId;
      const field = e.target.dataset.field;

      if (action === 'edit') {
        this.enableInlineEdit(metricId, field);
      } else if (action === 'save') {
        this.saveEdit(metricId, field);
      } else if (action === 'cancel') {
        this.cancelEdit(metricId, field);
      }
    });

    // Support keyboard navigation (Enter to edit)
    this.container.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.dataset.action === 'edit') {
        const metricId = e.target.dataset.metricId;
        const field = e.target.dataset.field;
        this.enableInlineEdit(metricId, field);
      }
    });
  }

  /**
   * Enable inline editing for a field
   */
  enableInlineEdit(metricId, field) {
    const metric = this.metrics.find(m => m.id === metricId);
    if (!metric) return;

    // Check if metric can be edited (Requirement 5.6)
    if (!this.canEdit(metric)) {
      alert('Metrics can only be edited within 24 hours of creation');
      return;
    }

    // Get current value based on field
    let originalValue;
    if (field === 'weight' || field === 'body_fat_pct') {
      originalValue = metric[field];
    } else if (field === 'waist_cm' || field === 'sleep_avg_hrs' || field === 'rhr_bpm' || field === 'energy_level_avg') {
      originalValue = metric.measurements?.[field];
    }

    // Store original value for cancel operation
    this.editingState[metricId] = {
      field: field,
      originalValue: originalValue
    };

    this.render();

    // Focus the input field
    const editKey = `${metricId}-${field}`;
    const input = document.getElementById(`edit-${editKey}`);
    if (input) {
      input.focus();
      input.select();
    }
  }

  /**
   * Save edited value (Requirement 5.6: validate and update)
   */
  async saveEdit(metricId, field) {
    const editKey = `${metricId}-${field}`;
    const input = document.getElementById(`edit-${editKey}`);
    const errorElement = document.getElementById(`error-${editKey}`);
    
    if (!input) return;

    const newValue = input.value.trim();

    // Clear previous errors
    if (errorElement) {
      errorElement.textContent = '';
    }

    // Validate the new value
    const validationError = this.validateField(field, newValue);
    if (validationError) {
      if (errorElement) {
        errorElement.textContent = validationError;
      }
      return;
    }

    // Show loading state
    const saveBtn = input.nextElementSibling;
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="loading loading-spinner loading-xs"></span>';
    }

    try {
      // Get the metric and prepare update
      const metric = this.metrics.find(m => m.id === metricId);
      if (!metric) throw new Error('Metric not found');

      // Prepare update data
      const updateData = {
        measurements: { ...metric.measurements }
      };

      // Update the specific field
      if (field === 'weight') {
        updateData.weight = newValue ? parseFloat(newValue) : null;
      } else if (field === 'body_fat_pct') {
        updateData.body_fat_pct = newValue ? parseFloat(newValue) : null;
      } else if (field === 'waist_cm' || field === 'sleep_avg_hrs' || field === 'energy_level_avg') {
        updateData.measurements[field] = newValue ? parseFloat(newValue) : null;
      } else if (field === 'rhr_bpm') {
        updateData.measurements[field] = newValue ? parseInt(newValue) : null;
      }

      // Call API to update
      const updatedMetric = await api.updateMetric(metricId, updateData);

      // Update local state
      const metricIndex = this.metrics.findIndex(m => m.id === metricId);
      if (metricIndex !== -1) {
        this.metrics[metricIndex] = updatedMetric;
      }

      // Clear editing state
      delete this.editingState[metricId];

      // Re-render to show updated value
      this.render();

      // Show success feedback briefly
      this.showSuccessFeedback(metricId);

    } catch (error) {
      console.error('Error saving edit:', error);
      
      // Show error message
      if (errorElement) {
        errorElement.textContent = error.message || 'Failed to save. Please try again.';
      }

      // Re-enable save button
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '✓';
      }
    }
  }

  /**
   * Cancel edit and restore original value
   */
  cancelEdit(metricId) {
    // Clear editing state
    delete this.editingState[metricId];

    // Re-render
    this.render();
  }

  /**
   * Validate field value (Requirement 5.2, 5.3)
   */
  validateField(fieldName, value) {
    // Empty values are allowed for optional fields
    if (!value || value === '') {
      // Weight is required
      if (fieldName === 'weight') {
        return 'Weight is required';
      }
      return null;
    }

    const rules = this.validationRules[fieldName];
    if (!rules) {
      // For fields without specific rules (like waist_cm), just check if it's a valid number
      const numValue = parseFloat(value);
      if (isNaN(numValue)) {
        return 'Must be a valid number';
      }
      if (numValue < 0) {
        return 'Must be a positive number';
      }
      return null;
    }

    const numValue = parseFloat(value);

    // Check if value is a valid number
    if (isNaN(numValue)) {
      return `${rules.label} must be a valid number`;
    }

    // Check minimum value
    if (numValue < rules.min) {
      return `${rules.label} must be at least ${rules.min}${fieldName === 'weight' ? 'kg' : '%'}`;
    }

    // Check maximum value
    if (numValue > rules.max) {
      return `${rules.label} must not exceed ${rules.max}${fieldName === 'weight' ? 'kg' : '%'}`;
    }

    return null;
  }

  /**
   * Show success feedback briefly
   */
  showSuccessFeedback(metricId) {
    const row = this.container.querySelector(`tr[data-metric-id="${metricId}"]`);
    if (row) {
      row.classList.add('bg-success', 'bg-opacity-20');
      setTimeout(() => {
        row.classList.remove('bg-success', 'bg-opacity-20');
      }, 1000);
    }
  }

  /**
   * Show error message
   */
  showError(message) {
    this.container.innerHTML = `
      <div class="alert alert-error">
        <span>${message}</span>
      </div>
    `;
  }

  /**
   * Format date for display
   */
  formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      weekday: 'short', 
      year: 'numeric',
      month: 'short', 
      day: 'numeric' 
    });
  }
}
export { MetricsList };
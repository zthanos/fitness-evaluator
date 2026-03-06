/**
 * DailyLogList Component
 * Displays daily logs with inline editing functionality
 * Requirements: 8.7, 9.1, 9.2, 9.3, 9.4, 9.5
 */

class DailyLogList {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.logs = [];
    this.editingState = {}; // Track which fields are being edited
    
    // Validation rules (same as DailyLogForm - Requirement 9.3)
    this.validationRules = {
      calories_in: { min: 0, max: 10000, label: 'Calories' },
      protein_g: { min: 0, max: 1000, label: 'Protein' },
      carbs_g: { min: 0, max: 1000, label: 'Carbs' },
      fat_g: { min: 0, max: 1000, label: 'Fats' },
      adherence_score: { min: 0, max: 100, label: 'Adherence' }
    };
  }

  /**
   * Load and render logs
   */
  async load() {
    try {
      const response = await api.listDailyLogs();
      this.logs = response.logs || response; // Handle both paginated and array responses
      this.render();
    } catch (error) {
      console.error('Error loading daily logs:', error);
      this.showError('Failed to load daily logs');
    }
  }

  /**
   * Render the log list (Requirement 8.7: reverse chronological order)
   */
  render() {
    if (!this.container) {
      console.error('Container not found');
      return;
    }

    if (this.logs.length === 0) {
      this.container.innerHTML = `
        <div class="text-center py-8 text-base-content/60">
          <p>No daily logs yet. Add your first entry above!</p>
        </div>
      `;
      return;
    }

    // Logs are already in reverse chronological order from API
    const logsHtml = this.logs.map(log => this.renderLogRow(log)).join('');

    this.container.innerHTML = `
      <div class="overflow-x-auto">
        <table class="table table-zebra w-full">
          <thead>
            <tr>
              <th>Date</th>
              <th>Calories</th>
              <th>Protein (g)</th>
              <th>Carbs (g)</th>
              <th>Fats (g)</th>
              <th>Adherence</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            ${logsHtml}
          </tbody>
        </table>
      </div>
    `;

    this.attachEventListeners();
  }

  /**
   * Render a single log row
   */
  renderLogRow(log) {
    const logId = log.id;
    const isEditing = this.editingState[logId];

    return `
      <tr data-log-id="${logId}">
        <td class="font-semibold">${this.formatDate(log.log_date)}</td>
        <td>${this.renderEditableField(logId, 'calories_in', log.calories_in, isEditing)}</td>
        <td>${this.renderEditableField(logId, 'protein_g', log.protein_g, isEditing)}</td>
        <td>${this.renderEditableField(logId, 'carbs_g', log.carbs_g, isEditing)}</td>
        <td>${this.renderEditableField(logId, 'fat_g', log.fat_g, isEditing)}</td>
        <td>${this.renderEditableField(logId, 'adherence_score', log.adherence_score, isEditing)}</td>
        <td>${this.renderEditableField(logId, 'notes', log.notes, isEditing, 'text')}</td>
      </tr>
    `;
  }

  /**
   * Render an editable field (Requirement 9.1: inline editing on click)
   */
  renderEditableField(logId, fieldName, value, isEditing, type = 'number') {
    const editKey = `${logId}-${fieldName}`;
    const displayValue = value !== null && value !== undefined ? value : '--';
    
    if (isEditing && isEditing.field === fieldName) {
      // Show input with save/cancel buttons (Requirement 9.2)
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
            data-log-id="${logId}"
            data-field="${fieldName}"
            aria-label="Save"
          >
            ✓
          </button>
          <button 
            class="btn btn-xs btn-ghost"
            data-action="cancel"
            data-log-id="${logId}"
            data-field="${fieldName}"
            aria-label="Cancel"
          >
            ✕
          </button>
        </div>
        <div class="text-xs text-error mt-1" id="error-${editKey}"></div>
      `;
    }

    // Show clickable value
    return `
      <span 
        class="cursor-pointer hover:bg-base-200 px-2 py-1 rounded inline-block"
        data-action="edit"
        data-log-id="${logId}"
        data-field="${fieldName}"
        tabindex="0"
        role="button"
        aria-label="Click to edit ${fieldName}"
      >
        ${displayValue}
      </span>
    `;
  }

  /**
   * Attach event listeners for inline editing
   */
  attachEventListeners() {
    this.container.addEventListener('click', (e) => {
      const action = e.target.dataset.action;
      const logId = e.target.dataset.logId;
      const field = e.target.dataset.field;

      if (action === 'edit') {
        this.enableInlineEdit(logId, field);
      } else if (action === 'save') {
        this.saveEdit(logId, field);
      } else if (action === 'cancel') {
        this.cancelEdit(logId, field);
      }
    });

    // Support keyboard navigation (Enter to edit)
    this.container.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.dataset.action === 'edit') {
        const logId = e.target.dataset.logId;
        const field = e.target.dataset.field;
        this.enableInlineEdit(logId, field);
      }
    });
  }

  /**
   * Enable inline editing for a field (Requirement 9.1)
   */
  enableInlineEdit(logId, field) {
    const log = this.logs.find(l => l.id === logId);
    if (!log) return;

    // Store original value for cancel operation
    this.editingState[logId] = {
      field: field,
      originalValue: log[field]
    };

    this.render();

    // Focus the input field
    const editKey = `${logId}-${field}`;
    const input = document.getElementById(`edit-${editKey}`);
    if (input) {
      input.focus();
      input.select();
    }
  }

  /**
   * Save edited value (Requirement 9.3: validate, 9.4: visual feedback, 9.5: refresh)
   */
  async saveEdit(logId, field) {
    const editKey = `${logId}-${field}`;
    const input = document.getElementById(`edit-${editKey}`);
    const errorElement = document.getElementById(`error-${editKey}`);
    
    if (!input) return;

    const newValue = input.value.trim();

    // Clear previous errors
    if (errorElement) {
      errorElement.textContent = '';
    }

    // Validate the new value (Requirement 9.3)
    const validationError = this.validateField(field, newValue);
    if (validationError) {
      if (errorElement) {
        errorElement.textContent = validationError;
      }
      return;
    }

    // Show loading state (Requirement 9.4: visual feedback)
    const saveBtn = input.nextElementSibling;
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<span class="loading loading-spinner loading-xs"></span>';
    }

    try {
      // Get the log and prepare update
      const log = this.logs.find(l => l.id === logId);
      if (!log) throw new Error('Log not found');

      // Prepare update data
      const updateData = {
        log_date: log.log_date,
        calories_in: log.calories_in,
        protein_g: log.protein_g,
        carbs_g: log.carbs_g,
        fat_g: log.fat_g,
        adherence_score: log.adherence_score,
        notes: log.notes
      };

      // Update the specific field
      if (field === 'notes') {
        updateData[field] = newValue || null;
      } else {
        updateData[field] = newValue ? parseFloat(newValue) : null;
      }

      // Call API to update (Requirement 9.3)
      const updatedLog = await api.updateDailyLog(logId, updateData);

      // Update local state
      const logIndex = this.logs.findIndex(l => l.id === logId);
      if (logIndex !== -1) {
        this.logs[logIndex] = updatedLog;
      }

      // Clear editing state
      delete this.editingState[logId];

      // Re-render to show updated value (Requirement 9.5)
      this.render();

      // Show success feedback briefly
      this.showSuccessFeedback(logId, field);

    } catch (error) {
      console.error('Error saving edit:', error);
      
      // Show error message (Requirement 9.6)
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
   * Cancel edit and restore original value (Requirement 9.4)
   */
  cancelEdit(logId, field) {
    const editState = this.editingState[logId];
    if (!editState) return;

    // Restore original value in local state
    const log = this.logs.find(l => l.id === logId);
    if (log) {
      log[field] = editState.originalValue;
    }

    // Clear editing state
    delete this.editingState[logId];

    // Re-render
    this.render();
  }

  /**
   * Validate field value (Requirement 9.3: same rules as creation form)
   */
  validateField(fieldName, value) {
    // Notes field doesn't need validation
    if (fieldName === 'notes') {
      return null;
    }

    // Empty values are allowed
    if (!value || value === '') {
      return null;
    }

    const rules = this.validationRules[fieldName];
    if (!rules) return null;

    const numValue = parseFloat(value);

    // Check if value is a valid number
    if (isNaN(numValue)) {
      return `${rules.label} must be a valid number`;
    }

    // Check minimum value
    if (numValue < rules.min) {
      return `${rules.label} must be at least ${rules.min}`;
    }

    // Check maximum value
    if (numValue > rules.max) {
      return `${rules.label} must not exceed ${rules.max}`;
    }

    return null;
  }

  /**
   * Show success feedback briefly
   */
  showSuccessFeedback(logId, field) {
    const row = this.container.querySelector(`tr[data-log-id="${logId}"]`);
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

  /**
   * Calculate calories from macros (for display purposes)
   */
  calculateMacros(protein, carbs, fats) {
    const p = parseFloat(protein) || 0;
    const c = parseFloat(carbs) || 0;
    const f = parseFloat(fats) || 0;
    return Math.round((p * 4) + (c * 4) + (f * 9));
  }
}

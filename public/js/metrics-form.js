/**
 * MetricsForm Component
 * Handles body metrics data entry with real-time validation
 * Requirements: 5.1, 5.2, 5.3, 5.7
 */

class MetricsForm {
  constructor(containerId, existingMetric = null, extendedMode = false) {
    this.containerId = containerId;
    this.existingMetric = existingMetric;
    this.isEditMode = !!existingMetric;
    this.extendedMode = extendedMode;
    this.successCallback = null;
    this.errorCallback = null;
    
    // Validation rules
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
   * Render the form
   */
  render() {
    this.container = document.getElementById(this.containerId);
    
    if (!this.container) {
      console.error('Container not found');
      return;
    }

    const formHtml = `
      <form id="metrics-form" class="space-y-4">
        <!-- Measurement Date -->
        <div class="form-control">
          <label class="label" for="measurement_date">
            <span class="label-text">Measurement Date</span>
          </label>
          <input 
            type="date" 
            id="measurement_date" 
            name="measurement_date"
            class="input input-bordered w-full"
            value="${this.existingMetric?.measurement_date || new Date().toISOString().split('T')[0]}"
            ${this.isEditMode ? 'disabled' : ''}
            required
          />
        </div>

        <!-- Weight -->
        <div class="form-control">
          <label class="label" for="weight">
            <span class="label-text">Weight (kg) *</span>
          </label>
          <input 
            type="number" 
            id="weight" 
            name="weight"
            class="input input-bordered w-full"
            placeholder="Enter weight in kg"
            step="0.1"
            min="30"
            max="300"
            value="${this.existingMetric?.weight_kg || ''}"
            required
          />
          <label class="label">
            <span class="label-text-alt text-error" id="weight-error"></span>
          </label>
        </div>

        <!-- Body Fat Percentage -->
        <div class="form-control">
          <label class="label" for="body_fat_pct">
            <span class="label-text">Body Fat %</span>
          </label>
          <input 
            type="number" 
            id="body_fat_pct" 
            name="body_fat_pct"
            class="input input-bordered w-full"
            placeholder="Enter body fat percentage"
            step="0.1"
            min="3"
            max="60"
            value="${this.existingMetric?.body_fat_pct || ''}"
          />
          <label class="label">
            <span class="label-text-alt text-error" id="body_fat_pct-error"></span>
          </label>
        </div>

        <!-- Waist Circumference -->
        <div class="form-control">
          <label class="label" for="waist_cm">
            <span class="label-text">Waist Circumference (cm)</span>
          </label>
          <input 
            type="number" 
            id="waist_cm" 
            name="waist_cm"
            class="input input-bordered w-full"
            placeholder="Enter waist measurement"
            step="0.1"
            min="0"
            value="${this.existingMetric?.waist_cm || ''}"
          />
        </div>

        ${this.extendedMode ? `
        <!-- Sleep Average -->
        <div class="form-control">
          <label class="label" for="sleep_avg_hrs">
            <span class="label-text">Sleep Average (hours)</span>
          </label>
          <input 
            type="number" 
            id="sleep_avg_hrs" 
            name="sleep_avg_hrs"
            class="input input-bordered w-full"
            placeholder="Enter average sleep hours"
            step="0.1"
            min="0"
            max="24"
            value="${this.existingMetric?.sleep_avg_hrs || ''}"
          />
          <label class="label">
            <span class="label-text-alt text-error" id="sleep_avg_hrs-error"></span>
          </label>
        </div>

        <!-- Resting Heart Rate -->
        <div class="form-control">
          <label class="label" for="rhr_bpm">
            <span class="label-text">Resting Heart Rate (bpm)</span>
          </label>
          <input 
            type="number" 
            id="rhr_bpm" 
            name="rhr_bpm"
            class="input input-bordered w-full"
            placeholder="Enter resting heart rate"
            min="30"
            max="220"
            value="${this.existingMetric?.rhr_bpm || ''}"
          />
          <label class="label">
            <span class="label-text-alt text-error" id="rhr_bpm-error"></span>
          </label>
        </div>

        <!-- Energy Level Average -->
        <div class="form-control">
          <label class="label" for="energy_level_avg">
            <span class="label-text">Energy Level Average (1-10)</span>
          </label>
          <input 
            type="number" 
            id="energy_level_avg" 
            name="energy_level_avg"
            class="input input-bordered w-full"
            placeholder="Enter average energy level"
            step="0.1"
            min="1"
            max="10"
            value="${this.existingMetric?.energy_level_avg || ''}"
          />
          <label class="label">
            <span class="label-text-alt text-error" id="energy_level_avg-error"></span>
          </label>
        </div>
        ` : ''}

        <!-- Form Actions -->
        <div class="flex gap-2 pt-4">
          <button 
            type="submit" 
            class="btn btn-primary"
            id="submit-btn"
          >
            ${this.isEditMode ? 'Update' : 'Save'} Measurement
          </button>
          ${this.isEditMode ? '<button type="button" class="btn btn-ghost" id="cancel-btn">Cancel</button>' : ''}
        </div>

        <!-- Success/Error Messages -->
        <div id="form-message" class="hidden"></div>
      </form>
    `;

    this.container.innerHTML = formHtml;
    this.attachEventListeners();
  }

  /**
   * Attach event listeners for validation and submission
   */
  attachEventListeners() {
    const form = document.getElementById('metrics-form');
    const weightInput = document.getElementById('weight');
    const bodyFatInput = document.getElementById('body_fat_pct');
    const cancelBtn = document.getElementById('cancel-btn');

    // Real-time validation for weight
    weightInput.addEventListener('input', () => {
      this.validateField('weight', weightInput.value);
    });

    weightInput.addEventListener('blur', () => {
      this.validateField('weight', weightInput.value);
    });

    // Real-time validation for body fat percentage
    bodyFatInput.addEventListener('input', () => {
      this.validateField('body_fat_pct', bodyFatInput.value);
    });

    bodyFatInput.addEventListener('blur', () => {
      this.validateField('body_fat_pct', bodyFatInput.value);
    });

    // Extended mode field validation
    if (this.extendedMode) {
      const sleepInput = document.getElementById('sleep_avg_hrs');
      const rhrInput = document.getElementById('rhr_bpm');
      const energyInput = document.getElementById('energy_level_avg');

      if (sleepInput) {
        sleepInput.addEventListener('input', () => {
          this.validateField('sleep_avg_hrs', sleepInput.value);
        });
        sleepInput.addEventListener('blur', () => {
          this.validateField('sleep_avg_hrs', sleepInput.value);
        });
      }

      if (rhrInput) {
        rhrInput.addEventListener('input', () => {
          this.validateField('rhr_bpm', rhrInput.value);
        });
        rhrInput.addEventListener('blur', () => {
          this.validateField('rhr_bpm', rhrInput.value);
        });
      }

      if (energyInput) {
        energyInput.addEventListener('input', () => {
          this.validateField('energy_level_avg', energyInput.value);
        });
        energyInput.addEventListener('blur', () => {
          this.validateField('energy_level_avg', energyInput.value);
        });
      }
    }

    // Form submission
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      this.submit();
    });

    // Cancel button (edit mode only)
    if (cancelBtn) {
      cancelBtn.addEventListener('click', () => {
        this.reset();
      });
    }
  }

  /**
   * Validate a specific field
   * @param {string} fieldName - Name of the field to validate
   * @param {string} value - Value to validate
   * @returns {boolean} - True if valid, false otherwise
   */
  validateField(fieldName, value) {
    const errorElement = document.getElementById(`${fieldName}-error`);
    const inputElement = document.getElementById(fieldName);
    
    if (!errorElement || !inputElement) return true;

    // Clear previous error
    errorElement.textContent = '';
    inputElement.classList.remove('input-error');

    // Skip validation if field is empty and not required
    if (!value && fieldName !== 'weight') {
      return true;
    }

    const rules = this.validationRules[fieldName];
    if (!rules) return true;

    const numValue = parseFloat(value);

    // Check if value is a valid number
    if (isNaN(numValue)) {
      errorElement.textContent = `${rules.label} must be a valid number`;
      inputElement.classList.add('input-error');
      return false;
    }

    // Check minimum value
    if (numValue < rules.min) {
      errorElement.textContent = `${rules.label} must be at least ${rules.min}${fieldName === 'weight' ? 'kg' : '%'}`;
      inputElement.classList.add('input-error');
      return false;
    }

    // Check maximum value
    if (numValue > rules.max) {
      errorElement.textContent = `${rules.label} must not exceed ${rules.max}${fieldName === 'weight' ? 'kg' : '%'}`;
      inputElement.classList.add('input-error');
      return false;
    }

    return true;
  }

  /**
   * Validate the entire form
   * @returns {boolean} - True if all fields are valid
   */
  validate() {
    const weightInput = document.getElementById('weight');
    const bodyFatInput = document.getElementById('body_fat_pct');

    let isValid = this.validateField('weight', weightInput.value);
    isValid = this.validateField('body_fat_pct', bodyFatInput.value) && isValid;

    if (this.extendedMode) {
      const sleepInput = document.getElementById('sleep_avg_hrs');
      const rhrInput = document.getElementById('rhr_bpm');
      const energyInput = document.getElementById('energy_level_avg');

      if (sleepInput) {
        isValid = this.validateField('sleep_avg_hrs', sleepInput.value) && isValid;
      }
      if (rhrInput) {
        isValid = this.validateField('rhr_bpm', rhrInput.value) && isValid;
      }
      if (energyInput) {
        isValid = this.validateField('energy_level_avg', energyInput.value) && isValid;
      }
    }

    return isValid;
  }

  /**
   * Submit the form
   */
  async submit() {
    // Validate form
    if (!this.validate()) {
      this.showMessage('Please fix the validation errors before submitting', 'error');
      return;
    }

    const submitBtn = document.getElementById('submit-btn');
    const originalText = submitBtn.textContent;
    
    try {
      // Disable submit button
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="loading loading-spinner loading-sm"></span> Saving...';

      // Collect form data
      const formData = this.getFormData();

      // Call API
      let result;
      if (this.isEditMode) {
        result = await api.updateWeeklyMeasurement(this.existingMetric.id, formData);
      } else {
        result = await api.createWeeklyMeasurement(formData);
      }

      // Show success message
      this.showMessage(`Measurement ${this.isEditMode ? 'updated' : 'saved'} successfully!`, 'success');

      // Call success callback if provided
      if (this.successCallback) {
        this.successCallback(result);
      }

      // Reset form if not in edit mode
      if (!this.isEditMode) {
        this.reset();
      }

    } catch (error) {
      console.error('Error submitting metrics:', error);
      this.showMessage(error.message || 'Failed to save measurement. Please try again.', 'error');
      
      // Call error callback if provided
      if (this.errorCallback) {
        this.errorCallback(error);
      }
    } finally {
      // Re-enable submit button
      submitBtn.disabled = false;
      submitBtn.textContent = originalText;
    }
  }

  /**
   * Get form data as an object
   * @returns {object} - Form data
   */
  getFormData() {
    const form = document.getElementById('metrics-form');
    const formData = new FormData(form);
    
    const data = {
      week_start: formData.get('measurement_date'),
      weight_kg: parseFloat(formData.get('weight')),
    };

    // Add optional fields if they have values
    const bodyFat = formData.get('body_fat_pct');
    if (bodyFat) {
      data.body_fat_pct = parseFloat(bodyFat);
    }

    const waist = formData.get('waist_cm');
    if (waist) {
      data.waist_cm = parseFloat(waist);
    }

    // Extended mode fields
    if (this.extendedMode) {
      const sleep = formData.get('sleep_avg_hrs');
      if (sleep) {
        data.sleep_avg_hrs = parseFloat(sleep);
      }

      const rhr = formData.get('rhr_bpm');
      if (rhr) {
        data.rhr_bpm = parseInt(rhr);
      }

      const energy = formData.get('energy_level_avg');
      if (energy) {
        data.energy_level_avg = parseFloat(energy);
      }
    }

    return data;
  }

  /**
   * Reset the form
   */
  reset() {
    const form = document.getElementById('metrics-form');
    if (form) {
      form.reset();
      
      // Clear all error messages
      document.querySelectorAll('[id$="-error"]').forEach(el => {
        el.textContent = '';
      });
      
      // Remove error styling
      document.querySelectorAll('.input-error').forEach(el => {
        el.classList.remove('input-error');
      });
      
      // Hide message
      this.hideMessage();
      
      // Reset date to today if not in edit mode
      if (!this.isEditMode) {
        const dateInput = document.getElementById('measurement_date');
        if (dateInput) {
          dateInput.value = new Date().toISOString().split('T')[0];
        }
      }
    }
  }

  /**
   * Show a message to the user
   * @param {string} message - Message to display
   * @param {string} type - Message type ('success' or 'error')
   */
  showMessage(message, type = 'info') {
    const messageElement = document.getElementById('form-message');
    if (!messageElement) return;

    const alertClass = type === 'success' ? 'alert-success' : 'alert-error';
    messageElement.className = `alert ${alertClass} mt-4`;
    messageElement.textContent = message;
    messageElement.classList.remove('hidden');

    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
      setTimeout(() => {
        this.hideMessage();
      }, 5000);
    }
  }

  /**
   * Hide the message
   */
  hideMessage() {
    const messageElement = document.getElementById('form-message');
    if (messageElement) {
      messageElement.classList.add('hidden');
    }
  }

  /**
   * Set success callback
   * @param {function} callback - Function to call on successful submission
   */
  onSuccess(callback) {
    this.successCallback = callback;
  }

  /**
   * Set error callback
   * @param {function} callback - Function to call on error
   */
  onError(callback) {
    this.errorCallback = callback;
  }
}
export { MetricsForm };
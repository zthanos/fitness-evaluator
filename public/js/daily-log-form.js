/**
 * DailyLogForm Component
 * Handles daily log data entry with real-time validation
 * Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
 */

class DailyLogForm {
  constructor(containerId) {
    this.containerId = containerId;
    this.container = null;
    this.successCallback = null;
    this.errorCallback = null;
    
    // Validation rules per Requirements 8.2
    this.validationRules = {
      calories_in: { min: 0, max: 10000, label: 'Calories' },
      protein_g: { min: 0, max: 1000, label: 'Protein' },
      carbs_g: { min: 0, max: 1000, label: 'Carbs' },
      fat_g: { min: 0, max: 1000, label: 'Fats' },
      adherence_score: { min: 0, max: 100, label: 'Adherence Score' }
    };
  }

  /**
   * Render the form
   */
  render() {
    // Get container if not already set
    if (!this.container) {
      this.container = document.getElementById(this.containerId);
    }
    
    if (!this.container) {
      console.error('Container not found');
      return;
    }

    const formHtml = `
      <form id="daily-log-form" class="space-y-4">
        <!-- Date -->
        <div class="form-control">
          <label class="label" for="log_date">
            <span class="label-text font-semibold">Date *</span>
          </label>
          <input 
            type="date" 
            id="log_date" 
            name="log_date"
            class="input input-bordered w-full"
            value="${new Date().toISOString().split('T')[0]}"
            required
          />
          <label class="label">
            <span class="label-text-alt text-error" id="log_date-error"></span>
          </label>
        </div>

        <!-- Calories -->
        <div class="form-control">
          <label class="label" for="calories_in">
            <span class="label-text font-semibold">Calories In</span>
            <span class="label-text-alt">kcal (0-10000)</span>
          </label>
          <input 
            type="number" 
            id="calories_in" 
            name="calories_in"
            class="input input-bordered w-full"
            placeholder="Enter total calories"
            min="0"
            max="10000"
          />
          <label class="label">
            <span class="label-text-alt text-error" id="calories_in-error"></span>
          </label>
        </div>

        <!-- Protein -->
        <div class="form-control">
          <label class="label" for="protein_g">
            <span class="label-text font-semibold">Protein</span>
            <span class="label-text-alt">grams (0-1000)</span>
          </label>
          <input 
            type="number" 
            id="protein_g" 
            name="protein_g"
            class="input input-bordered w-full"
            placeholder="Enter protein in grams"
            step="0.1"
            min="0"
            max="1000"
          />
          <label class="label">
            <span class="label-text-alt text-error" id="protein_g-error"></span>
          </label>
        </div>

        <!-- Carbs -->
        <div class="form-control">
          <label class="label" for="carbs_g">
            <span class="label-text font-semibold">Carbs</span>
            <span class="label-text-alt">grams (0-1000)</span>
          </label>
          <input 
            type="number" 
            id="carbs_g" 
            name="carbs_g"
            class="input input-bordered w-full"
            placeholder="Enter carbs in grams"
            step="0.1"
            min="0"
            max="1000"
          />
          <label class="label">
            <span class="label-text-alt text-error" id="carbs_g-error"></span>
          </label>
        </div>

        <!-- Fats -->
        <div class="form-control">
          <label class="label" for="fat_g">
            <span class="label-text font-semibold">Fats</span>
            <span class="label-text-alt">grams (0-1000)</span>
          </label>
          <input 
            type="number" 
            id="fat_g" 
            name="fat_g"
            class="input input-bordered w-full"
            placeholder="Enter fats in grams"
            step="0.1"
            min="0"
            max="1000"
          />
          <label class="label">
            <span class="label-text-alt text-error" id="fat_g-error"></span>
          </label>
        </div>

        <!-- Adherence Score -->
        <div class="form-control">
          <label class="label" for="adherence_score">
            <span class="label-text font-semibold">Adherence Score</span>
            <span class="label-text-alt">0-100</span>
          </label>
          <input 
            type="number" 
            id="adherence_score" 
            name="adherence_score"
            class="input input-bordered w-full"
            placeholder="Enter adherence score (0-100)"
            min="0"
            max="100"
          />
          <label class="label">
            <span class="label-text-alt text-error" id="adherence_score-error"></span>
          </label>
        </div>

        <!-- Mood/Energy Notes -->
        <div class="form-control">
          <label class="label" for="notes">
            <span class="label-text font-semibold">Mood / Energy Notes</span>
          </label>
          <textarea 
            id="notes" 
            name="notes"
            class="textarea textarea-bordered w-full"
            placeholder="How did you feel today? Any observations about mood or energy levels..."
            rows="3"
          ></textarea>
        </div>

        <!-- Form Actions -->
        <div class="form-control mt-6">
          <button 
            type="submit" 
            class="btn btn-primary"
            id="submit-btn"
          >
            Save Log Entry
          </button>
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
    const form = document.getElementById('daily-log-form');
    
    // Add real-time validation for all numeric fields
    ['calories_in', 'protein_g', 'carbs_g', 'fat_g', 'adherence_score'].forEach(fieldName => {
      const input = document.getElementById(fieldName);
      if (input) {
        input.addEventListener('input', () => {
          this.validateField(fieldName, input.value);
        });
        
        input.addEventListener('blur', () => {
          this.validateField(fieldName, input.value);
        });
      }
    });

    // Form submission
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      this.submit();
    });
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

    // Skip validation if field is empty (all fields are optional except date)
    if (!value || value === '') {
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

    // Check minimum value (Requirement 8.4: specific validation error messages)
    if (numValue < rules.min) {
      errorElement.textContent = `${rules.label} must be at least ${rules.min}`;
      inputElement.classList.add('input-error');
      return false;
    }

    // Check maximum value (Requirement 8.4: specific validation error messages)
    if (numValue > rules.max) {
      errorElement.textContent = `${rules.label} must not exceed ${rules.max}`;
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
    let isValid = true;
    
    // Validate all numeric fields
    ['calories_in', 'protein_g', 'carbs_g', 'fat_g', 'adherence_score'].forEach(fieldName => {
      const input = document.getElementById(fieldName);
      if (input && input.value) {
        const fieldValid = this.validateField(fieldName, input.value);
        isValid = isValid && fieldValid;
      }
    });

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
      // Disable submit button (Requirement 8.5)
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="loading loading-spinner loading-sm"></span> Saving...';

      // Collect form data
      const formData = this.getFormData();

      // Check for duplicate date (Requirement 8.3)
      try {
        const existingLog = await api.getDailyLog(formData.log_date);
        if (existingLog) {
          this.showMessage(`A log entry already exists for ${formData.log_date}. Please choose a different date or edit the existing entry.`, 'error');
          submitBtn.disabled = false;
          submitBtn.textContent = originalText;
          return;
        }
      } catch (error) {
        // 404 error or "not found" means no existing log, which is what we want
        const isNotFound = error.message.includes('404') || 
                          error.message.includes('not found') || 
                          error.message.includes('Not Found');
        if (!isNotFound) {
          throw error;
        }
        // Otherwise, continue to create the log
      }

      // Call API to create log
      const result = await api.createDailyLog(formData);

      // Show success message
      this.showMessage('Daily log saved successfully!', 'success');

      // Call success callback if provided
      if (this.successCallback) {
        this.successCallback(result);
      }

      // Reset form
      this.reset();

    } catch (error) {
      console.error('Error submitting daily log:', error);
      
      // Handle duplicate date error from server
      if (error.message && error.message.includes('duplicate')) {
        this.showMessage('A log entry already exists for this date. Please choose a different date.', 'error');
      } else {
        this.showMessage(error.message || 'Failed to save log entry. Please try again.', 'error');
      }
      
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
    const form = document.getElementById('daily-log-form');
    const formData = new FormData(form);
    
    const data = {
      log_date: formData.get('log_date'),
    };

    // Add optional numeric fields if they have values
    const calories = formData.get('calories_in');
    if (calories) {
      data.calories_in = parseInt(calories);
    }

    const protein = formData.get('protein_g');
    if (protein) {
      data.protein_g = parseFloat(protein);
    }

    const carbs = formData.get('carbs_g');
    if (carbs) {
      data.carbs_g = parseFloat(carbs);
    }

    const fats = formData.get('fat_g');
    if (fats) {
      data.fat_g = parseFloat(fats);
    }

    const adherence = formData.get('adherence_score');
    if (adherence) {
      data.adherence_score = parseInt(adherence);
    }

    const notes = formData.get('notes');
    if (notes && notes.trim()) {
      data.notes = notes.trim();
    }

    return data;
  }

  /**
   * Reset the form
   */
  reset() {
    const form = document.getElementById('daily-log-form');
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
      
      // Reset date to today
      const dateInput = document.getElementById('log_date');
      if (dateInput) {
        dateInput.value = new Date().toISOString().split('T')[0];
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

export { DailyLogForm };
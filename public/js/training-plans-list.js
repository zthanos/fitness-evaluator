/**
 * TrainingPlansList Component
 * Displays training plans in a card grid with progress and adherence metrics
 * Requirements: 12.1, 12.2, 12.3, 12.4
 */

class TrainingPlansList {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.container = null;
    
    this.plans = [];
    this.onPlanClick = options.onPlanClick || null;
  }

  /**
   * Initialize the component and load data
   */
  async init() {
    // Wait a bit for DOM to be ready, then get the container element
    await new Promise(resolve => setTimeout(resolve, 50));
    
    this.container = document.getElementById(this.containerId);
    if (!this.container) {
      // Try one more time after another delay
      await new Promise(resolve => setTimeout(resolve, 100));
      this.container = document.getElementById(this.containerId);
      
      if (!this.container) {
        console.error('DOM state:', document.getElementById('main-content')?.innerHTML.substring(0, 200));
        throw new Error(`Container with id "${this.containerId}" not found`);
      }
    }
    
    await this.loadPlans();
    this.render();
  }

  /**
   * Load training plans from the API
   */
  async loadPlans() {
    try {
      const response = await api.get('/training-plans');
      this.plans = response.plans || [];
    } catch (error) {
      console.error('Failed to load training plans:', error);
      this.plans = [];
      throw error;
    }
  }

  /**
   * Render the complete component
   */
  render() {
    if (this.plans.length === 0) {
      this.renderEmptyState();
      return;
    }

    this.container.innerHTML = `
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        ${this.plans.map(plan => this.renderPlanCard(plan)).join('')}
      </div>
    `;
    
    this.attachEventListeners();
  }

  /**
   * Render empty state when no plans exist
   */
  renderEmptyState() {
    this.container.innerHTML = `
      <div class="card bg-base-100 shadow-xl">
        <div class="card-body text-center py-12">
          <div class="text-6xl mb-4">🎯</div>
          <h2 class="text-2xl font-bold mb-2">No Training Plans Yet</h2>
          <p class="text-base-content/60 mb-6">
            Start by chatting with your AI coach to create a personalized training plan.
          </p>
          <a href="/chat.html" class="btn btn-primary">
            💬 Chat with Coach
          </a>
        </div>
      </div>
    `;
  }

  /**
   * Render a single plan card
   * Requirements: 12.2, 12.3
   */
  renderPlanCard(plan) {
    const statusBadge = this.getStatusBadge(plan.status);
    const adherenceColor = this.getAdherenceColor(plan.adherence_percentage);
    const startDate = this.formatDate(plan.start_date);
    const endDate = this.formatDate(plan.end_date);
    
    return `
      <div class="card bg-base-100 shadow-xl hover:shadow-2xl transition-shadow cursor-pointer" 
           data-plan-id="${plan.id}">
        <div class="card-body">
          <!-- Header -->
          <div class="flex justify-between items-start mb-3">
            <h2 class="card-title text-lg">${this.escapeHtml(plan.title)}</h2>
            ${statusBadge}
          </div>
          
          <!-- Plan Details -->
          <div class="space-y-2 text-sm">
            <div class="flex items-center gap-2">
              <span class="text-base-content/60">Sport:</span>
              <span class="badge badge-outline">${this.escapeHtml(plan.sport)}</span>
            </div>
            
            ${plan.goal ? `
              <div class="flex items-center gap-2">
                <span class="text-base-content/60">Goal:</span>
                <span class="font-medium">${this.escapeHtml(plan.goal)}</span>
              </div>
            ` : ''}
            
            <div class="flex items-center gap-2">
              <span class="text-base-content/60">Duration:</span>
              <span>${startDate} - ${endDate}</span>
            </div>
          </div>
          
          <!-- Progress Section -->
          <div class="mt-4">
            <div class="flex justify-between items-center mb-2">
              <span class="text-sm font-medium">Adherence</span>
              <span class="text-sm font-bold ${adherenceColor}">
                ${plan.adherence_percentage.toFixed(1)}%
              </span>
            </div>
            
            <!-- Progress Bar -->
            <div class="w-full bg-base-300 rounded-full h-3">
              <div class="${adherenceColor} h-3 rounded-full transition-all duration-300" 
                   style="width: ${plan.adherence_percentage}%">
              </div>
            </div>
            
            <!-- Session Stats -->
            <div class="text-xs text-base-content/60 mt-2">
              ${plan.completed_sessions} of ${plan.total_sessions} sessions completed
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Get status badge HTML
   * Requirement: 12.2
   */
  getStatusBadge(status) {
    const badges = {
      draft: '<span class="badge badge-ghost">Draft</span>',
      active: '<span class="badge badge-success">Active</span>',
      completed: '<span class="badge badge-info">Completed</span>',
      abandoned: '<span class="badge badge-warning">Abandoned</span>'
    };
    
    return badges[status] || badges.draft;
  }

  /**
   * Get adherence color class based on percentage
   * Requirement: 12.3
   */
  getAdherenceColor(percentage) {
    if (percentage >= 80) return 'text-success';
    if (percentage >= 60) return 'text-warning';
    return 'text-error';
  }

  /**
   * Format date for display
   */
  formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric' 
    });
  }

  /**
   * Escape HTML to prevent XSS
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Attach event listeners
   * Requirement: 12.4
   */
  attachEventListeners() {
    const cards = this.container.querySelectorAll('[data-plan-id]');
    cards.forEach(card => {
      card.addEventListener('click', () => {
        const planId = card.dataset.planId;
        if (this.onPlanClick) {
          this.onPlanClick(planId);
        } else {
          window.location.href = `/training-plans/${planId}`;
        }
      });
    });
  }

  /**
   * Reload plans and re-render
   */
  async refresh() {
    await this.loadPlans();
    this.render();
  }
}
export { TrainingPlansList };
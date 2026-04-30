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
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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
      <div class="card bg-base-100 shadow-sm border border-base-200">
        <div class="card-body items-center text-center py-12 gap-3">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-10 h-10 text-base-content/20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"/>
          </svg>
          <p class="font-semibold text-base-content/70">No training plans yet</p>
          <p class="text-sm text-base-content/40 max-w-xs">Create a plan from a goal, a route, or by chatting with your coach.</p>
          <button onclick="document.getElementById('btn-new-plan').click()" class="btn btn-sm btn-primary mt-1">Create a plan</button>
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
    
    const adherencePct = Math.min(100, Math.max(0, plan.adherence_percentage));
    const bgColor = adherencePct >= 80 ? 'bg-success' : adherencePct >= 60 ? 'bg-warning' : 'bg-error';

    return `
      <div class="card bg-base-100 shadow-sm hover:shadow-md border border-base-200 hover:border-primary/30 transition-all cursor-pointer"
           data-plan-id="${plan.id}">
        <div class="card-body p-4 gap-3">
          <!-- Header row -->
          <div class="flex items-start justify-between gap-2">
            <h2 class="font-semibold text-sm leading-snug line-clamp-2 flex-1">${this.escapeHtml(plan.title)}</h2>
            ${statusBadge}
          </div>

          <!-- Meta chips -->
          <div class="flex flex-wrap gap-1.5">
            <span class="badge badge-outline badge-sm">${this.escapeHtml(plan.sport)}</span>
            ${plan.plan_type && plan.plan_type !== 'primary' ? `<span class="badge badge-ghost badge-sm">${this.escapeHtml(plan.plan_type)}</span>` : ''}
          </div>

          ${plan.goal ? `<p class="text-xs text-base-content/60 leading-snug line-clamp-2">${this.escapeHtml(plan.goal)}</p>` : ''}

          <!-- Dates -->
          <p class="text-xs text-base-content/50">${startDate} → ${endDate}</p>

          <!-- Adherence bar -->
          <div>
            <div class="flex justify-between items-center mb-1">
              <span class="text-xs text-base-content/60">Adherence</span>
              <span class="text-xs font-semibold ${adherenceColor}">${adherencePct.toFixed(1)}%</span>
            </div>
            <div class="w-full bg-base-300 rounded-full h-1.5">
              <div class="${bgColor} h-1.5 rounded-full transition-all duration-300" style="width: ${adherencePct}%"></div>
            </div>
            <p class="text-xs text-base-content/40 mt-1">${plan.completed_sessions} / ${plan.total_sessions} sessions</p>
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
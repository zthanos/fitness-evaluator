/**
 * TrainingPlanDetail Component
 * Displays detailed training plan with weekly timeline and session grid
 * Requirements: 13.1, 13.2, 13.3, 13.4
 */

class TrainingPlanDetail {
  constructor(containerId, planId) {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      throw new Error(`Container with id "${containerId}" not found`);
    }
    
    this.planId = planId;
    this.plan = null;
    this.adherenceChart = null;
  }

  /**
   * Initialize the component and load data
   */
  async init() {
    try {
      await this.loadPlan();
      this.render();
    } catch (error) {
      console.error('Failed to load plan:', error);
      this.renderError(error.message);
    }
  }

  /**
   * Load plan details from the API
   */
  async loadPlan() {
    const response = await api.get(`/training-plans/${this.planId}`);
    this.plan = response.plan;
  }

  /**
   * Render the complete component
   */
  render() {
    if (!this.plan) {
      this.renderError('Plan not found');
      return;
    }

    this.container.innerHTML = `
      ${this.renderHeader()}
      ${this.renderOverallProgress()}
      ${this.renderAdherenceChart()}
      ${this.renderWeeklyTimeline()}
      ${this.renderAskCoachButton()}
    `;
    
    // Initialize adherence chart
    this.initAdherenceChart();
  }

  /**
   * Render plan header
   * Requirement: 13.1
   */
  renderHeader() {
    const statusBadge = this.getStatusBadge(this.plan.status);
    const startDate = this.formatDate(this.plan.start_date);
    const endDate = this.formatDate(this.plan.end_date);
    
    return `
      <div class="card bg-base-100 shadow-xl mb-6">
        <div class="card-body">
          <div class="flex justify-between items-start">
            <div>
              <h1 class="text-3xl font-bold mb-2">${this.escapeHtml(this.plan.title)}</h1>
              <div class="flex flex-wrap gap-3 text-sm">
                <div class="flex items-center gap-2">
                  <span class="text-base-content/60">Sport:</span>
                  <span class="badge badge-outline badge-lg">${this.escapeHtml(this.plan.sport)}</span>
                </div>
                ${this.plan.goal_id ? `
                  <div class="flex items-center gap-2">
                    <span class="text-base-content/60">Goal:</span>
                    <span class="font-medium">Goal linked</span>
                  </div>
                ` : ''}
                <div class="flex items-center gap-2">
                  <span class="text-base-content/60">Duration:</span>
                  <span>${startDate} - ${endDate}</span>
                </div>
              </div>
            </div>
            ${statusBadge}
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Render overall progress bar
   * Requirement: 13.2
   */
  renderOverallProgress() {
    const adherenceColor = this.getAdherenceColorClass(this.plan.overall_adherence);
    const progressColor = this.getProgressColorClass(this.plan.overall_adherence);
    
    return `
      <div class="card bg-base-100 shadow-xl mb-6">
        <div class="card-body">
          <h2 class="card-title mb-4">Overall Progress</h2>
          
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <!-- Adherence -->
            <div class="stat bg-base-200 rounded-lg">
              <div class="stat-title">Adherence</div>
              <div class="stat-value ${adherenceColor}">
                ${this.plan.overall_adherence.toFixed(1)}%
              </div>
              <div class="stat-desc">
                ${this.getCompletedSessions()} of ${this.getTotalSessions()} sessions
              </div>
            </div>
            
            <!-- Time Progress -->
            <div class="stat bg-base-200 rounded-lg">
              <div class="stat-title">Time Progress</div>
              <div class="stat-value text-info">
                ${this.getTimeProgress()}%
              </div>
              <div class="stat-desc">
                ${this.getElapsedWeeks()} of ${this.plan.weeks.length} weeks
              </div>
            </div>
            
            <!-- Status -->
            <div class="stat bg-base-200 rounded-lg">
              <div class="stat-title">Status</div>
              <div class="stat-value text-sm">
                ${this.getStatusBadge(this.plan.status)}
              </div>
              <div class="stat-desc">
                ${this.getStatusDescription()}
              </div>
            </div>
          </div>
          
          <!-- Progress Bar -->
          <div class="mt-6">
            <div class="flex justify-between items-center mb-2">
              <span class="text-sm font-medium">Overall Adherence</span>
              <span class="text-sm font-bold ${adherenceColor}">
                ${this.plan.overall_adherence.toFixed(1)}%
              </span>
            </div>
            <div class="w-full bg-base-300 rounded-full h-4">
              <div class="${progressColor} h-4 rounded-full transition-all duration-300" 
                   style="width: ${this.plan.overall_adherence}%">
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Render adherence chart section
   * Requirement: 13.5
   */
  renderAdherenceChart() {
    return `
      <div class="card bg-base-100 shadow-xl mb-6">
        <div class="card-body">
          <h2 class="card-title mb-4">Weekly Adherence Trend</h2>
          <div id="adherence-chart-container" class="min-h-[300px]">
            <canvas id="adherence-chart"></canvas>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Render weekly timeline with session grid
   * Requirements: 13.3, 13.4
   */
  renderWeeklyTimeline() {
    return `
      <div class="card bg-base-100 shadow-xl mb-6">
        <div class="card-body">
          <h2 class="card-title mb-4">Weekly Timeline</h2>
          <div class="space-y-6">
            ${this.plan.weeks.map(week => this.renderWeek(week)).join('')}
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Render a single week with session grid
   * Requirements: 13.3, 13.4
   */
  renderWeek(week) {
    const adherenceColor = this.getAdherenceColorClass(week.adherence);
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    
    return `
      <div class="border border-base-300 rounded-lg p-4">
        <!-- Week Header -->
        <div class="flex justify-between items-center mb-4">
          <div>
            <h3 class="text-lg font-bold">Week ${week.week_number}</h3>
            <p class="text-sm text-base-content/60">${this.escapeHtml(week.focus || 'No focus specified')}</p>
          </div>
          <div class="text-right">
            <div class="text-sm text-base-content/60">Adherence</div>
            <div class="text-xl font-bold ${adherenceColor}">
              ${week.adherence.toFixed(1)}%
            </div>
          </div>
        </div>
        
        <!-- Session Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3">
          ${week.sessions.map((session, index) => 
            this.renderSession(session, days[session.day_of_week - 1])
          ).join('')}
        </div>
      </div>
    `;
  }

  /**
   * Render a single session card
   * Requirement: 13.4
   */
  renderSession(session, dayName) {
    const completionIcon = session.completed ? '✓' : '';
    const completionClass = session.completed ? 'bg-success text-success-content' : 'bg-base-200';
    const borderClass = session.completed ? 'border-success' : 'border-base-300';
    
    return `
      <div class="card ${completionClass} border-2 ${borderClass} shadow-sm">
        <div class="card-body p-3">
          <div class="flex justify-between items-start mb-2">
            <div class="text-xs font-bold">${dayName}</div>
            ${completionIcon ? `<div class="text-lg">${completionIcon}</div>` : ''}
          </div>
          <div class="text-sm font-medium mb-1">
            ${this.formatSessionType(session.session_type)}
          </div>
          <div class="text-xs space-y-1">
            <div>⏱️ ${session.duration_minutes} min</div>
            <div>💪 ${this.escapeHtml(session.intensity)}</div>
          </div>
          ${session.description ? `
            <div class="text-xs text-base-content/70 mt-2 line-clamp-2">
              ${this.escapeHtml(session.description)}
            </div>
          ` : ''}
          ${session.matched_activity ? `
            <div class="badge badge-sm badge-success mt-2">
              Matched
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }

  /**
   * Render Ask Coach button
   */
  renderAskCoachButton() {
    return `
      <div class="card bg-primary text-primary-content shadow-xl">
        <div class="card-body">
          <div class="flex flex-col md:flex-row justify-between items-center gap-4">
            <div>
              <h3 class="card-title">Need help with your plan?</h3>
              <p class="text-sm opacity-90">Chat with your AI coach for guidance and adjustments</p>
            </div>
            <a href="/chat.html?context=plan:${this.planId}" class="btn btn-secondary gap-2">
              💬 Ask Coach
            </a>
          </div>
        </div>
      </div>
    `;
  }

  /**
   * Initialize adherence chart
   */
  async initAdherenceChart() {
    try {
      const response = await api.get(`/training-plans/${this.planId}/adherence`);
      
      this.adherenceChart = new AdherenceChart('adherence-chart-container', {
        data: response.adherence_by_week,
        overallAdherence: response.overall_adherence
      });
      
      this.adherenceChart.render();
    } catch (error) {
      console.error('Failed to load adherence data:', error);
      document.getElementById('adherence-chart-container').innerHTML = `
        <div class="text-center text-base-content/60 py-8">
          <p>Unable to load adherence chart</p>
        </div>
      `;
    }
  }

  /**
   * Get status badge HTML
   */
  getStatusBadge(status) {
    const badges = {
      draft: '<span class="badge badge-ghost badge-lg">Draft</span>',
      active: '<span class="badge badge-success badge-lg">Active</span>',
      completed: '<span class="badge badge-info badge-lg">Completed</span>',
      abandoned: '<span class="badge badge-warning badge-lg">Abandoned</span>'
    };
    
    return badges[status] || badges.draft;
  }

  /**
   * Get adherence color class
   */
  getAdherenceColorClass(percentage) {
    if (percentage >= 80) return 'text-success';
    if (percentage >= 60) return 'text-warning';
    return 'text-error';
  }

  /**
   * Get progress bar color class
   */
  getProgressColorClass(percentage) {
    if (percentage >= 80) return 'bg-success';
    if (percentage >= 60) return 'bg-warning';
    return 'bg-error';
  }

  /**
   * Get completed sessions count
   */
  getCompletedSessions() {
    let count = 0;
    this.plan.weeks.forEach(week => {
      week.sessions.forEach(session => {
        if (session.completed) count++;
      });
    });
    return count;
  }

  /**
   * Get total sessions count
   */
  getTotalSessions() {
    let count = 0;
    this.plan.weeks.forEach(week => {
      count += week.sessions.length;
    });
    return count;
  }

  /**
   * Get time progress percentage
   */
  getTimeProgress() {
    const startDate = new Date(this.plan.start_date);
    const endDate = new Date(this.plan.end_date);
    const now = new Date();
    
    if (now < startDate) return 0;
    if (now > endDate) return 100;
    
    const totalDuration = endDate - startDate;
    const elapsed = now - startDate;
    
    return Math.round((elapsed / totalDuration) * 100);
  }

  /**
   * Get elapsed weeks
   */
  getElapsedWeeks() {
    const startDate = new Date(this.plan.start_date);
    const now = new Date();
    
    if (now < startDate) return 0;
    
    const elapsed = now - startDate;
    const weeks = Math.floor(elapsed / (7 * 24 * 60 * 60 * 1000)) + 1;
    
    return Math.min(weeks, this.plan.weeks.length);
  }

  /**
   * Get status description
   */
  getStatusDescription() {
    const descriptions = {
      draft: 'Plan not started yet',
      active: 'Currently in progress',
      completed: 'Plan finished',
      abandoned: 'Plan discontinued'
    };
    
    return descriptions[this.plan.status] || '';
  }

  /**
   * Format session type
   */
  formatSessionType(type) {
    return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
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
   * Render error message
   */
  renderError(message) {
    this.container.innerHTML = `
      <div class="alert alert-error">
        <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>Error: ${message}</span>
      </div>
    `;
  }

  /**
   * Reload plan and re-render
   */
  async refresh() {
    await this.loadPlan();
    this.render();
  }
}

/**
 * ActivityList Component
 * Displays activities in a paginated table with filtering and sorting
 */

class ActivityList {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      throw new Error(`Container with id "${containerId}" not found`);
    }
    
    // Configuration
    this.pageSize = options.pageSize || 25;
    this.currentPage = 1;
    this.totalActivities = 0;
    this.activities = [];
    
    // Filters
    this.filters = {
      type: null,
      date_from: null,
      date_to: null,
      distance_min: null,
      distance_max: null
    };
    
    // Sorting
    this.sortBy = 'start_date';
    this.sortDir = 'desc';
    
    // Callbacks
    this.onRowClick = options.onRowClick || null;
  }

  /**
   * Initialize the component and load data
   */
  async init() {
    await this.loadActivities();
    this.render();
  }

  /**
   * Load activities from the API
   */
  async loadActivities() {
    try {
      const params = {
        page: this.currentPage,
        page_size: this.pageSize,
        sort_by: this.sortBy,
        sort_dir: this.sortDir,
        ...this.filters
      };
      
      const response = await api.getActivities(params);
      this.activities = response.activities || [];
      this.totalActivities = response.total || 0;
    } catch (error) {
      console.error('Failed to load activities:', error);
      showError(error);
      this.activities = [];
      this.totalActivities = 0;
    }
  }

  /**
   * Render the complete component
   */
  render() {
    this.container.innerHTML = `
      <div class="activity-list">
        ${this.renderFilters()}
        ${this.renderTable()}
        ${this.renderPagination()}
      </div>
    `;
    
    this.attachEventListeners();
  }

  /**
   * Render filter controls
   */
  renderFilters() {
    return `
      <div class="mb-4 p-4 bg-base-200 rounded-lg">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <!-- Activity Type Filter -->
          <div class="form-control">
            <label class="label">
              <span class="label-text">Activity Type</span>
            </label>
            <select id="filter-type" class="select select-bordered select-sm w-full">
              <option value="">All Types</option>
              <option value="Run" ${this.filters.type === 'Run' ? 'selected' : ''}>Run</option>
              <option value="Ride" ${this.filters.type === 'Ride' ? 'selected' : ''}>Ride</option>
              <option value="WeightTraining" ${this.filters.type === 'WeightTraining' ? 'selected' : ''}>Weight Training</option>
              <option value="Swim" ${this.filters.type === 'Swim' ? 'selected' : ''}>Swim</option>
              <option value="Walk" ${this.filters.type === 'Walk' ? 'selected' : ''}>Walk</option>
              <option value="Hike" ${this.filters.type === 'Hike' ? 'selected' : ''}>Hike</option>
            </select>
          </div>

          <!-- Date From Filter -->
          <div class="form-control">
            <label class="label">
              <span class="label-text">From Date</span>
            </label>
            <input 
              type="date" 
              id="filter-date-from" 
              class="input input-bordered input-sm w-full"
              value="${this.filters.date_from || ''}"
            />
          </div>

          <!-- Date To Filter -->
          <div class="form-control">
            <label class="label">
              <span class="label-text">To Date</span>
            </label>
            <input 
              type="date" 
              id="filter-date-to" 
              class="input input-bordered input-sm w-full"
              value="${this.filters.date_to || ''}"
            />
          </div>

          <!-- Distance Min Filter -->
          <div class="form-control">
            <label class="label">
              <span class="label-text">Min Distance (km)</span>
            </label>
            <input 
              type="number" 
              id="filter-distance-min" 
              class="input input-bordered input-sm w-full"
              placeholder="0"
              min="0"
              step="0.1"
              value="${this.filters.distance_min || ''}"
            />
          </div>

          <!-- Distance Max Filter -->
          <div class="form-control">
            <label class="label">
              <span class="label-text">Max Distance (km)</span>
            </label>
            <input 
              type="number" 
              id="filter-distance-max" 
              class="input input-bordered input-sm w-full"
              placeholder="∞"
              min="0"
              step="0.1"
              value="${this.filters.distance_max || ''}"
            />
          </div>
        </div>

        <!-- Filter Actions -->
        <div class="flex gap-2 mt-4">
          <button id="apply-filters-btn" class="btn btn-primary btn-sm">
            Apply Filters
          </button>
          <button id="clear-filters-btn" class="btn btn-ghost btn-sm">
            Clear Filters
          </button>
        </div>
      </div>
    `;
  }

  /**
   * Render the activities table
   */
  renderTable() {
    if (this.activities.length === 0) {
      return `
        <div class="text-center py-8">
          <p class="text-base-content/60">No activities found. Sync your Strava activities to get started.</p>
        </div>
      `;
    }

    return `
      <div class="overflow-x-auto">
        <table class="table table-zebra w-full">
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th class="sortable cursor-pointer hover:bg-base-200" data-sort-column="start_date">
                Date ${this.renderSortIndicator('start_date')}
              </th>
              <th class="sortable cursor-pointer hover:bg-base-200" data-sort-column="distance_m">
                Distance ${this.renderSortIndicator('distance_m')}
              </th>
              <th class="sortable cursor-pointer hover:bg-base-200" data-sort-column="moving_time_s">
                Duration ${this.renderSortIndicator('moving_time_s')}
              </th>
              <th class="sortable cursor-pointer hover:bg-base-200" data-sort-column="elevation_m">
                Elevation ${this.renderSortIndicator('elevation_m')}
              </th>
              <th class="sortable cursor-pointer hover:bg-base-200" data-sort-column="calories">
                Calories ${this.renderSortIndicator('calories')}
              </th>
            </tr>
          </thead>
          <tbody>
            ${this.activities.map(activity => this.renderActivityRow(activity)).join('')}
          </tbody>
        </table>
      </div>
    `;
  }

  /**
   * Render sort indicator for a column
   */
  renderSortIndicator(column) {
    if (this.sortBy !== column) {
      return '<span class="inline-block ml-1 text-base-content/30">↕</span>';
    }
    
    const arrow = this.sortDir === 'asc' ? '↑' : '↓';
    return `<span class="inline-block ml-1 text-primary">${arrow}</span>`;
  }

  /**
   * Render a single activity row
   */
  renderActivityRow(activity) {
    const name = this.getActivityName(activity);
    const type = activity.activity_type || 'Unknown';
    const date = this.formatDate(activity.start_date);
    const distance = this.formatDistance(activity.distance_m);
    const duration = this.formatDuration(activity.moving_time_s);
    const elevation = this.formatElevation(activity.elevation_m);
    const calories = this.formatCalories(activity.calories);
    
    return `
      <tr class="hover cursor-pointer" data-activity-id="${activity.strava_id}">
        <td class="font-medium">${name}</td>
        <td>
          <span class="badge badge-outline">${type}</span>
        </td>
        <td>${date}</td>
        <td>${distance}</td>
        <td>${duration}</td>
        <td>${elevation}</td>
        <td>${calories}</td>
      </tr>
    `;
  }

  /**
   * Render pagination controls
   */
  renderPagination() {
    const totalPages = Math.ceil(this.totalActivities / this.pageSize);
    
    if (totalPages <= 1) {
      return '';
    }

    const startRecord = (this.currentPage - 1) * this.pageSize + 1;
    const endRecord = Math.min(this.currentPage * this.pageSize, this.totalActivities);

    return `
      <div class="flex justify-between items-center mt-4">
        <div class="text-sm text-base-content/60">
          Showing ${startRecord}-${endRecord} of ${this.totalActivities} activities
        </div>
        <div class="join">
          <button class="join-item btn btn-sm" data-page="prev" ${this.currentPage === 1 ? 'disabled' : ''}>
            «
          </button>
          ${this.renderPageNumbers(totalPages)}
          <button class="join-item btn btn-sm" data-page="next" ${this.currentPage === totalPages ? 'disabled' : ''}>
            »
          </button>
        </div>
      </div>
    `;
  }

  /**
   * Render page number buttons
   */
  renderPageNumbers(totalPages) {
    const pages = [];
    const maxVisible = 5;
    
    let startPage = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    
    if (endPage - startPage < maxVisible - 1) {
      startPage = Math.max(1, endPage - maxVisible + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
      const isActive = i === this.currentPage;
      pages.push(`
        <button class="join-item btn btn-sm ${isActive ? 'btn-active' : ''}" data-page="${i}">
          ${i}
        </button>
      `);
    }

    return pages.join('');
  }

  /**
   * Attach event listeners
   */
  attachEventListeners() {
    // Filter button handlers
    const applyFiltersBtn = this.container.querySelector('#apply-filters-btn');
    const clearFiltersBtn = this.container.querySelector('#clear-filters-btn');
    
    if (applyFiltersBtn) {
      applyFiltersBtn.addEventListener('click', () => {
        this.handleApplyFilters();
      });
    }
    
    if (clearFiltersBtn) {
      clearFiltersBtn.addEventListener('click', () => {
        this.handleClearFilters();
      });
    }

    // Sortable column header handlers
    const sortableHeaders = this.container.querySelectorAll('th.sortable[data-sort-column]');
    sortableHeaders.forEach(header => {
      header.addEventListener('click', () => {
        const column = header.dataset.sortColumn;
        this.handleSort(column);
      });
    });

    // Row click handlers
    const rows = this.container.querySelectorAll('tr[data-activity-id]');
    rows.forEach(row => {
      row.addEventListener('click', () => {
        const activityId = row.dataset.activityId;
        if (this.onRowClick) {
          this.onRowClick(activityId);
        } else {
          // Default behavior: navigate to detail page
          window.location.href = `/activities/${activityId}`;
        }
      });
    });

    // Pagination handlers
    const paginationButtons = this.container.querySelectorAll('button[data-page]');
    paginationButtons.forEach(button => {
      button.addEventListener('click', async () => {
        const page = button.dataset.page;
        
        if (page === 'prev' && this.currentPage > 1) {
          this.currentPage--;
        } else if (page === 'next') {
          const totalPages = Math.ceil(this.totalActivities / this.pageSize);
          if (this.currentPage < totalPages) {
            this.currentPage++;
          }
        } else if (!isNaN(page)) {
          this.currentPage = parseInt(page);
        }
        
        await this.loadActivities();
        this.render();
      });
    });
  }

  /**
   * Handle sort column click
   */
  async handleSort(column) {
    // Toggle direction if clicking the same column, otherwise default to descending
    if (this.sortBy === column) {
      this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortBy = column;
      this.sortDir = 'desc'; // Default to descending for new column
    }
    
    this.currentPage = 1; // Reset to first page
    await this.loadActivities();
    this.render();
  }

  /**
   * Handle apply filters button click
   */
  async handleApplyFilters() {
    const typeSelect = this.container.querySelector('#filter-type');
    const dateFromInput = this.container.querySelector('#filter-date-from');
    const dateToInput = this.container.querySelector('#filter-date-to');
    const distanceMinInput = this.container.querySelector('#filter-distance-min');
    const distanceMaxInput = this.container.querySelector('#filter-distance-max');
    
    const filters = {
      type: typeSelect.value || null,
      date_from: dateFromInput.value || null,
      date_to: dateToInput.value || null,
      distance_min: distanceMinInput.value ? parseFloat(distanceMinInput.value) : null,
      distance_max: distanceMaxInput.value ? parseFloat(distanceMaxInput.value) : null
    };
    
    await this.applyFilters(filters);
  }

  /**
   * Handle clear filters button click
   */
  async handleClearFilters() {
    this.filters = {
      type: null,
      date_from: null,
      date_to: null,
      distance_min: null,
      distance_max: null
    };
    
    this.currentPage = 1;
    await this.loadActivities();
    this.render();
  }

  /**
   * Apply filters and reload
   */
  async applyFilters(filters) {
    this.filters = { ...this.filters, ...filters };
    this.currentPage = 1; // Reset to first page
    await this.loadActivities();
    this.render();
  }

  /**
   * Apply sorting and reload
   */
  async applySorting(column, direction = 'asc') {
    this.sortBy = column;
    this.sortDir = direction;
    this.currentPage = 1; // Reset to first page
    await this.loadActivities();
    this.render();
  }

  /**
   * Set page and reload
   */
  async setPage(pageNumber) {
    const totalPages = Math.ceil(this.totalActivities / this.pageSize);
    if (pageNumber >= 1 && pageNumber <= totalPages) {
      this.currentPage = pageNumber;
      await this.loadActivities();
      this.render();
    }
  }

  /**
   * Get activity name (fallback to type + date if no name)
   */
  getActivityName(activity) {
    // For now, generate a name from type and date since we don't have a name field
    const type = activity.activity_type || 'Activity';
    const date = new Date(activity.start_date);
    const time = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    return `${type} - ${time}`;
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
   * Format distance (meters to km)
   */
  formatDistance(meters) {
    if (!meters || meters === 0) return '-';
    return `${(meters / 1000).toFixed(1)} km`;
  }

  /**
   * Format duration (seconds to HH:MM:SS or MM:SS)
   */
  formatDuration(seconds) {
    if (!seconds || seconds === 0) return '-';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${minutes}:${String(secs).padStart(2, '0')}`;
  }

  /**
   * Format elevation (meters)
   */
  formatElevation(meters) {
    if (!meters || meters === 0) return '-';
    return `${Math.round(meters)} m`;
  }

  /**
   * Format calories
   */
  formatCalories(calories) {
    if (!calories || calories === 0) return '-';
    return `${Math.round(calories)} kcal`;
  }
}

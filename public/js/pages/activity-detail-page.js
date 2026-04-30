/**
 * ActivityDetailPage
 * Equivalent to activity-detail.html + its inline <script>.
 */

class ActivityDetailPage {
    constructor() {
      this._detail = null;
    }
  
    async init(params, query) {
      const activityId = params.id;
  
      window.renderPage(this._html());
      await this._tick();
  
      if (!activityId) {
        this._showError('Invalid activity ID');
        return;
      }
  
      this._detail = new ActivityDetail('activity-detail-container', activityId);
      await this._detail.init();
    }
  
    destroy() {}
  
    // ─── Private ────────────────────────────────────────────────────────────────
  
    _html() {
      return `
        <!-- flex-1 min-h-0 lets this div fill main-content (flex flex-col h-full overflow-hidden) -->
        <div class="flex flex-col flex-1 min-h-0">

          <!-- Loading State -->
          <div id="loading-container" class="flex justify-center items-center py-12 px-6">
            <span class="loading loading-spinner loading-lg"></span>
          </div>

          <!-- Error State -->
          <div id="error-container" class="hidden px-6 pt-6">
            <div class="alert alert-error">
              <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span id="error-message">Failed to load activity details</span>
            </div>
          </div>

          <!-- flex flex-col flex-1 min-h-0: fills remaining space; hidden removed by component -->
          <div id="activity-detail-container" class="hidden flex flex-col flex-1 min-h-0">

            <!-- ── FIXED HEADER: back button + title/badges + 4 stat cards ── -->
            <div class="shrink-0 bg-base-200 shadow-sm px-6 pt-5 pb-4 z-30">
              <div class="mb-3">
                <a href="/activities" data-spa-link class="btn btn-ghost btn-sm">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd" />
                  </svg>
                  Back to Activities
                </a>
              </div>

              <div class="mb-4">
                <h1 id="activity-title" class="text-4xl font-bold mb-2"></h1>
                <div class="flex flex-wrap gap-2">
                  <span id="activity-type-badge" class="badge badge-primary badge-lg"></span>
                  <span id="activity-date"       class="badge badge-outline badge-lg"></span>
                </div>
              </div>

              <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <div class="card bg-base-100 shadow"><div class="card-body py-3 px-4">
                  <h3 class="card-title text-xs text-base-content/70 uppercase tracking-wide">Distance</h3>
                  <p id="stat-distance" class="text-2xl font-bold">--</p>
                </div></div>
                <div class="card bg-base-100 shadow"><div class="card-body py-3 px-4">
                  <h3 class="card-title text-xs text-base-content/70 uppercase tracking-wide">Duration</h3>
                  <p id="stat-duration" class="text-2xl font-bold">--</p>
                </div></div>
                <div class="card bg-base-100 shadow"><div class="card-body py-3 px-4">
                  <h3 class="card-title text-xs text-base-content/70 uppercase tracking-wide" id="pace-label">Pace</h3>
                  <p id="stat-pace" class="text-2xl font-bold">--</p>
                </div></div>
                <div class="card bg-base-100 shadow"><div class="card-body py-3 px-4">
                  <h3 class="card-title text-xs text-base-content/70 uppercase tracking-wide">Elevation</h3>
                  <p id="stat-elevation" class="text-2xl font-bold">--</p>
                </div></div>
              </div>
            </div>

            <!-- ── SCROLLABLE BODY: flex-1 min-h-0 overflow-y-auto owns the scroll ── -->
            <div class="flex-1 min-h-0 overflow-y-auto px-6 pb-6 pt-5 space-y-5">

              <div id="heart-rate-section" class="card bg-base-100 shadow-xl hidden">
                <div class="card-body">
                  <h2 class="card-title">Heart Rate</h2>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div><p class="text-sm text-base-content/70">Average HR</p>
                      <p id="stat-avg-hr" class="text-2xl font-bold">--</p></div>
                    <div><p class="text-sm text-base-content/70">Max HR</p>
                      <p id="stat-max-hr" class="text-2xl font-bold">--</p></div>
                  </div>
                </div>
              </div>

              <div id="performance-section" class="card bg-base-100 shadow-xl hidden">
                <div class="card-body">
                  <h2 class="card-title">Performance Metrics</h2>
                  <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div id="avg-cadence-detail" class="hidden">
                      <p class="text-sm text-base-content/70">Avg Cadence</p>
                      <p id="stat-avg-cadence" class="text-2xl font-bold">--</p>
                    </div>
                    <div id="max-cadence-detail" class="hidden">
                      <p class="text-sm text-base-content/70">Max Cadence</p>
                      <p id="stat-max-cadence" class="text-2xl font-bold">--</p>
                    </div>
                    <div id="avg-watts-detail" class="hidden">
                      <p class="text-sm text-base-content/70">Avg Power</p>
                      <p id="stat-avg-watts" class="text-2xl font-bold">--</p>
                    </div>
                    <div id="weighted-watts-detail" class="hidden">
                      <p class="text-sm text-base-content/70">Normalized Power</p>
                      <p id="stat-weighted-watts" class="text-2xl font-bold">--</p>
                    </div>
                  </div>
                </div>
              </div>

              <div id="splits-section" class="card bg-base-100 shadow-xl hidden">
                <div class="card-body">
                  <h2 class="card-title mb-4">Splits</h2>
                  <div class="overflow-x-auto">
                    <table class="table table-zebra">
                      <thead><tr><th>Split</th><th>Distance</th><th>Time</th><th>Pace</th><th>Elevation</th></tr></thead>
                      <tbody id="splits-table-body"></tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div id="map-section" class="card bg-base-100 shadow-xl hidden">
                <div class="card-body">
                  <h2 class="card-title mb-4">Route Map</h2>
                  <div id="activity-map" class="w-full h-96 bg-base-200 rounded-lg"></div>
                </div>
              </div>

              <div id="analysis-section" class="card bg-base-100 shadow-xl hidden">
                <div class="card-body">
                  <h2 class="card-title mb-4">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    AI Effort Analysis
                  </h2>
                  <div id="analysis-loading" class="flex items-center gap-2 text-base-content/70">
                    <span class="loading loading-spinner loading-sm"></span>
                    <span>Generating effort analysis...</span>
                  </div>
                  <div id="analysis-content" class="hidden prose max-w-none"></div>
                  <div id="analysis-error" class="hidden alert alert-warning">
                    <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <span>Unable to generate effort analysis at this time.</span>
                  </div>
                </div>
              </div>

              <div class="card bg-base-100 shadow-xl">
                <div class="card-body">
                  <h2 class="card-title mb-4">Additional Details</h2>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div id="calories-detail" class="hidden">
                      <p class="text-sm text-base-content/70">Calories</p>
                      <p id="stat-calories" class="text-xl font-semibold">--</p>
                    </div>
                    <div id="suffer-score-detail" class="hidden">
                      <p class="text-sm text-base-content/70">Suffer Score</p>
                      <p id="stat-suffer-score" class="text-xl font-semibold">--</p>
                    </div>
                    <div id="sport-type-detail" class="hidden">
                      <p class="text-sm text-base-content/70">Sport Type</p>
                      <p id="stat-sport-type" class="text-xl font-semibold">--</p>
                    </div>
                    <div>
                      <p class="text-sm text-base-content/70">Activity ID</p>
                      <p id="stat-activity-id" class="text-xl font-semibold">--</p>
                    </div>
                  </div>
                  <div id="enriched-badge" class="hidden mt-3">
                    <span class="badge badge-success badge-sm">Data refreshed from Strava</span>
                  </div>
                </div>
              </div>

            </div><!-- end scrollable body -->
          </div><!-- end activity-detail-container -->
        </div>`;
    }
  
    _showError(message) {
      const loading = document.getElementById('loading-container');
      const error   = document.getElementById('error-container');
      const msg     = document.getElementById('error-message');
      if (loading) loading.classList.add('hidden');
      if (msg)     msg.textContent = message;
      if (error)   error.classList.remove('hidden');
    }
  
    _tick() {
      return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    }
  }
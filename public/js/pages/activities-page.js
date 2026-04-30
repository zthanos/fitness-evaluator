/**
 * ActivitiesPage
 *
 * Wraps the Activities view for the SPA.
 * Equivalent to the old activities.html + its inline <script>.
 */

class ActivitiesPage {
    constructor() {
      this._activityList = null;
    }
  
    async init(params, query) {
      window.renderPage(this._html());
  
      // Wait for the DOM to be updated
      await this._tick();
  
      // Init activity list component
      this._activityList = new ActivityList('activities-container', {
        pageSize: 25,
        onRowClick: (activityId) => {
          router.navigate(`/activities/${activityId}`);
        },
      });
      await this._activityList.init();
  
      // Strava sync button
      const syncBtn = document.getElementById('sync-strava-btn');
      if (syncBtn) {
        syncBtn.addEventListener('click', () => this._handleStravaSync(syncBtn));
      }

      // Enrich details button
      const enrichBtn = document.getElementById('enrich-activities-btn');
      if (enrichBtn) {
        enrichBtn.addEventListener('click', () => this._handleEnrich(enrichBtn));
      }
    }
  
    destroy() {
      // Nothing special — renderPage() will overwrite the DOM
    }
  
    // ─── Private ────────────────────────────────────────────────────────────────
  
    _html() {
      return `
        <div class="p-6">
          <div class="flex justify-between items-center mb-6">
            <h1 class="text-4xl font-bold">⚡ Activities</h1>
            <div class="flex gap-2">
              <button id="enrich-activities-btn" class="btn btn-outline gap-2" title="Fetch full detail data (cadence, power, splits) for recent activities">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clip-rule="evenodd" />
                </svg>
                Enrich Details
              </button>
              <button id="sync-strava-btn" class="btn btn-primary gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd" />
                </svg>
                Sync Strava Activities
              </button>
            </div>
          </div>
  
          <div class="card bg-base-100 shadow-xl">
            <div class="card-body">
              <h2 class="card-title mb-4">Activity List</h2>
              <div id="activities-container">
                <div class="flex justify-center items-center py-8">
                  <span class="loading loading-spinner loading-lg"></span>
                </div>
              </div>
            </div>
          </div>
        </div>`;
    }
  
    async _handleStravaSync(button) {
      button.disabled = true;
      const originalHTML = button.innerHTML;
      button.innerHTML = `<span class="loading loading-spinner loading-sm"></span> Syncing...`;

      try {
        const token = window.getAuthToken?.();
        const response = await fetch(`${api.baseUrl}/auth/strava/sync`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          },
        });

        if (!response.ok) {
          const err = await response.json();
          throw new Error(err.detail || 'Sync failed');
        }

        const result = await response.json();
        showToast(`⏳ ${result.message}`, 'info');

        // Sync runs in background — reload after 15 s to pick up new activities
        setTimeout(async () => {
          await this._activityList.loadActivities();
          this._activityList.render();
        }, 15_000);
      } catch (err) {
        console.error('Strava sync failed:', err);
        if (err.message.includes('revoked')) {
          showToast('❌ Strava authorization revoked. Reconnect in Settings.', 'error');
        } else if (err.message.includes('No Strava token')) {
          showToast('⚠️ Strava not connected. Connect in Settings.', 'warning');
        } else {
          showToast(`❌ Sync failed: ${err.message}`, 'error');
        }
      } finally {
        button.disabled = false;
        button.innerHTML = originalHTML;
      }
    }
  
    async _handleEnrich(button) {
      button.disabled = true;
      const originalHTML = button.innerHTML;
      button.innerHTML = `<span class="loading loading-spinner loading-sm"></span> Enriching...`;

      try {
        const token = window.getAuthToken?.();
        const response = await fetch(`${api.baseUrl}/strava/enrich?days=60`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          },
        });

        if (!response.ok) {
          const err = await response.json();
          throw new Error(err.detail || 'Enrichment failed');
        }

        const result = await response.json();
        showToast(`⚡ ${result.message}`, 'info');
      } catch (err) {
        console.error('Enrichment failed:', err);
        showToast(`❌ Enrichment failed: ${err.message}`, 'error');
      } finally {
        button.disabled = false;
        button.innerHTML = originalHTML;
      }
    }

    _tick() {
      return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    }
  }
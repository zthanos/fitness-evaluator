import { api }               from '/js/api.js';
import { router }            from '/js/router.js';
import { ActivityList }      from '/js/components/activity-list.js';
import { ActivityDetail }    from '/js/components/activity-detail.js';
import { DailyLogForm }      from '/js/daily-log-form.js';
import { DailyLogList }      from '/js/daily-log-list.js';
import { MetricsForm }       from '/js/metrics-form.js';
import { MetricsChart }      from '/js/metrics-chart.js';
import { MetricsList }       from '/js/metrics-list.js';
import { CoachChat }         from '/js/coach-chat.js';
import { TrainingPlansList } from '/js/training-plans-list.js';
import { GoalsManager }       from '/js/goals.js';
import { SettingsManager }    from '/js/settings.js';
import { AppSettingsManager } from '/js/app-settings.js';
import { getWeekStart }      from '/js/utils.js';

// ─── DashboardPage ────────────────────────────────────────────────────────────

class DashboardPage {
  async init(params, query) {
    this.activityVolumeChart = null;
    this.weightTrendChart = null;
    
    await this.loadDashboard();
  }
  
  async loadDashboard() {
    try {
      await Promise.all([
        this.loadStats(),
        this.loadActivityVolumeChart(),
        this.loadWeightTrendChart(),
        this.loadRecentActivities(),
        this.loadRecentLogs(),
        this.loadLatestEvaluation(),
        this.loadSportProfiles(),
      ]);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    }
  }
  
  async loadStats() {
    try {
      const response = await api.get('/dashboard/stats');
      const stats = response;
      
      document.getElementById('stat-activities').textContent = stats.total_activities || '0';
      document.getElementById('stat-weight').textContent = stats.current_weight ? `${stats.current_weight} kg` : '--';
      document.getElementById('stat-adherence').textContent = stats.weekly_adherence_avg ? `${stats.weekly_adherence_avg}/10` : '--';
      
      if (stats.latest_evaluation_score) {
        document.getElementById('stat-eval-score').textContent = `${stats.latest_evaluation_score}/10`;
      } else {
        document.getElementById('stat-eval-score').textContent = '--';
      }
      
      if (stats.latest_evaluation_date) {
        const date = new Date(stats.latest_evaluation_date);
        document.getElementById('stat-eval-date').textContent = date.toLocaleDateString('en-US', { 
          year: 'numeric', month: 'short', day: 'numeric' 
        });
      }
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  }
  
  async loadActivityVolumeChart() {
    try {
      const data = await api.get('/dashboard/charts/activity-volume');
      const ctx = document.getElementById('activity-volume-chart').getContext('2d');
      
      if (this.activityVolumeChart) {
        this.activityVolumeChart.destroy();
      }
      
      this.activityVolumeChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: data.data_points.map(d => {
            const date = new Date(d.week_start);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
          }),
          datasets: [{
            label: 'Distance (km)',
            data: data.data_points.map(d => d.total_distance_km),
            backgroundColor: 'rgba(59, 130, 246, 0.5)',
            borderColor: 'rgba(59, 130, 246, 1)',
            borderWidth: 1
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          scales: {
            y: {
              beginAtZero: true,
              title: { display: true, text: 'Distance (km)' }
            }
          }
        }
      });
    } catch (error) {
      console.error('Error loading activity volume chart:', error);
    }
  }
  
  async loadWeightTrendChart() {
    try {
      const data = await api.get('/dashboard/charts/weight-trend');
      const ctx = document.getElementById('weight-trend-chart').getContext('2d');
      
      if (this.weightTrendChart) {
        this.weightTrendChart.destroy();
      }
      
      this.weightTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: data.data_points.map(d => {
            const date = new Date(d.measurement_date);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
          }),
          datasets: [{
            label: 'Weight (kg)',
            data: data.data_points.map(d => d.weight_kg),
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            borderColor: 'rgba(16, 185, 129, 1)',
            borderWidth: 2,
            tension: 0.4,
            fill: true
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: true,
          scales: {
            y: {
              beginAtZero: false,
              title: { display: true, text: 'Weight (kg)' }
            }
          }
        }
      });
    } catch (error) {
      console.error('Error loading weight trend chart:', error);
    }
  }
  
  async loadRecentActivities() {
    try {
      const data = await api.get('/dashboard/recent/activities');
      const container = document.getElementById('recent-activities-list');
      
      if (data.activities.length === 0) {
        container.innerHTML = '<p class="text-base-content/60">No activities yet. Connect Strava to sync your workouts!</p>';
        return;
      }
      
      container.innerHTML = data.activities.map(activity => `
        <div class="flex justify-between items-center p-3 bg-base-200 rounded-lg hover:bg-base-300 transition-colors">
          <div class="flex-1">
            <p class="font-semibold">${activity.activity_type}</p>
            <p class="text-sm text-base-content/60">${new Date(activity.start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</p>
          </div>
          <div class="text-right">
            <p class="font-semibold">${activity.distance_km} km</p>
            <p class="text-sm text-base-content/60">${activity.duration_min} min</p>
          </div>
        </div>
      `).join('');
    } catch (error) {
      console.error('Error loading recent activities:', error);
      document.getElementById('recent-activities-list').innerHTML = '<p class="text-error">Failed to load activities</p>';
    }
  }
  
  async loadRecentLogs() {
    try {
      const data = await api.get('/dashboard/recent/logs');
      const container = document.getElementById('recent-logs-list');
      
      if (data.logs.length === 0) {
        container.innerHTML = '<p class="text-base-content/60">No logs yet. Start tracking your daily nutrition!</p>';
        return;
      }
      
      container.innerHTML = data.logs.map(log => `
        <div class="flex justify-between items-center p-3 bg-base-200 rounded-lg hover:bg-base-300 transition-colors">
          <div class="flex-1">
            <p class="font-semibold">${new Date(log.log_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</p>
            <p class="text-sm text-base-content/60">Adherence: ${log.adherence_score || '--'}/10</p>
          </div>
          <div class="text-right">
            <p class="font-semibold">${log.calories_in || '--'} kcal</p>
            <p class="text-sm text-base-content/60">${log.protein_g || '--'}g protein</p>
          </div>
        </div>
      `).join('');
    } catch (error) {
      console.error('Error loading recent logs:', error);
      document.getElementById('recent-logs-list').innerHTML = '<p class="text-error">Failed to load logs</p>';
    }
  }
  
  async loadLatestEvaluation() {
    try {
      const data = await api.get('/dashboard/latest-evaluation');
      const container = document.getElementById('latest-eval-summary');
      
      if (!data || !data.score) {
        container.innerHTML = `
          <div class="text-center py-8">
            <p class="text-base-content/60 mb-4">No evaluations yet. Generate your first evaluation!</p>
            <a href="/evaluations" class="btn btn-primary">Generate Evaluation</a>
          </div>
        `;
        return;
      }
      
      const strengthsList = data.top_strengths?.length > 0 
        ? data.top_strengths.map(s => `<li class="flex items-start gap-2"><span class="text-success text-xl">✓</span><span>${s}</span></li>`).join('')
        : '<li class="text-base-content/60">No strengths recorded</li>';
      
      const improvementsList = data.top_improvements?.length > 0
        ? data.top_improvements.map(i => `<li class="flex items-start gap-2"><span class="text-warning text-xl">⚠</span><span>${i}</span></li>`).join('')
        : '<li class="text-base-content/60">No improvements recorded</li>';
      
      const scoreColor = data.score >= 80 ? 'text-success' : data.score >= 60 ? 'text-warning' : data.score >= 40 ? 'text-info' : 'text-error';
      
      container.innerHTML = `
        <div class="flex flex-col md:flex-row gap-6">
          <div class="flex-shrink-0 text-center">
            <div class="radial-progress ${scoreColor}" style="--value:${data.score}; --size:10rem; --thickness:0.6rem;" role="progressbar">
              <div class="flex flex-col">
                <span class="text-3xl font-bold">${data.score}</span>
                <span class="text-sm text-base-content/60">out of 100</span>
              </div>
            </div>
            <p class="text-sm text-base-content/60 mt-3">${data.period_type || 'Weekly'} Evaluation</p>
            <p class="text-xs text-base-content/50">
              ${new Date(data.period_start).toLocaleDateString()} - ${new Date(data.period_end).toLocaleDateString()}
            </p>
            <a href="/evaluations" class="btn btn-sm btn-primary mt-3">View Full Report</a>
          </div>
          <div class="flex-1 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h3 class="font-semibold mb-2 text-success">✓ Top Strengths:</h3>
              <ul class="space-y-2">${strengthsList}</ul>
            </div>
            <div>
              <h3 class="font-semibold mb-2 text-warning">⚠ Areas for Improvement:</h3>
              <ul class="space-y-2">${improvementsList}</ul>
            </div>
          </div>
        </div>
      `;
    } catch (error) {
      console.error('Error loading latest evaluation:', error);
      const container = document.getElementById('latest-eval-summary');
      // Check if it's a 404 (no evaluations) or a real error
      if (error.message && (error.message.includes('404') || error.message.includes('not found'))) {
        container.innerHTML = `
          <div class="text-center py-8">
            <p class="text-base-content/60 mb-4">No evaluations yet. Generate your first evaluation!</p>
            <a href="/evaluations" class="btn btn-primary">Generate Evaluation</a>
          </div>
        `;
      } else {
        container.innerHTML = `<p class="text-error">Failed to load evaluation: ${error.message}</p>`;
      }
    }
  }
  
  async loadSportProfiles() {
    const container = document.getElementById('dashboard-sport-profiles');
    if (!container) return;
    try {
      const data = await api.get('/dashboard/sport-profiles');
      const profiles = data.profiles || [];
      const dominant = data.dominant_sport || {};

      if (profiles.length === 0) {
        container.innerHTML = `
          <div class="text-center py-6 text-base-content/60">
            <p class="mb-2">No sport profiles yet.</p>
            <a href="/profile" class="btn btn-sm btn-primary">Build Profiles in Profile</a>
          </div>`;
        return;
      }

      const sportMeta = {
        ride:     { label: 'Cycling',  icon: '🚴' },
        run:      { label: 'Running',  icon: '🏃' },
        swim:     { label: 'Swimming', icon: '🏊' },
        strength: { label: 'Strength', icon: '🏋️' },
      };
      const confClass = (c) => c >= 0.7 ? 'badge-success' : c >= 0.4 ? 'badge-warning' : 'badge-error';
      const fmt = (v, dec = 1) => v != null ? parseFloat(v).toFixed(dec) : '—';

      const cards = profiles.map(p => {
        const meta   = sportMeta[p.sport_group] || { label: p.sport_group, icon: '🏅' };
        const conf   = p.profile_confidence || 0;
        const isPri  = p.sport_group === dominant.primary;

        // No data
        if (conf < 0.15) {
          return `
            <div class="bg-base-200 rounded-xl p-4 opacity-60 flex flex-col gap-1">
              <div class="flex items-center justify-between">
                <span class="font-semibold flex items-center gap-1.5"><span class="text-lg">${meta.icon}</span> ${meta.label}</span>
                <span class="badge badge-ghost badge-xs">No data</span>
              </div>
              <p class="text-xs text-base-content/50">Insufficient sessions for analysis.</p>
            </div>`;
        }

        // Primary metric headline
        let headline = '';
        let secondaryPills = [];
        if (p.sport_group === 'ride') {
          if (p.ftp_estimate_w) headline = `<span class="text-2xl font-bold text-primary">${Math.round(p.ftp_estimate_w)}<span class="text-sm font-normal ml-0.5">W FTP</span></span>`;
          else if (p.typical_endurance_speed_kmh) headline = `<span class="text-2xl font-bold text-primary">${fmt(p.typical_endurance_speed_kmh)}<span class="text-sm font-normal ml-0.5">km/h</span></span>`;
          if (p.typical_endurance_speed_kmh && p.ftp_estimate_w) secondaryPills.push(`${fmt(p.typical_endurance_speed_kmh)} km/h`);
          if (p.typical_cadence_rpm) secondaryPills.push(`${Math.round(p.typical_cadence_rpm)} rpm`);
          if (p.weekly_volume_km) secondaryPills.push(`${fmt(p.weekly_volume_km)} km/wk`);
        } else if (p.sport_group === 'run') {
          if (p.easy_pace_min_per_km) {
            const paceLabel = p.hr_classified ? 'easy pace' : 'avg pace';
            headline = `<span class="text-2xl font-bold text-primary">${fmt(p.easy_pace_min_per_km)}<span class="text-sm font-normal ml-0.5">min/km ${paceLabel}</span></span>`;
          } else if (p.typical_endurance_speed_kmh) {
            const pace = (60 / p.typical_endurance_speed_kmh).toFixed(1);
            headline = `<span class="text-2xl font-bold text-primary">${pace}<span class="text-sm font-normal ml-0.5">min/km</span></span>`;
          }
          if (p.typical_run_km) secondaryPills.push(`${fmt(p.typical_run_km)} km typical`);
          if (p.longest_run_km) secondaryPills.push(`${fmt(p.longest_run_km)} km longest`);
          if (p.weekly_volume_km) secondaryPills.push(`${fmt(p.weekly_volume_km)} km/wk`);
        } else if (p.sport_group === 'strength') {
          const sessions = p.weekly_training_time_min ? Math.max(1, Math.round(p.weekly_training_time_min / 50)) : null;
          const stimulus = !p.weekly_training_time_min ? '' : p.weekly_training_time_min >= 120 ? 'Building' : 'Maintenance';
          if (sessions) headline = `<span class="text-2xl font-bold">${sessions}<span class="text-sm font-normal ml-0.5">×/wk</span></span>`;
          if (p.weekly_training_time_min) secondaryPills.push(`${Math.round(p.weekly_training_time_min)} min/wk`);
          if (stimulus) secondaryPills.push(stimulus);
        } else {
          if (p.weekly_training_time_min) headline = `<span class="text-2xl font-bold">${Math.round(p.weekly_training_time_min)}<span class="text-sm font-normal ml-0.5">min/wk</span></span>`;
        }
        if (p.max_hr_estimate) secondaryPills.push(`HR ${p.max_hr_estimate}`);

        // Top limiter only (concise)
        const topLimiter = (p.current_limiters || [])[0] || '';
        const topStrength = (p.current_strengths || [])[0] || '';

        return `
          <div class="bg-base-200 rounded-xl p-4 flex flex-col gap-2 ${isPri ? 'ring-1 ring-primary/30' : ''}">
            <div class="flex items-center justify-between">
              <span class="font-semibold flex items-center gap-1.5">
                <span class="text-lg">${meta.icon}</span> ${meta.label}
                ${isPri ? '<span class="badge badge-primary badge-xs">Primary</span>' : ''}
              </span>
              <span class="badge badge-sm ${confClass(conf)}">${conf >= 0.7 ? 'High' : conf >= 0.4 ? 'Med' : 'Low'}</span>
            </div>
            ${headline ? `<div class="my-0.5">${headline}</div>` : ''}
            ${secondaryPills.length ? `<div class="flex flex-wrap gap-1">${secondaryPills.map(t => `<span class="badge badge-ghost badge-xs text-base-content/60">${t}</span>`).join('')}</div>` : ''}
            ${topStrength ? `<p class="text-xs text-success/80 leading-snug">✓ ${topStrength}</p>` : ''}
            ${topLimiter  ? `<p class="text-xs text-warning/80 leading-snug">⚠ ${topLimiter}</p>` : ''}
            ${p.next_focus ? `<p class="text-[11px] text-primary/70 leading-snug border-t border-base-300 pt-1.5 mt-0.5">🎯 ${p.next_focus}</p>` : ''}
          </div>`;
      }).join('');

      // Athlete identity strip above the cards
      const priLabel = dominant.primary   ? (sportMeta[dominant.primary]?.label   || dominant.primary)   : null;
      const secLabel = dominant.secondary ? (sportMeta[dominant.secondary]?.label || dominant.secondary) : null;
      const identityStrip = priLabel ? `
        <div class="text-sm text-base-content/50 mb-3">
          <span class="font-semibold text-base-content/70">Primary:</span> ${priLabel}
          ${secLabel ? `&nbsp;·&nbsp; <span class="font-semibold text-base-content/70">Secondary:</span> ${secLabel}` : ''}
        </div>` : '';

      container.innerHTML = identityStrip + `<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">${cards}</div>`;
    } catch (err) {
      container.innerHTML = '<p class="text-base-content/60 text-sm py-2">Sport profiles unavailable.</p>';
    }
  }

  destroy() {
    if (this.activityVolumeChart) this.activityVolumeChart.destroy();
    if (this.weightTrendChart) this.weightTrendChart.destroy();
  }
}

// ─── ActivitiesPage ───────────────────────────────────────────────────────────

class ActivitiesPage {
  async init(params, query) {

    this._list = new ActivityList(null, {
      pageSize: 25,
      onRowClick: (id) => router.navigate(`/activities/${id}`),
      filtersContainerId: 'activities-filters',
      tableContainerId:   'activities-table',
      pagerContainerId:   'activities-pager',
    });
    await this._list.init();

    document.getElementById('sync-strava-btn')
      ?.addEventListener('click', e => this._handleSync(e.currentTarget));
  }

  destroy() {}

  async _handleSync(btn) {
    const orig = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="loading loading-spinner loading-sm"></span> Syncing...`;
    try {
      const token = window.getAuthToken?.();
      const res = await fetch(`${api.baseUrl}/auth/strava/sync`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Sync failed');
      const result = await res.json();
      window.showToast(`⏳ ${result.message}`, 'info');
    } catch (err) {
      window.showToast(`❌ ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = orig;
    }
  }
}
// ─── ActivityDetailPage ───────────────────────────────────────────────────────

class ActivityDetailPage {
  async init(params, query) {

    if (!params.id) { this._showError('Invalid activity ID'); return; }
    const detail = new ActivityDetail('activity-detail-container', params.id);
    await detail.init();
  }

  destroy() {}

  _showError(msg) {
    document.getElementById('loading-container')?.classList.add('hidden');
    const el = document.getElementById('error-message');
    if (el) el.textContent = msg;
    document.getElementById('error-container')?.classList.remove('hidden');
  }
}

// ─── LogsPage ─────────────────────────────────────────────────────────────────

class LogsPage {
  async init(params, query) {

    this._form = new DailyLogForm('daily-log-form-container');
    this._form.render();
    this._form.onSuccess(() => {
      this._loadWeeklyStats();
      this._list?.load();
      document.getElementById('log-form-modal')?.close();
    });

    this._list = new DailyLogList('daily-log-list-container');
    await this._list.load();
    await this._loadWeeklyStats();

    document.getElementById('add-log-btn')
      ?.addEventListener('click', () => document.getElementById('log-form-modal')?.showModal());
  }

  destroy() {}

  async _loadWeeklyStats() {
    try {
      const response = await api.listDailyLogs();
      const logs = response.logs || response;
      if (!logs?.length) return;

      const weekStart = getWeekStart();
      const weekLogs  = logs.filter(l => new Date(l.log_date) >= weekStart);
      if (!weekLogs.length) return;

      let totalCal = 0, totalAdh = 0, totalProt = 0;
      weekLogs.forEach(l => {
        if (l.calories_in)             totalCal  += l.calories_in;
        if (l.adherence_score != null) totalAdh  += l.adherence_score;
        if (l.protein_g)               totalProt += l.protein_g;
      });

      const n   = weekLogs.length;
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
      set('avg-calories',  totalCal  > 0 ? Math.round(totalCal / n)         : '--');
      set('avg-adherence', totalAdh  > 0 ? (totalAdh / n).toFixed(1)        : '--');
      set('avg-sleep',     totalProt > 0 ? (totalProt / n).toFixed(1) + 'g' : '--');
      set('avg-energy',    n);
    } catch (err) {
      console.error('Error loading weekly stats:', err);
    }
  }
}

// ─── MetricsPage ──────────────────────────────────────────────────────────────

class MetricsPage {
  async init(params, query) {

    this._extendedMode = localStorage.getItem('metricsExtendedMode') === 'true';
    const toggle = document.getElementById('extended-mode-toggle');
    if (toggle) toggle.checked = this._extendedMode;

    this._form  = new MetricsForm('metrics-form-container', null, this._extendedMode);
    this._form.render();
    this._chart = new MetricsChart('metrics-charts-container', api);
    await this._chart.render();
    this._list  = new MetricsList('metrics-list-container', this._extendedMode);
    await this._list.load();

    toggle?.addEventListener('change', e => {
      this._extendedMode = e.target.checked;
      localStorage.setItem('metricsExtendedMode', this._extendedMode);
      this._form.setExtendedMode(this._extendedMode);
      this._form.render();
      this._list.setExtendedMode(this._extendedMode);
      this._list.render();
    });

    this._form.onSuccess(async () => {
      await this._chart.update();
      await this._list.load();
      document.getElementById('metric-form-modal')?.close();
    });

    document.getElementById('add-metric-btn')
      ?.addEventListener('click', () => document.getElementById('metric-form-modal')?.showModal());
  }

  destroy() {}
}

// ─── ChatPage ─────────────────────────────────────────────────────────────────

class ChatPage {
  async init(params, query) {

    this._chat = new CoachChat();
    window._coachChat = this._chat;
    await this._chat.init();
  }

  destroy() { window._coachChat = null; }
}

// ─── TrainingPlansPage ────────────────────────────────────────────────────────

class TrainingPlansPage {
  async init(params, query) {
    this._list = new TrainingPlansList('plans-container', {
      onPlanClick: (id) => router.navigate(`/training-plans/${id}`),
    });
    await this._list.init();
    this._routeProfileId = null;
    this._initModal();
  }

  destroy() {}

  // ── Modal setup ────────────────────────────────────────────────────────────

  _initModal() {
    const modal = document.getElementById('new-plan-modal');
    if (!modal) return;

    document.getElementById('btn-new-plan')?.addEventListener('click', () => {
      this._resetModal();
      modal.showModal();
    });

    document.getElementById('btn-type-general')?.addEventListener('click', () => {
      modal.close();
      router.navigate('/chat');
    });
    document.getElementById('btn-type-route')?.addEventListener('click', () => this._showStep('route'));
    document.getElementById('btn-back-to-type')?.addEventListener('click', () => this._showStep('type'));

    // GPX drop zone
    const dropZone = document.getElementById('gpx-drop-zone');
    const fileInput = document.getElementById('gpx-file-input');
    dropZone?.addEventListener('click', () => fileInput?.click());
    dropZone?.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('border-primary'); });
    dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('border-primary'));
    dropZone?.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('border-primary');
      const file = e.dataTransfer?.files[0];
      if (file) this._handleGpxFile(file);
    });
    fileInput?.addEventListener('change', () => {
      if (fileInput.files[0]) this._handleGpxFile(fileInput.files[0]);
    });

    // Duration slider
    const slider = document.getElementById('duration-input');
    slider?.addEventListener('input', () => {
      document.getElementById('duration-label').textContent = `${slider.value} weeks`;
      // Once the user manually adjusts, hide the suggestion so it doesn't conflict
      document.getElementById('duration-suggestion')?.classList.add('hidden');
    });

    // Goal radios — show/hide target time input + populate estimate hint
    document.querySelectorAll('input[name="plan-goal"]').forEach(r => {
      r.addEventListener('change', () => {
        const isTargetTime = r.value === 'target_time' && r.checked;
        document.getElementById('target-time-row')?.classList.toggle('hidden', !isTargetTime);
        if (isTargetTime) this._showEstimateHint();
      });
    });

    document.getElementById('btn-generate-plan')?.addEventListener('click', () => this._generatePlan());
  }

  _resetModal() {
    this._routeProfileId  = null;
    this._estimatedFinish = null;
    this._showStep('type');

    // GPX zone
    document.getElementById('gpx-upload-prompt')?.classList.remove('hidden');
    document.getElementById('gpx-analyzing')?.classList.add('hidden');
    document.getElementById('gpx-selected')?.classList.add('hidden');
    const fi = document.getElementById('gpx-file-input');
    if (fi) fi.value = '';

    // Route info block
    document.getElementById('route-summary-card')?.classList.add('hidden');
    document.getElementById('rs-readiness-loading')?.classList.add('hidden');
    document.getElementById('rs-readiness-card')?.classList.add('hidden');
    document.getElementById('rs-demands-card')?.classList.add('hidden');
    document.getElementById('rs-athlete-difficulty-row')?.classList.add('hidden');

    // Event details
    document.getElementById('event-details-form')?.classList.add('hidden');
    document.getElementById('btn-generate-plan')?.classList.add('hidden');
    document.getElementById('target-time-row')?.classList.add('hidden');
    document.getElementById('rs-gap-card')?.classList.add('hidden');

    // Duration reset
    const slider = document.getElementById('duration-input');
    if (slider) { slider.value = 8; document.getElementById('duration-label').textContent = '8 weeks'; }
    document.getElementById('duration-suggestion')?.classList.add('hidden');

    // Target time reset
    const th = document.getElementById('target-hours');
    const tm = document.getElementById('target-minutes');
    if (th) th.value = '';
    if (tm) tm.value = '';

    // Reset goal to first option
    const firstGoal = document.querySelector('input[name="plan-goal"][value="finish"]');
    if (firstGoal) firstGoal.checked = true;
  }

  _showStep(step) {
    document.getElementById('plan-step-type')?.classList.toggle('hidden', step !== 'type');
    document.getElementById('plan-step-route')?.classList.toggle('hidden', step !== 'route');
  }

  // ── GPX upload & analysis ──────────────────────────────────────────────────

  async _handleGpxFile(file) {
    if (!file.name.toLowerCase().endsWith('.gpx')) {
      window.showToast('Please upload a .gpx file', 'error'); return;
    }

    document.getElementById('gpx-upload-prompt')?.classList.add('hidden');
    document.getElementById('gpx-selected')?.classList.add('hidden');
    document.getElementById('gpx-analyzing')?.classList.remove('hidden');
    document.getElementById('route-summary-card')?.classList.add('hidden');
    document.getElementById('event-details-form')?.classList.add('hidden');
    document.getElementById('btn-generate-plan')?.classList.add('hidden');

    const sport = document.querySelector('input[name="plan-sport"]:checked')?.value || 'run';

    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('sport', sport);
      const data = await api.upload('/routes/analyze', fd);
      const profile = data.route_profile;
      this._routeProfileId = profile.id;

      this._renderRouteSummary(profile);

      document.getElementById('gpx-analyzing')?.classList.add('hidden');
      document.getElementById('gpx-selected')?.classList.remove('hidden');
      document.getElementById('gpx-filename').textContent = file.name;
      document.getElementById('route-summary-card')?.classList.remove('hidden');
      document.getElementById('event-details-form')?.classList.remove('hidden');
      document.getElementById('btn-generate-plan')?.classList.remove('hidden');

      if (data.cached) window.showToast('Route already analysed — using cached profile', 'info', 3000);

      // Load readiness asynchronously — doesn't block UI
      document.getElementById('rs-readiness-loading')?.classList.remove('hidden');
      this._loadReadiness(profile.id);

    } catch (err) {
      document.getElementById('gpx-analyzing')?.classList.add('hidden');
      document.getElementById('gpx-upload-prompt')?.classList.remove('hidden');
      window.showToast(`Route analysis failed: ${err.message}`, 'error');
    }
  }

  _renderRouteSummary(p) {
    const diffColors = { easy: 'badge-success', moderate: 'badge-warning', hard: 'badge-error', extreme: 'badge-error' };
    const name = (p.filename || 'Route').replace(/\.gpx$/i, '').replace(/[_-]/g, ' ').toUpperCase();

    document.getElementById('rs-name').textContent = name;
    const diffBadge = document.getElementById('rs-difficulty');
    diffBadge.textContent = p.route_difficulty || 'unknown';
    diffBadge.className = `badge badge-sm ${diffColors[p.route_difficulty] || 'badge-ghost'}`;

    document.getElementById('rs-metrics').innerHTML = [
      { label: 'Distance',  value: p.distance_km            ? `${p.distance_km.toFixed(1)} km`           : '—' },
      { label: 'Elevation', value: p.total_elevation_gain_m ? `${Math.round(p.total_elevation_gain_m)} m` : '—' },
      { label: 'Max grade', value: p.max_gradient_pct       ? `${p.max_gradient_pct.toFixed(0)}%`         : '—' },
    ].map(m => `
      <div class="bg-base-100 rounded-lg p-2">
        <div class="font-bold text-sm">${m.value}</div>
        <div class="text-xs text-base-content/50">${m.label}</div>
      </div>`).join('');

    const critical = p.critical_sections || [];
    const critEl = document.getElementById('rs-critical');
    if (critical.length) {
      critEl.classList.remove('hidden');
      document.getElementById('rs-critical-list').innerHTML = critical.map(c =>
        `<div class="text-xs text-base-content/70 flex items-start gap-1.5">
          <span class="text-warning mt-0.5">▲</span>
          <span>${c.description} <span class="opacity-50">at km ${c.start_km}–${c.end_km}</span></span>
        </div>`
      ).join('');
    } else {
      critEl.classList.add('hidden');
    }
  }

  // ── Readiness ──────────────────────────────────────────────────────────────

  async _loadReadiness(routeId) {
    try {
      const data = await api.get(`/routes/${routeId}/readiness`);
      document.getElementById('rs-readiness-loading')?.classList.add('hidden');
      this._renderReadiness(data);
    } catch (err) {
      document.getElementById('rs-readiness-loading')?.classList.add('hidden');
      // Readiness is non-critical — fail silently
    }
  }

  _renderReadiness(data) {
    const levelIcon  = { good: '✅', moderate: '⚠️', limited: '❌' };
    const levelColor = { good: 'text-success', moderate: 'text-warning', limited: 'text-error' };
    const diffColors = { easy: 'badge-success', moderate: 'badge-warning', hard: 'badge-error', extreme: 'badge-error' };
    const overallColor = { easy: 'text-success', moderate: 'text-warning', hard: 'text-error', extreme: 'text-error' };

    // Save estimated finish so the target-time-estimate span can reference it
    this._estimatedFinish = data.estimated_finish || null;

    // Athlete difficulty badge in route header
    const athDiffRow = document.getElementById('rs-athlete-difficulty-row');
    const athDiff    = document.getElementById('rs-athlete-difficulty');
    if (athDiffRow && athDiff && data.athlete_difficulty) {
      athDiff.textContent = data.athlete_difficulty;
      athDiff.className = `badge badge-sm badge-outline ${diffColors[data.athlete_difficulty] || 'badge-ghost'}`;
      athDiffRow.classList.remove('hidden');
    }

    // Readiness rows (endurance / climbing / speed)
    const readiness = data.readiness || {};
    document.getElementById('rs-readiness-rows').innerHTML = Object.entries(readiness).map(([dim, r]) => `
      <div class="flex items-start gap-2">
        <span class="text-sm mt-0.5 shrink-0">${levelIcon[r.level] || '—'}</span>
        <div class="min-w-0">
          <span class="text-xs font-semibold capitalize ${levelColor[r.level] || ''}">${dim}:</span>
          <span class="text-xs text-base-content/70 ml-1">${r.detail}</span>
        </div>
      </div>`).join('');

    // Overall label
    const overallEl = document.getElementById('rs-overall-label');
    if (overallEl) {
      overallEl.textContent = data.overall_label || '';
      overallEl.className = `text-xs font-semibold ${overallColor[data.athlete_difficulty] || ''}`;
    }
    document.getElementById('rs-readiness-card')?.classList.remove('hidden');

    // Route demands
    const demands = data.route_demands || [];
    if (demands.length) {
      document.getElementById('rs-demands-list').innerHTML = demands.map(d =>
        `<div class="text-xs text-base-content/70 flex items-start gap-1.5">
          <span class="text-primary mt-0.5 shrink-0">›</span>
          <span>${d}</span>
        </div>`).join('');
      document.getElementById('rs-demands-card')?.classList.remove('hidden');
    }

    // Suggested duration — pre-fill slider + show hint
    if (data.suggested_duration_weeks) {
      const w = data.suggested_duration_weeks;
      const slider = document.getElementById('duration-input');
      const label  = document.getElementById('duration-label');
      const hint   = document.getElementById('duration-suggestion');
      if (slider) { slider.value = w; }
      if (label)  { label.textContent = `${w} weeks`; }
      if (hint)   {
        hint.textContent = `Suggested: ${w} weeks based on current fitness vs route difficulty`;
        hint.classList.remove('hidden');
      }
    }

    // Gap summary
    const gaps  = data.gap_summary?.gaps     || [];
    const focus = data.gap_summary?.plan_focus || [];
    if (gaps.length || focus.length) {
      document.getElementById('rs-gap-list').innerHTML = gaps.map(g =>
        `<div class="text-xs text-base-content/70 flex items-start gap-1.5">
          <span class="text-warning shrink-0">⚠</span><span>${g}</span>
        </div>`).join('');
      document.getElementById('rs-focus-list').innerHTML = focus.map(f =>
        `<div class="text-xs text-base-content/70 flex items-start gap-1.5">
          <span class="text-success shrink-0">✓</span><span>${f}</span>
        </div>`).join('');
      document.getElementById('rs-gap-card')?.classList.remove('hidden');
    }

    // If user already selected "target_time" before readiness arrived, update hint now
    const selectedGoal = document.querySelector('input[name="plan-goal"]:checked')?.value;
    if (selectedGoal === 'target_time') this._showEstimateHint();
  }

  _showEstimateHint() {
    const el = document.getElementById('target-time-estimate');
    if (!el) return;
    if (this._estimatedFinish) {
      el.textContent = `Current estimate: ${this._estimatedFinish.display}`;
    } else {
      el.textContent = '';
    }
  }

  // ── Plan generation ────────────────────────────────────────────────────────

  async _generatePlan() {
    if (!this._routeProfileId) { window.showToast('Please upload a GPX file first', 'warning'); return; }

    const eventDate = document.getElementById('event-date-input')?.value;
    if (!eventDate) { window.showToast('Please select an event date', 'warning'); return; }
    if (new Date(eventDate) <= new Date()) { window.showToast('Event date must be in the future', 'warning'); return; }

    const goalType     = document.querySelector('input[name="plan-goal"]:checked')?.value || 'finish';
    const durationWeeks = parseInt(document.getElementById('duration-input')?.value || '8', 10);

    // Target time (only relevant when goalType === 'target_time')
    let targetTimeMin = null;
    if (goalType === 'target_time') {
      const h = parseInt(document.getElementById('target-hours')?.value || '0', 10);
      const m = parseInt(document.getElementById('target-minutes')?.value || '0', 10);
      if (!h && !m) { window.showToast('Please enter a target time', 'warning'); return; }
      targetTimeMin = h * 60 + m;
    }

    const btn = document.getElementById('btn-generate-plan');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading loading-spinner loading-xs"></span> Generating...';

    try {
      const payload = { event_date: eventDate, goal_type: goalType, duration_weeks: durationWeeks };
      if (targetTimeMin !== null) payload.target_time_min = targetTimeMin;

      const data = await api.post(`/routes/${this._routeProfileId}/plan`, payload);
      document.getElementById('new-plan-modal').close();
      window.showToast(`Plan created: ${data.title}`, 'success', 4000);
      await this._list.refresh();
      if (data.plan_id) router.navigate(`/training-plans/${data.plan_id}`);
    } catch (err) {
      window.showToast(`Plan generation failed: ${err.message}`, 'error');
      btn.disabled = false;
      btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/></svg> Generate Plan';
    }
  }
}

// ─── TrainingPlanDetailPage ───────────────────────────────────────────────────

class TrainingPlanDetailPage {
  async init(params) {
    this._planId = params.id;
    await this._load();
  }
  destroy() {}

  async _load() {
    try {
      const data = await api.get(`/training-plans/${this._planId}`);
      this._render(data.plan);
    } catch (err) {
      document.getElementById('pd-loading').innerHTML =
        `<p class="text-error text-sm">Failed to load plan: ${err.message}</p>`;
    }
  }

  async _confirmDelete(plan) {
    if (!confirm(`Delete "${plan.title}"? This cannot be undone.`)) return;
    const btn = document.getElementById('pd-delete-btn');
    btn.disabled = true;
    try {
      await api.delete(`/training-plans/${this._planId}`);
      window.location.href = '/training-plans';
    } catch (err) {
      btn.disabled = false;
      window.showToast(`Failed to delete plan: ${err.message}`, 'error');
    }
  }

  _render(plan) {
    document.getElementById('pd-loading')?.classList.add('hidden');
    document.getElementById('pd-content')?.classList.remove('hidden');

    document.getElementById('pd-delete-btn')?.addEventListener('click', () => this._confirmDelete(plan));

    // Title + status + meta
    document.getElementById('pd-title').textContent = plan.title;
    const statusColors = { active: 'badge-success', draft: 'badge-ghost', completed: 'badge-info', abandoned: 'badge-warning' };
    const statusEl = document.getElementById('pd-status');
    statusEl.textContent = plan.status;
    statusEl.className = `badge badge-sm ${statusColors[plan.status] || 'badge-ghost'}`;

    const start = plan.start_date ? new Date(plan.start_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
    const end   = plan.end_date   ? new Date(plan.end_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
    document.getElementById('pd-meta').textContent = `${plan.sport} · ${start} – ${end}`;

    // ── Route context block ───────────────────────────────────────────────────
    const rc = plan.route_context;
    if (rc) {
      const diffColors = { easy: 'badge-success', moderate: 'badge-warning', hard: 'badge-error', extreme: 'badge-error' };
      document.getElementById('pd-route-name').textContent = rc.name?.toUpperCase() || 'Route';
      const diffBadge = document.getElementById('pd-route-difficulty');
      diffBadge.textContent = rc.route_difficulty || '';
      diffBadge.className = `badge badge-sm ${diffColors[rc.route_difficulty] || 'badge-ghost'}`;

      document.getElementById('pd-route-metrics').innerHTML = [
        { label: 'Distance',  value: rc.distance_km            ? `${rc.distance_km.toFixed(1)} km`           : '—' },
        { label: 'Elevation', value: rc.total_elevation_gain_m ? `${Math.round(rc.total_elevation_gain_m)} m` : '—' },
        { label: 'Max grade', value: rc.max_gradient_pct       ? `${rc.max_gradient_pct.toFixed(0)}%`         : '—' },
      ].map(m => `
        <div class="bg-base-200 rounded-lg p-2">
          <div class="font-bold text-sm">${m.value}</div>
          <div class="text-xs text-base-content/50">${m.label}</div>
        </div>`).join('');

      // Critical sections → key demands
      const critical = rc.critical_sections || [];
      if (critical.length) {
        document.getElementById('pd-route-demands-list').innerHTML = critical.slice(0, 4).map(c =>
          `<div class="text-xs text-base-content/70 flex items-start gap-1.5">
            <span class="text-warning shrink-0 mt-0.5">▲</span>
            <span>${c.description}</span>
          </div>`).join('');
        document.getElementById('pd-route-demands')?.classList.remove('hidden');
      }
      document.getElementById('pd-route-context')?.classList.remove('hidden');
    }

    // ── Why this plan works ───────────────────────────────────────────────────
    const meta = plan.plan_metadata || {};
    const rationale = meta.plan_rationale;
    if (rationale) {
      const whyText = rationale.why_it_works || '';
      const strategy = rationale.strategy || [];
      if (whyText) document.getElementById('pd-rationale-text').textContent = whyText;
      if (strategy.length) {
        document.getElementById('pd-strategy-list').innerHTML = strategy.map(s =>
          `<div class="flex items-start gap-1.5 text-xs text-base-content/70">
            <span class="text-success shrink-0 mt-0.5">✓</span><span>${s}</span>
          </div>`).join('');
      }
      if (whyText || strategy.length) document.getElementById('pd-rationale')?.classList.remove('hidden');
    }

    // ── Performance target ────────────────────────────────────────────────────
    const perfTarget = meta.performance_target;
    if (perfTarget) {
      const label = perfTarget.label || '';
      const metrics = perfTarget.metrics || [];
      if (label) document.getElementById('pd-perf-target-label').textContent = label;
      if (metrics.length) {
        document.getElementById('pd-perf-metrics').innerHTML = metrics.map(m =>
          `<span class="badge badge-outline badge-primary badge-sm">${m}</span>`).join('');
      }
      if (label || metrics.length) document.getElementById('pd-perf-target')?.classList.remove('hidden');
    }

    // ── Adherence ─────────────────────────────────────────────────────────────
    const adh   = plan.overall_adherence ?? 0;
    const total  = plan.weeks?.reduce((n, w) => n + (w.sessions?.length ?? 0), 0) ?? 0;
    const done   = plan.weeks?.reduce((n, w) => n + (w.sessions?.filter(s => s.completed).length ?? 0), 0) ?? 0;
    document.getElementById('pd-adh-pct').textContent = `${adh.toFixed(0)}%`;
    document.getElementById('pd-adh-bar').value = adh;
    document.getElementById('pd-adh-detail').textContent = `${done} of ${total} sessions completed`;

    // ── Week tabs ─────────────────────────────────────────────────────────────
    const phaseColors     = { base: 'badge-ghost', specific: 'badge-primary', taper: 'badge-secondary' };
    const intensityColors = { recovery: 'text-base-content/40', easy: 'text-success', moderate: 'text-warning', hard: 'text-error', max: 'text-error font-bold' };
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const weeks = plan.weeks || [];

    // Determine which week to show by default (current week for active plans)
    let defaultIdx = 0;
    if (plan.status === 'active' && plan.start_date) {
      const msPerWeek = 7 * 24 * 60 * 60 * 1000;
      const elapsed = Math.floor((Date.now() - new Date(plan.start_date)) / msPerWeek);
      defaultIdx = Math.max(0, Math.min(elapsed, weeks.length - 1));
    }

    const tabsEl   = document.getElementById('pd-week-tabs');
    const panelsEl = document.getElementById('pd-week-panels');

    tabsEl.innerHTML = weeks.map((week, i) => {
      const allDone = (week.sessions || []).filter(s => s.session_type !== 'rest').every(s => s.completed);
      const anyDone = (week.sessions || []).some(s => s.completed);
      const dot = allDone
        ? '<span class="w-1.5 h-1.5 rounded-full bg-success inline-block ml-1"></span>'
        : anyDone
          ? '<span class="w-1.5 h-1.5 rounded-full bg-warning inline-block ml-1"></span>'
          : '';
      const isActive = i === defaultIdx;
      return `<button
        class="pd-week-tab px-4 py-2.5 text-sm font-medium border-b-2 transition-colors shrink-0
               ${isActive ? 'border-primary text-primary' : 'border-transparent text-base-content/50 hover:text-base-content hover:border-base-300'}"
        data-idx="${i}">Week ${week.week_number}${dot}</button>`;
    }).join('');

    panelsEl.innerHTML = weeks.map((week, i) => {
      const sessions = (week.sessions || []).filter(s => s.session_type !== 'rest');
      const phaseBadge = week.phase
        ? `<span class="badge badge-xs ${phaseColors[week.phase] || 'badge-ghost'} uppercase">${week.phase}</span>`
        : '';
      const distTarget = week.distance_target_km
        ? `<span class="text-xs text-base-content/50">${week.distance_target_km.toFixed(0)} km target</span>`
        : '';
      const volTarget = week.volume_target
        ? `<span class="text-xs text-base-content/40">${week.volume_target}h</span>`
        : '';

      return `<div class="pd-week-panel ${i !== defaultIdx ? 'hidden' : ''}" data-idx="${i}">
        <div class="flex items-start justify-between gap-2 mb-4">
          <div class="flex items-center gap-2 flex-wrap">
            ${phaseBadge}
            ${week.focus ? `<span class="text-sm text-base-content/70 leading-snug">${week.focus}</span>` : ''}
          </div>
          <div class="flex items-center gap-2 shrink-0">${distTarget}${volTarget}</div>
        </div>
        ${sessions.length === 0
          ? '<p class="text-sm text-base-content/40 text-center py-6">Rest week</p>'
          : `<div class="space-y-0">
              ${sessions.map(s => {
                const parts = (s.description || '').split(/\s*→\s*/);
                const main  = parts[0] || '';
                const why   = parts.slice(1).join(' → ');
                return `
                  <div class="py-2.5 border-b border-base-200 last:border-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <span class="text-xs text-base-content/40 w-8 shrink-0">${days[(s.day_of_week - 1) % 7]}</span>
                      <span class="text-sm font-semibold">${s.session_type.replace(/_/g, ' ')}</span>
                      <span class="text-xs ${intensityColors[s.intensity] || ''}">${s.intensity}</span>
                      ${s.duration_minutes ? `<span class="text-xs text-base-content/40">${s.duration_minutes} min</span>` : ''}
                      ${s.completed ? '<span class="badge badge-success badge-xs">done</span>' : ''}
                    </div>
                    ${main ? `<p class="text-xs text-base-content/70 mt-0.5 ml-10 leading-snug">${main}</p>` : ''}
                    ${why  ? `<p class="text-xs text-primary/70 mt-0.5 ml-10 leading-snug italic">→ ${why}</p>` : ''}
                  </div>`;
              }).join('')}
            </div>`
        }
      </div>`;
    }).join('');

    // Tab click handler
    tabsEl.addEventListener('click', e => {
      const btn = e.target.closest('.pd-week-tab');
      if (!btn) return;
      const idx = parseInt(btn.dataset.idx, 10);
      tabsEl.querySelectorAll('.pd-week-tab').forEach((t, i) => {
        t.className = t.className
          .replace('border-primary text-primary', 'border-transparent text-base-content/50 hover:text-base-content hover:border-base-300');
        if (i === idx) t.className = t.className
          .replace('border-transparent text-base-content/50 hover:text-base-content hover:border-base-300', 'border-primary text-primary');
      });
      panelsEl.querySelectorAll('.pd-week-panel').forEach(p => p.classList.toggle('hidden', parseInt(p.dataset.idx, 10) !== idx));
    });

    // Scroll the default tab into view
    tabsEl.querySelector(`[data-idx="${defaultIdx}"]`)?.scrollIntoView({ inline: 'nearest', block: 'nearest' });
  }
}

// ─── GoalsPage ────────────────────────────────────────────────────────────────

class GoalsPage {
  async init(params, query) {
    window.goalsPage = new GoalsManager();
    await window.goalsPage.init();
  }
  destroy() { delete window.goalsPage; }
}

// ─── SettingsPage ─────────────────────────────────────────────────────────────

class SettingsPage {
  async init(params, query) {
    await new SettingsManager().init();
  }
  destroy() {}
}

// ─── AppSettingsPage ──────────────────────────────────────────────────────────

class AppSettingsPage {
  async init(params, query) {
    await new AppSettingsManager().init();
  }
  destroy() {}
}

// ─── EvaluationDetailPage ─────────────────────────────────────────────────────

class EvaluationDetailPage {
  async init(params, query) {
    if (!params.id) {
      window.showToast('Invalid evaluation ID', 'error');
      router.navigate('/evaluations');
      return;
    }
    
    this.evaluationId = params.id;
    await this.loadEvaluation();
    this.attachEventListeners();
  }
  
  async loadEvaluation() {
    try {
      const evaluation = await api.get(`/evaluations/${this.evaluationId}`);
      this.renderEvaluation(evaluation);
    } catch (error) {
      console.error('Error loading evaluation:', error);
      window.showToast(`Failed to load evaluation: ${error.message}`, 'error');
      router.navigate('/evaluations');
    }
  }
  
  renderEvaluation(evaluation) {
    // Header
    document.getElementById('eval-title').textContent = `${evaluation.period_type || 'Weekly'} Evaluation`;
    
    const startDate = new Date(evaluation.period_start).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    const endDate = new Date(evaluation.period_end).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    document.getElementById('eval-period').textContent = `${startDate} - ${endDate}`;
    
    const generatedDate = new Date(evaluation.generated_at).toLocaleDateString('en-US', { 
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' 
    });
    document.getElementById('eval-generated').textContent = `Generated: ${generatedDate}`;
    
    // Score
    const scoreColor = evaluation.overall_score >= 80 ? 'text-success' : 
                      evaluation.overall_score >= 60 ? 'text-warning' : 
                      evaluation.overall_score >= 40 ? 'text-info' : 'text-error';
    const scoreEl = document.getElementById('overall-score');
    scoreEl.textContent = evaluation.overall_score;
    scoreEl.className = `text-6xl font-bold ${scoreColor}`;
    
    // Confidence
    const confidencePercent = Math.round(evaluation.confidence_score * 100);
    const confidenceEl = document.getElementById('confidence-badge');
    confidenceEl.textContent = `${confidencePercent}% confidence`;
    confidenceEl.className = confidencePercent >= 80 ? 'badge badge-success' : 
                            confidencePercent >= 60 ? 'badge badge-warning' : 'badge badge-error';
    
    // Strengths
    const strengthsList = document.getElementById('strengths-list');
    strengthsList.innerHTML = evaluation.strengths && evaluation.strengths.length > 0
      ? evaluation.strengths.map(s => `<li class="flex items-start gap-2"><span class="text-success text-xl">✓</span><span>${s}</span></li>`).join('')
      : '<li class="text-base-content/60">No strengths recorded</li>';
    
    // Improvements
    const improvementsList = document.getElementById('improvements-list');
    improvementsList.innerHTML = evaluation.improvements && evaluation.improvements.length > 0
      ? evaluation.improvements.map(i => `<li class="flex items-start gap-2"><span class="text-warning text-xl">⚠</span><span>${i}</span></li>`).join('')
      : '<li class="text-base-content/60">No improvements recorded</li>';
    
    // Goal Alignment
    document.getElementById('goal-alignment').textContent = evaluation.goal_alignment || 'No goal alignment information available';
    
    // Tips
    const tipsList = document.getElementById('tips-list');
    tipsList.innerHTML = evaluation.tips && evaluation.tips.length > 0
      ? evaluation.tips.map(t => `<li class="flex items-start gap-2"><span class="text-info">💡</span><span>${t}</span></li>`).join('')
      : '<li class="text-base-content/60">No tips available</li>';
    
    // Exercises
    const exercisesList = document.getElementById('exercises-list');
    exercisesList.innerHTML = evaluation.recommended_exercises && evaluation.recommended_exercises.length > 0
      ? evaluation.recommended_exercises.map(e => `<li class="flex items-start gap-2"><span class="text-primary">🏋️</span><span>${e}</span></li>`).join('')
      : '<li class="text-base-content/60">No exercises recommended</li>';
  }
  
  attachEventListeners() {
    // Fix back button
    const backBtn = document.querySelector('a[href="evaluations-list.html"]');
    if (backBtn) {
      backBtn.href = '/evaluations';
      backBtn.onclick = (e) => {
        e.preventDefault();
        router.navigate('/evaluations');
      };
    }
    
    // Re-evaluate button
    document.getElementById('re-evaluate-btn')?.addEventListener('click', () => {
      this.reEvaluate();
    });
  }
  
  async reEvaluate() {
    const btn = document.getElementById('re-evaluate-btn');
    if (!btn) return;
    
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="loading loading-spinner loading-xs"></span> Re-evaluating...';
    
    try {
      window.showToast('Generating new evaluation...', 'info');
      
      const response = await api.post(`/evaluations/${this.evaluationId}/re-evaluate`);
      
      window.showToast('✅ New evaluation generated!', 'success');
      
      // Navigate to the new evaluation
      router.navigate(`/evaluations/${response.id}`);
    } catch (error) {
      console.error('Error re-evaluating:', error);
      window.showToast(`❌ Failed to re-evaluate: ${error.message}`, 'error');
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  }
  
  destroy() {}
}

// ─── EvaluationsPage ──────────────────────────────────────────────────────────

class EvaluationsPage {
  async init(params, query) {
    this.filters = {
      date_from: null,
      date_to: null,
      score_min: null,
      score_max: null
    };
    
    await this.loadEvaluations();
    this.attachEventListeners();
  }
  
  async loadEvaluations() {
    try {
      // Build query params
      const params = new URLSearchParams();
      if (this.filters.date_from) params.append('date_from', this.filters.date_from);
      if (this.filters.date_to) params.append('date_to', this.filters.date_to);
      if (this.filters.score_min) params.append('score_min', this.filters.score_min);
      if (this.filters.score_max) params.append('score_max', this.filters.score_max);
      
      const endpoint = params.toString() ? `/evaluations?${params.toString()}` : '/evaluations';
      const evaluations = await api.get(endpoint);
      
      const container = document.getElementById('evaluations-container');
      const emptyState = document.getElementById('empty-state');
      
      if (!evaluations || evaluations.length === 0) {
        container.classList.add('hidden');
        emptyState.classList.remove('hidden');
        return;
      }
      
      container.classList.remove('hidden');
      emptyState.classList.add('hidden');
      
      container.innerHTML = evaluations.map(evaluation => this.renderEvaluationCard(evaluation)).join('');
    } catch (error) {
      console.error('Error loading evaluations:', error);
      document.getElementById('evaluations-container').innerHTML = 
        `<p class="text-error">Failed to load evaluations: ${error.message}</p>`;
    }
  }
  
  renderEvaluationCard(evaluation) {
    const scoreColor = evaluation.overall_score >= 80 ? 'text-success' : 
                      evaluation.overall_score >= 60 ? 'text-warning' : 
                      evaluation.overall_score >= 40 ? 'text-info' : 'text-error';
    
    const date = new Date(evaluation.period_end);
    const dateStr = date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    
    // Create summary from strengths and improvements
    const summary = evaluation.strengths && evaluation.strengths.length > 0 
      ? evaluation.strengths[0] 
      : evaluation.goal_alignment || 'No summary available';
    
    return `
      <div class="card bg-base-100 shadow-xl hover:shadow-2xl transition-shadow cursor-pointer" 
           onclick="window.location.href='/evaluations/${evaluation.id}'">
        <div class="card-body">
          <div class="flex justify-between items-start">
            <div class="flex-1">
              <h3 class="card-title">${evaluation.period_type || 'Weekly'} Evaluation</h3>
              <p class="text-sm text-base-content/60">${dateStr}</p>
            </div>
            <div class="text-right">
              <div class="text-3xl font-bold ${scoreColor}">${evaluation.overall_score}</div>
              <div class="text-sm text-base-content/60">out of 100</div>
            </div>
          </div>
          <p class="mt-2 text-sm">${summary.substring(0, 150)}${summary.length > 150 ? '...' : ''}</p>
        </div>
      </div>
    `;
  }
  
  attachEventListeners() {
    document.getElementById('generate-eval-btn')?.addEventListener('click', () => {
      this.showGenerateModal();
    });
    
    document.getElementById('generate-eval-empty-btn')?.addEventListener('click', () => {
      this.showGenerateModal();
    });
    
    document.getElementById('apply-filters-btn')?.addEventListener('click', () => {
      this.applyFilters();
    });
    
    document.getElementById('clear-filters-btn')?.addEventListener('click', () => {
      this.clearFilters();
    });
    
    // Modal event listeners
    document.getElementById('cancel-generate-btn')?.addEventListener('click', () => {
      document.getElementById('generate-modal')?.close();
    });
    
    document.getElementById('generate-form')?.addEventListener('submit', (e) => {
      e.preventDefault();
      this.handleGenerateSubmit();
    });
  }
  
  showGenerateModal() {
    const modal = document.getElementById('generate-modal');
    if (!modal) return;
    
    // Set default dates
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 7); // Default to weekly
    
    document.getElementById('period-start').value = startDate.toISOString().split('T')[0];
    document.getElementById('period-end').value = endDate.toISOString().split('T')[0];
    document.getElementById('period-type').value = 'weekly';
    
    modal.showModal();
  }
  
  async handleGenerateSubmit() {
    const periodStart = document.getElementById('period-start').value;
    const periodEnd = document.getElementById('period-end').value;
    const periodType = document.getElementById('period-type').value;
    
    if (!periodStart || !periodEnd || !periodType) {
      window.showToast('Please fill in all fields', 'error');
      return;
    }
    
    // Close modal
    document.getElementById('generate-modal')?.close();
    
    // Generate evaluation
    await this.generateEvaluation(periodStart, periodEnd, periodType);
  }
  
  async generateEvaluation(periodStart, periodEnd, periodType) {
    try {
      window.showToast('Generating evaluation...', 'info');
      
      const response = await api.post('/evaluations/generate', {
        period_start: periodStart,
        period_end: periodEnd,
        period_type: periodType
      });
      
      window.showToast('✅ Evaluation generated successfully!', 'success');
      
      // Reload evaluations list
      await this.loadEvaluations();
      
      // Navigate to the new evaluation
      if (response.id) {
        router.navigate(`/evaluations/${response.id}`);
      }
    } catch (error) {
      console.error('Error generating evaluation:', error);
      window.showToast(`❌ Failed to generate evaluation: ${error.message}`, 'error');
    }
  }
  
  async applyFilters() {
    this.filters = {
      date_from: document.getElementById('filter-date-from').value || null,
      date_to: document.getElementById('filter-date-to').value || null,
      score_min: document.getElementById('filter-score-min').value || null,
      score_max: document.getElementById('filter-score-max').value || null
    };
    
    await this.loadEvaluations();
  }
  
  async clearFilters() {
    this.filters = {
      date_from: null,
      date_to: null,
      score_min: null,
      score_max: null
    };
    
    document.getElementById('filter-date-from').value = '';
    document.getElementById('filter-date-to').value = '';
    document.getElementById('filter-score-min').value = '';
    document.getElementById('filter-score-max').value = '';
    
    await this.loadEvaluations();
  }

  destroy() {}
}

export {
  DashboardPage,
  ActivitiesPage,
  ActivityDetailPage,
  LogsPage,
  MetricsPage,
  ChatPage,
  TrainingPlansPage,
  TrainingPlanDetailPage,
  GoalsPage,
  SettingsPage,
  AppSettingsPage,
  EvaluationsPage,
  EvaluationDetailPage,
};
/**
 * telemetry.js — Telemetry dashboard page logic.
 * Polls /api/telemetry/health, /api/telemetry/stats, /api/telemetry/logs
 * and renders results into the telemetry.html skeleton.
 */

import { initAuth, isAuthenticated, getToken } from './auth.js';
import { NavigationSidebar } from './navigation-sidebar.js';
import { router } from './router.js';

// ── Auth & sidebar ─────────────────────────────────────────────────────────

await initAuth();
if (!isAuthenticated()) { window.location.replace('/'); }


// In this standalone page, register a fallback so sidebar nav links do full-page redirects.
router.notFound(path => { window.location.href = path; });

const sidebar = new NavigationSidebar('sidebar-container');
sidebar.setActiveRoute('/telemetry');

// ── Helpers ────────────────────────────────────────────────────────────────

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch(path) {
  const resp = await fetch(path, { headers: authHeaders() });
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json();
}

function fmtMs(ms) {
  if (ms == null || ms === 0) return '—';
  return `${ms.toFixed(0)} ms`;
}

function fmtUptime(sec) {
  if (!sec) return '—';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function fmtTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString();
}

function statusBadgeClass(status) {
  return {
    healthy:     'badge-operational',
    operational: 'badge-operational',
    degraded:    'badge-degraded',
    unhealthy:   'badge-outage',
    outage:      'badge-outage',
  }[status] ?? 'badge-unknown';
}

function statusLabel(status) {
  return {
    operational: '🟢 Operational',
    degraded:    '🟡 Degraded',
    outage:      '🔴 Outage',
    healthy:     '🟢 Healthy',
    unhealthy:   '🔴 Unhealthy',
  }[status] ?? '⚪ Unknown';
}

function statusIcon(overall) {
  return { operational: '🟢', degraded: '🟡', outage: '🔴' }[overall] ?? '⚪';
}

function errorRateColor(rate) {
  if (rate === 0) return 'text-success';
  if (rate < 5)  return 'text-warning';
  return 'text-error';
}

// ── Render: health ─────────────────────────────────────────────────────────

function renderHealth(health) {
  const overall = health.overall ?? 'unknown';

  // Overall badge + icon
  const badge = document.getElementById('overall-badge');
  badge.className = `badge font-semibold px-3 ${statusBadgeClass(overall)}`;
  badge.textContent = overall.charAt(0).toUpperCase() + overall.slice(1);

  document.getElementById('status-icon').textContent  = statusIcon(overall);
  document.getElementById('status-label').textContent = statusLabel(overall);
  document.getElementById('uptime-value').textContent = fmtUptime(health.uptime_seconds);

  // DB
  const db = health.services?.database ?? {};
  const dbBadge = document.getElementById('db-badge');
  dbBadge.className = `badge font-semibold ${statusBadgeClass(db.status)}`;
  dbBadge.textContent = db.status ?? '—';
  document.getElementById('db-latency').textContent = `Latency: ${fmtMs(db.latency_ms)}`;
  const dbErr = document.getElementById('db-error');
  if (db.error) { dbErr.textContent = db.error; dbErr.classList.remove('hidden'); }
  else           { dbErr.classList.add('hidden'); }

  // LLM
  const llm = health.services?.llm ?? {};
  const llmBadge = document.getElementById('llm-badge');
  llmBadge.className = `badge font-semibold ${statusBadgeClass(llm.status)}`;
  llmBadge.textContent = llm.status ?? '—';
  document.getElementById('llm-label').textContent   = `LLM (${llm.type ?? '?'})`;
  document.getElementById('llm-model').textContent   = llm.model ? `Model: ${llm.model}` : llm.endpoint ?? '';
  document.getElementById('llm-latency').textContent = `Latency: ${fmtMs(llm.latency_ms)}`;
  const llmErr = document.getElementById('llm-error');
  if (llm.error) { llmErr.textContent = llm.error; llmErr.classList.remove('hidden'); }
  else            { llmErr.classList.add('hidden'); }
}

// ── Render: stats ──────────────────────────────────────────────────────────

function renderStats(stats) {
  // Top-level KPIs
  document.getElementById('rps-value').textContent = stats.rps ?? '—';

  const errEl = document.getElementById('error-rate-value');
  const rate = stats.error_rate ?? 0;
  errEl.textContent = `${rate.toFixed(1)}%`;
  errEl.className = `text-3xl font-black ${errorRateColor(rate)}`;
  document.getElementById('total-req-label').textContent = `${stats.total_requests ?? 0} requests in window`;

  // Latency bars — scale relative to p99
  const lat = stats.latency ?? {};
  const max = Math.max(lat.p99 ?? 1, 1);
  ['p50', 'p95', 'p99'].forEach(p => {
    const val = lat[p] ?? 0;
    document.getElementById(`${p}-val`).textContent = fmtMs(val);
    document.getElementById(`${p}-bar`).style.width = `${Math.min(100, (val / max) * 100)}%`;
  });
  document.getElementById('avg-val').textContent = fmtMs(lat.avg);

  // Status codes
  const grid = document.getElementById('status-codes-grid');
  const codes = stats.status_codes ?? {};
  if (Object.keys(codes).length === 0) {
    grid.innerHTML = '<div class="text-base-content/40 text-sm col-span-full">No requests recorded yet…</div>';
  } else {
    grid.innerHTML = Object.entries(codes)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([code, count]) => {
        const cls = code.startsWith('5') ? 'badge-error' :
                    code.startsWith('4') ? 'badge-warning' : 'badge-success';
        return `
          <div class="card bg-base-100 border border-base-200 shadow-sm">
            <div class="card-body p-3 items-center text-center">
              <span class="badge ${cls} text-xs font-bold">${code}</span>
              <span class="text-2xl font-black mt-1">${count}</span>
            </div>
          </div>`;
      }).join('');
  }

  // Top endpoints
  const tbody = document.getElementById('endpoints-tbody');
  const eps = stats.top_endpoints ?? [];
  if (eps.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-base-content/40 py-6">No data yet…</td></tr>';
  } else {
    tbody.innerHTML = eps.map(ep => {
      const errCls = ep.error_rate > 10 ? 'text-error font-bold' :
                     ep.error_rate > 0  ? 'text-warning' : 'text-success';
      return `
        <tr>
          <td class="font-mono text-xs">${ep.path}</td>
          <td class="text-right">${ep.count}</td>
          <td class="text-right ${errCls}">${ep.error_rate}%</td>
          <td class="text-right font-mono text-xs">${ep.p95_ms}</td>
          <td class="text-right font-mono text-xs">${ep.avg_ms}</td>
        </tr>`;
    }).join('');
  }

  // Recent errors
  const errTbody = document.getElementById('errors-tbody');
  const errs = stats.recent_errors ?? [];
  if (errs.length === 0) {
    errTbody.innerHTML = '<tr><td colspan="5" class="text-center text-base-content/40 py-6">No errors recorded 🎉</td></tr>';
  } else {
    errTbody.innerHTML = errs.map((e, i) => {
      const cls = e.status >= 500 ? 'badge-error' : 'badge-warning';
      const hasDetail = e.error_detail && e.error_detail.trim().length > 0;
      const detailId = `err-detail-${i}`;
      const mainRow = `
        <tr class="${hasDetail ? 'cursor-pointer hover:bg-base-200' : ''}" ${hasDetail ? `onclick="document.getElementById('${detailId}').classList.toggle('hidden')"` : ''}>
          <td class="text-xs text-base-content/50 whitespace-nowrap">${fmtTime(e.timestamp)}</td>
          <td><span class="badge badge-ghost badge-sm font-mono">${e.method}</span></td>
          <td class="font-mono text-xs">${e.path}${hasDetail ? ' <span class="text-base-content/30 text-xs">▶</span>' : ''}</td>
          <td class="text-right"><span class="badge ${cls} badge-sm">${e.status}</span></td>
          <td class="text-right font-mono text-xs">${e.duration_ms}</td>
        </tr>`;
      const detailRow = hasDetail ? `
        <tr id="${detailId}" class="hidden">
          <td colspan="5" class="bg-base-200 px-4 py-2">
            <pre class="text-xs text-error whitespace-pre-wrap break-all font-mono">${e.error_detail.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
          </td>
        </tr>` : '';
      return mainRow + detailRow;
    }).join('');
  }
}

// ── Render: logs ───────────────────────────────────────────────────────────

function renderLogs(data) {
  const container = document.getElementById('logs-container');
  const logs = data.logs ?? [];
  if (logs.length === 0) {
    container.innerHTML = '<div class="text-base-content/40 text-center py-6 text-sm font-sans">No log entries captured yet…</div>';
    return;
  }

  const levelCls = {
    ERROR:   'text-error',
    WARNING: 'text-warning',
    INFO:    'text-info',
    DEBUG:   'text-base-content/40',
  };

  container.innerHTML = logs.map(l => {
    const cls = levelCls[l.level] ?? 'text-base-content/60';
    return `
      <div class="flex gap-3 px-4 py-2 hover:bg-base-200 transition-colors">
        <span class="text-base-content/30 whitespace-nowrap flex-shrink-0">${fmtTime(l.timestamp)}</span>
        <span class="${cls} font-bold flex-shrink-0 w-14">${l.level}</span>
        <span class="text-base-content/50 flex-shrink-0 hidden md:inline truncate max-w-xs">${l.logger}</span>
        <span class="text-base-content/80 break-all">${l.message}</span>
      </div>`;
  }).join('');
}

// ── Fetch & refresh cycle ──────────────────────────────────────────────────

async function refresh() {
  const icon = document.getElementById('refresh-icon');
  icon.classList.add('animate-spin');

  const window_ = document.getElementById('time-window').value;
  const logLevel = document.getElementById('log-level-filter').value;

  try {
    const [health, stats, logs] = await Promise.all([
      apiFetch('/api/telemetry/health'),
      apiFetch(`/api/telemetry/stats?window=${window_}`),
      apiFetch(`/api/telemetry/logs?limit=50${logLevel ? '&level=' + logLevel : ''}`),
    ]);
    renderHealth(health);
    renderStats(stats);
    renderLogs(logs);
    document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
  } catch (err) {
    console.error('Telemetry fetch error:', err);
  } finally {
    icon.classList.remove('animate-spin');
  }
}

// ── Auto-refresh timer ─────────────────────────────────────────────────────

let _timer = null;

function startTimer() {
  clearInterval(_timer);
  const interval = parseInt(document.getElementById('refresh-interval').value, 10);
  if (interval > 0) _timer = setInterval(refresh, interval * 1000);
}

// ── Event wiring ───────────────────────────────────────────────────────────

document.getElementById('refresh-btn').addEventListener('click', refresh);
document.getElementById('time-window').addEventListener('change', refresh);
document.getElementById('refresh-interval').addEventListener('change', startTimer);
document.getElementById('log-level-filter').addEventListener('change', refresh);

document.addEventListener('keydown', e => {
  if (e.key === 'r' && !e.ctrlKey && !e.metaKey && document.activeElement.tagName !== 'INPUT') {
    refresh();
  }
});

// ── Boot ───────────────────────────────────────────────────────────────────

await refresh();
startTimer();

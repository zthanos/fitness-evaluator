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

// ── Render: traces table ───────────────────────────────────────────────────

const INTENT_BADGE = {
  activity_list:    'badge-info',
  workout_analysis: 'badge-warning',
  recovery_check:   'badge-success',
  progress_check:   'badge-secondary',
  plan_generation:  'badge-primary',
  nutrition_check:  'badge-accent',
  general:          'badge-ghost',
};

function intentBadge(intent) {
  const cls = INTENT_BADGE[intent] ?? 'badge-ghost';
  return `<span class="badge badge-sm ${cls} font-mono">${intent ?? '—'}</span>`;
}

function renderTraces(data) {
  const tbody = document.getElementById('traces-tbody');
  const rows = data.traces ?? [];
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-base-content/40 py-6">No traces yet — send a chat message first</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(t => {
    const toolCls = t.tool_calls_made > 0 ? 'text-info font-bold' : 'text-base-content/30';
    const latCls  = t.total_latency_ms > 10000 ? 'text-error' : t.total_latency_ms > 4000 ? 'text-warning' : 'text-success';
    const modelShort = (t.model_used || '—').split('/').pop().split(':')[0];
    return `
      <tr class="cursor-pointer hover:bg-base-200 transition-colors" onclick="showTrace('${t.trace_id}')">
        <td class="text-xs text-base-content/50 whitespace-nowrap">${fmtTime(t.timestamp)}</td>
        <td>${intentBadge(t.intent)}</td>
        <td class="text-xs font-mono truncate max-w-[120px]" title="${t.model_used}">${modelShort}</td>
        <td class="text-right ${toolCls}">${t.tool_calls_made}</td>
        <td class="text-right font-mono text-xs">${t.iterations}</td>
        <td class="text-right font-mono text-xs ${latCls}">${fmtMs(t.total_latency_ms)}</td>
        <td class="text-xs text-base-content/60 truncate max-w-[200px]" title="${(t.user_message || '').replace(/"/g, '&quot;')}">${t.user_message || '—'}</td>
      </tr>`;
  }).join('');
}

// ── Trace drill-down modal ─────────────────────────────────────────────────

const STEP_STYLE = {
  think:   { badge: 'badge-info',    icon: '🧠', label: 'THINK' },
  act:     { badge: 'badge-warning', icon: '⚙️',  label: 'ACT'   },
  observe: { badge: 'badge-success', icon: '👁️',  label: 'OBSERVE' },
};

function fmtParams(params) {
  if (!params || Object.keys(params).length === 0) return '<span class="text-base-content/30">—</span>';
  try {
    return `<pre class="text-xs bg-base-300 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">${JSON.stringify(params, null, 2)}</pre>`;
  } catch { return String(params); }
}

function renderTraceDetail(t) {
  const modal = document.getElementById('trace-modal');
  document.getElementById('trace-modal-title').textContent =
    `Trace — ${t.intent ?? 'unknown'} → ${(t.final_content || '').slice(0, 60)}${t.final_content?.length > 60 ? '…' : ''}`;
  document.getElementById('trace-modal-meta').textContent =
    `${new Date(t.timestamp * 1000).toLocaleString()}  ·  session ${t.session_id}  ·  user ${t.user_id}`;

  // Copy button
  const copyBtn = document.getElementById('trace-copy-btn');
  copyBtn.onclick = () => {
    navigator.clipboard.writeText(JSON.stringify(t, null, 2)).then(() => {
      const orig = copyBtn.textContent;
      copyBtn.textContent = 'Copied!';
      setTimeout(() => { copyBtn.textContent = orig; }, 1500);
    });
  };

  // ── Overview stats ────────────────────────────────────────────────────────
  const overviewHtml = `
    <div>
      <h4 class="font-semibold text-sm mb-2">Overview</h4>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
        ${statCard('Intent', intentBadge(t.intent))}
        ${statCard('Total Latency', `<span class="font-mono">${fmtMs(t.total_latency_ms)}</span>`)}
        ${statCard('Tool Calls', `<span class="text-2xl font-black ${t.tool_calls_made > 0 ? 'text-info' : 'text-base-content/30'}">${t.tool_calls_made}</span>`)}
        ${statCard('Model', `<span class="font-mono text-xs break-all">${(t.model_used || '—').split('/').pop()}</span>`)}
      </div>
      <div class="grid grid-cols-3 gap-3 mt-3">
        ${statCard('Retrieval', `<span class="font-mono text-sm">${fmtMs(t.retrieval_latency_ms)}</span>`)}
        ${statCard('Model', `<span class="font-mono text-sm">${fmtMs(t.model_latency_ms)}</span>`)}
        ${statCard('Context Tokens', `<span class="font-mono text-sm">${t.total_context_tokens ?? 0}</span>`)}
      </div>
    </div>`;

  // ── Context layer tokens ──────────────────────────────────────────────────
  const tokens = t.context_tokens ?? {};
  const totalTok = Object.values(tokens).reduce((a, b) => a + b, 0) || 1;
  const tokenRows = Object.entries(tokens)
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a)
    .map(([layer, count]) => {
      const pct = Math.min(100, Math.round((count / totalTok) * 100));
      return `
        <div class="flex items-center gap-2 text-xs">
          <span class="w-40 text-base-content/60 truncate">${layer.replace(/_/g, ' ')}</span>
          <div class="flex-1 bg-base-300 rounded-full h-2">
            <div class="bg-primary h-2 rounded-full" style="width:${pct}%"></div>
          </div>
          <span class="font-mono w-12 text-right">${count}</span>
        </div>`;
    }).join('');
  const contextHtml = tokenRows ? `
    <div>
      <h4 class="font-semibold text-sm mb-2">Context Layers</h4>
      <div class="space-y-1.5">${tokenRows}</div>
    </div>` : '';

  // ── User message ──────────────────────────────────────────────────────────
  const messageHtml = `
    <div>
      <h4 class="font-semibold text-sm mb-1">User Message</h4>
      <div class="bg-base-200 rounded-lg px-3 py-2 text-sm">${(t.user_message || '—').replace(/</g, '&lt;')}</div>
    </div>`;

  // ── Chain of thought timeline ─────────────────────────────────────────────
  let cotHtml = '';
  if (t.intent_used_tools && t.react_steps?.length > 0) {
    const stepCards = t.react_steps.map((s, i) => {
      const style = STEP_STYLE[s.step] ?? { badge: 'badge-ghost', icon: '•', label: s.step.toUpperCase() };
      const meta = s.metadata ?? {};
      let extraHtml = '';

      if (s.step === 'think' && meta.tool_calls_requested?.length > 0) {
        extraHtml = `<div class="mt-1 text-xs text-info">→ will call: <span class="font-mono font-bold">${meta.tool_calls_requested.join(', ')}</span></div>`;
      } else if (s.step === 'think' && meta.tool_calls_requested?.length === 0) {
        extraHtml = `<div class="mt-1 text-xs text-success">→ producing final answer (no tool calls)</div>`;
      } else if (s.step === 'act') {
        const success = meta.success !== false;
        extraHtml = `<div class="mt-1 text-xs ${success ? 'text-success' : 'text-error'}">
          <span class="font-mono font-bold">${meta.tool_name ?? ''}</span>
          ${success ? '✓ succeeded' : '✗ failed'}
          ${meta.error_type ? `<span class="opacity-60"> (${meta.error_type})</span>` : ''}
        </div>`;
      } else if (s.step === 'observe') {
        const success = meta.success !== false;
        extraHtml = `<div class="mt-1 text-xs ${success ? 'text-base-content/50' : 'text-error'}">
          result appended ${success ? '' : '(error)'} · ${meta.result_length ?? '?'} chars
        </div>`;
      }

      return `
        <div class="flex gap-3">
          <div class="flex flex-col items-center">
            <div class="badge ${style.badge} badge-sm w-6 h-6 flex-shrink-0 text-xs">${style.icon}</div>
            ${i < t.react_steps.length - 1 ? '<div class="w-px flex-1 bg-base-300 mt-1"></div>' : ''}
          </div>
          <div class="pb-3 flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-0.5">
              <span class="font-semibold text-xs">${style.label}</span>
              <span class="text-xs text-base-content/40">iter ${s.iteration}</span>
              <span class="text-xs text-base-content/40 ml-auto">${fmtMs(s.latency_ms)}</span>
            </div>
            <p class="text-xs text-base-content/70">${s.detail}</p>
            ${extraHtml}
          </div>
        </div>`;
    }).join('');

    cotHtml = `
      <div>
        <h4 class="font-semibold text-sm mb-3">Chain of Thought</h4>
        <div class="space-y-0">${stepCards}</div>
      </div>`;
  } else if (!t.intent_used_tools) {
    cotHtml = `
      <div>
        <h4 class="font-semibold text-sm mb-2">Chain of Thought</h4>
        <div class="bg-base-200 rounded-lg px-3 py-2 text-xs text-base-content/60">
          Structured output path (LLMAdapter) — no tool calls were made for this intent.
        </div>
      </div>`;
  }

  // ── Tool call cards ───────────────────────────────────────────────────────
  let toolsHtml = '';
  if (t.tool_calls?.length > 0) {
    const cards = t.tool_calls.map(tc => {
      const successCls = tc.success ? 'border-success/30 bg-success/5' : 'border-error/30 bg-error/5';
      const successIcon = tc.success ? '✓' : '✗';
      const successTxt = tc.success ? 'text-success' : 'text-error';
      return `
        <div class="border ${successCls} rounded-lg p-3 space-y-2">
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <span class="${successTxt} font-bold text-xs">${successIcon}</span>
              <span class="font-mono font-bold text-sm">${tc.tool_name}</span>
              <span class="badge badge-ghost badge-xs">iter ${tc.iteration}</span>
            </div>
            <span class="text-xs font-mono text-base-content/50">${fmtMs(tc.latency_ms)}</span>
          </div>
          ${tc.error ? `<div class="text-xs text-error">${tc.error}${tc.error_type ? ` (${tc.error_type})` : ''}</div>` : ''}
          <details class="text-xs">
            <summary class="cursor-pointer text-base-content/50 hover:text-base-content select-none">Parameters</summary>
            ${fmtParams(tc.parameters)}
          </details>
          ${tc.result_preview ? `
          <details class="text-xs">
            <summary class="cursor-pointer text-base-content/50 hover:text-base-content select-none">Result preview</summary>
            <pre class="bg-base-300 rounded p-2 mt-1 overflow-x-auto whitespace-pre-wrap break-all text-xs">${tc.result_preview.replace(/</g, '&lt;')}</pre>
          </details>` : ''}
        </div>`;
    }).join('');
    toolsHtml = `<div><h4 class="font-semibold text-sm mb-2">Tool Calls</h4><div class="space-y-3">${cards}</div></div>`;
  }

  // ── Final response preview ────────────────────────────────────────────────
  const responseHtml = t.final_content ? `
    <div>
      <h4 class="font-semibold text-sm mb-1">Response Preview</h4>
      <div class="bg-base-200 rounded-lg px-3 py-2 text-sm text-base-content/80 whitespace-pre-wrap">${t.final_content.replace(/</g, '&lt;')}${(t.final_content?.length ?? 0) >= 300 ? '…' : ''}</div>
    </div>` : '';

  document.getElementById('trace-modal-body').innerHTML =
    [overviewHtml, contextHtml, messageHtml, cotHtml, toolsHtml, responseHtml].filter(Boolean).join('');

  modal.showModal();
}

function statCard(label, valueHtml) {
  return `
    <div class="bg-base-200 rounded-xl p-3">
      <div class="text-xs text-base-content/50 mb-1">${label}</div>
      <div>${valueHtml}</div>
    </div>`;
}

window.showTrace = async function(traceId) {
  const modal = document.getElementById('trace-modal');
  document.getElementById('trace-modal-body').innerHTML =
    '<div class="text-center py-8 text-base-content/30">Loading…</div>';
  modal.showModal();
  try {
    const t = await apiFetch(`/api/telemetry/traces/${traceId}`);
    renderTraceDetail(t);
  } catch (err) {
    document.getElementById('trace-modal-body').innerHTML =
      `<div class="text-error text-sm">Failed to load trace: ${err.message}</div>`;
  }
};

// ── Fetch & refresh cycle ──────────────────────────────────────────────────

async function refresh() {
  const icon = document.getElementById('refresh-icon');
  icon.classList.add('animate-spin');

  const window_ = document.getElementById('time-window').value;
  const logLevel = document.getElementById('log-level-filter').value;

  try {
    const [health, stats, logs, tracesData] = await Promise.all([
      apiFetch('/api/telemetry/health'),
      apiFetch(`/api/telemetry/stats?window=${window_}`),
      apiFetch(`/api/telemetry/logs?limit=50${logLevel ? '&level=' + logLevel : ''}`),
      apiFetch('/api/telemetry/traces?limit=30'),
    ]);
    renderHealth(health);
    renderStats(stats);
    renderLogs(logs);
    renderTraces(tracesData);
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

/**
 * app.js — ES Module entry point
 *
 * Lazy loading: φορτώνει το all-pages.js μία φορά (με dynamic import)
 * και τα HTML views ανά σελίδα με PageLoader (cached).
 */

import { router }            from '/js/router.js';
import { api }               from '/js/api.js';
import { PageLoader }        from '/js/page-loader.js';
import { NavigationSidebar } from '/js/navigation-sidebar.js';
import { initAuth, isAuthenticated, getToken, getUser, logout } from '/js/auth.js';

// ─── Globals ──────────────────────────────────────────────────────────────────
window.api = api;

window.renderPage = function(html) {
    return new Promise(resolve => {
        const main = document.getElementById('main-content');
        main.style.transition = 'opacity 150ms ease';
        main.style.opacity = '0';
        
        requestAnimationFrame(() => {
          main.innerHTML = html;
          
          // Wait for next frame to ensure DOM is updated
          requestAnimationFrame(() => {
            main.style.opacity = '1';
            
            // Give the browser time to paint before resolving
            requestAnimationFrame(() => {
              resolve();
            });
          });
        });
      });
};

window.showToast = function(message, type = 'info', duration = 5000) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `alert alert-${type} shadow-lg`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.transition = 'opacity 300ms';
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, duration);
};

// ─── Theme ────────────────────────────────────────────────────────────────────
document.documentElement.setAttribute('data-theme', localStorage.getItem('theme') || 'light');
document.addEventListener('themechange', e => localStorage.setItem('theme', e.detail));

// ─── Sidebar ──────────────────────────────────────────────────────────────────
const sidebar = new NavigationSidebar('sidebar-container');
const updateSidebar = path => sidebar.setActiveRoute(path);

// ─── Tick helper ──────────────────────────────────────────────────────────────
const tick = () => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));

// ─── Lazy load all page classes (μία φορά, cached από browser) ───────────────
let _pages = null;
async function getPages() {
  if (!_pages) _pages = await import('/js/pages/all-pages.js');
  return _pages;
}

// ─── Route helper ─────────────────────────────────────────────────────────────
async function mountPage(sidebarPath, viewPath, PageClass, extraImports = []) {
    updateSidebar(sidebarPath);
  
    // Load HTML and any extra JS modules in parallel
    const [html] = await Promise.all([
      PageLoader.load(viewPath),
      ...extraImports.map(p => import(p)),
    ]);
    
    // Render the HTML and wait for it to be fully in the DOM
    await window.renderPage(html);
    
    // Wait for DOM to be fully ready
    await tick();
    await tick();
    
    // Now create and return the page instance
    const page = new PageClass();
    return page;
}

// ─── Routes ───────────────────────────────────────────────────────────────────
router

  .on('/', async (params, query) => {
    const { DashboardPage } = await getPages();
    const page = await mountPage('/', '/js/views/dashboard.html', DashboardPage);
    await page.init(params, query);
    return page;
  })

  .on('/index.html', () => router.replace('/'))

  .on('/activities', async (params, query) => {
    const { ActivitiesPage } = await getPages();
    const page = await mountPage('/activities', '/js/views/activities.html', ActivitiesPage, [
      '/js/components/activity-list.js',
    ]);
    await page.init(params, query);
    return page;
  })

  .on('/activities/:id', async (params, query) => {
    const { ActivityDetailPage } = await getPages();
    const page = await mountPage('/activities', '/js/views/activity-detail.html', ActivityDetailPage, [
      '/js/components/activity-detail.js',
    ]);
    await page.init(params, query);
    return page;
  })

  .on('/logs', async (params, query) => {
    const { LogsPage } = await getPages();
    const page = await mountPage('/logs', '/js/views/logs.html', LogsPage, [
      '/js/daily-log-form.js',
      '/js/daily-log-list.js',
    ]);
    await page.init(params, query);
    return page;
  })

  .on('/metrics', async (params, query) => {
    const { MetricsPage } = await getPages();
    const page = await mountPage('/metrics', '/js/views/metrics.html', MetricsPage, [
      '/js/chart-config.js',
      '/js/metrics-form.js',
      '/js/metrics-chart.js',
      '/js/metrics-list.js',
    ]);
    await page.init(params, query);
    return page;
  })

  .on('/chat', async (params, query) => {
    const { ChatPage } = await getPages();
    const page = await mountPage('/chat', '/js/views/chat.html', ChatPage, [
      '/js/coach-chat.js',
    ]);
    await page.init(params, query);
    return page;
  })

  .on('/training-plans', async (params, query) => {
    const { TrainingPlansPage } = await getPages();
    const page = await mountPage('/training-plans', '/js/views/training-plans.html', TrainingPlansPage, [
      '/js/training-plans-list.js',
    ]);
    await page.init(params, query);
    return page;
  })

  .on('/settings', async (params, query) => {
    const { SettingsPage } = await getPages();
    const page = await mountPage('/settings', '/js/views/settings.html', SettingsPage, [
      '/js/settings.js',
    ]);
    await page.init(params, query);
    return page;
  })

  .on('/app-settings', async (params, query) => {
    const { AppSettingsPage } = await getPages();
    const page = await mountPage('/app-settings', '/js/views/app-settings.html', AppSettingsPage, [
      '/js/app-settings.js',
    ]);
    await page.init(params, query);
    return page;
  })

  .on('/evaluations', async (params, query) => {
    const { EvaluationsPage } = await getPages();
    const page = await mountPage('/evaluations', '/js/views/evaluations-list.html', EvaluationsPage);
    await page.init(params, query);
    return page;
  })

  .on('/evaluations/:id', async (params, query) => {
    const { EvaluationDetailPage } = await getPages();
    const page = await mountPage('/evaluations', '/js/views/evaluation-detail.html', EvaluationDetailPage);
    await page.init(params, query);
    return page;
  })

  // Legacy redirects
  .on('/settings.html',         () => router.replace('/settings'))
  .on('/chat.html',             () => router.replace('/chat'))
  .on('/logs.html',             () => router.replace('/logs'))
  .on('/metrics.html',          () => router.replace('/metrics'))
  .on('/training-plans.html',   () => router.replace('/training-plans'))
  .on('/activities.html',       () => router.replace('/activities'))
  .on('/evaluations-list.html', () => router.replace('/evaluations'))

  .on('/telemetry', () => { window.location.href = '/telemetry'; })

  .notFound(path => {
    window.renderPage(`
      <div class="flex flex-col items-center justify-center h-screen gap-6">
        <div class="text-8xl">🏃</div>
        <h1 class="text-4xl font-bold">Page Not Found</h1>
        <p class="text-base-content/60">No route: <code class="badge">${path}</code></p>
        <a href="/" class="btn btn-primary">Back to Dashboard</a>
      </div>`);
  });

// ─── Boot ─────────────────────────────────────────────────────────────────────
(async () => {
  try {
    await initAuth();
  } catch (err) {
    console.warn('[app] initAuth failed, redirecting to landing:', err);
    window.location.replace('/');
    return;
  }
  if (!isAuthenticated()) {
    window.location.replace('/');
    return;
  }
  sidebar.setUser(getUser());
  window.appLogout = logout;
  window.getAuthToken = getToken;
  router.start();
})();
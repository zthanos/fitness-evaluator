/**
 * router.js — ES Module
 *
 * Client-side router με lazy loading scripts ανά page.
 * Κάθε route ορίζει ποια scripts χρειάζεται — φορτώνονται
 * με dynamic import() μόνο όταν επισκεφτείς εκείνη τη σελίδα.
 */

export class Router {
    constructor() {
      this._routes = [];
      this._currentPage = null;
      this._notFoundHandler = null;
  
      document.addEventListener('click', (e) => {
        const anchor = e.target.closest('a[href]');
        if (!anchor) return;
        const href = anchor.getAttribute('href');
        if (
          !href || href.startsWith('http') || href.startsWith('//') ||
          href.startsWith('mailto:') || href === '#' ||
          e.ctrlKey || e.metaKey || e.shiftKey || e.altKey
        ) return;
        e.preventDefault();
        this.navigate(href);
      });
  
      window.addEventListener('popstate', () => this._dispatch(window.location.pathname));
    }
  
    on(path, handler) {
      const keys = [];
      const pattern = new RegExp(
        '^' +
        path.replace(/\//g, '\\/').replace(/:([^/]+)/g, (_, k) => { keys.push(k); return '([^/]+)'; }) +
        '\\/?$'
      );
      this._routes.push({ pattern, keys, handler });
      return this;
    }
  
    notFound(handler) { this._notFoundHandler = handler; return this; }
  
    navigate(path) {
      if (window.location.pathname === path) return;
      window.history.pushState({}, '', path);
      this._dispatch(path);
    }
  
    replace(path) {
      window.history.replaceState({}, '', path);
      this._dispatch(path);
    }
  
    start() { this._dispatch(window.location.pathname); }
  
    async _dispatch(pathname) {
      if (this._currentPage?.destroy) await this._currentPage.destroy();
      this._currentPage = null;
  
      const query = Object.fromEntries(new URLSearchParams(window.location.search));
  
      for (const route of this._routes) {
        const match = pathname.match(route.pattern);
        if (!match) continue;
  
        const params = {};
        route.keys.forEach((k, i) => { params[k] = decodeURIComponent(match[i + 1]); });
  
        try {
          this._currentPage = await route.handler(params, query) || null;
        } catch (err) {
          console.error('[Router]', err);
          this._renderError(err);
        }
        return;
      }
  
      this._notFoundHandler?.(pathname) ?? this._renderError(new Error(`No route: "${pathname}"`));
    }
  
    _renderError(err) {
      const el = document.getElementById('main-content');
      if (el) el.innerHTML = `
        <div class="p-12 flex flex-col items-center justify-center gap-4">
          <div class="text-6xl">😵</div>
          <h2 class="text-2xl font-bold">Something went wrong</h2>
          <p class="text-base-content/60">${err.message}</p>
          <a href="/" class="btn btn-primary">Go Home</a>
        </div>`;
    }
  }
  
  export const router = new Router();
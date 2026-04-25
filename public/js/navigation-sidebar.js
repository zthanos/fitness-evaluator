/**
 * NavigationSidebar  —  SPA Edition
 *
 * Changes from the MPA version:
 *  • Uses router.navigate() instead of full-page <a href> reloads.
 *  • setActiveRoute() re-renders only the nav items (not the whole sidebar).
 *  • Theme toggle dispatches a 'themechange' CustomEvent so app.js can persist it.
 *  • Clean paths (no .html extensions) to match the SPA router.
 */

import { router } from '/js/router.js';

class NavigationSidebar {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.currentRoute = this._getCurrentRoute();
    this.isMobileMenuOpen = false;
    this._user = null;

    this.navItems = [
      { id: 'dashboard',       label: 'Dashboard',       icon: '📊', path: '/' },
      { id: 'activities',      label: 'Activities',       icon: '⚡', path: '/activities' },
      { id: 'training-plans',  label: 'Training Plans',   icon: '🎯', path: '/training-plans' },
      { id: 'metrics',         label: 'Metrics',          icon: '📈', path: '/metrics' },
      { id: 'logs',            label: 'Logs',             icon: '📝', path: '/logs' },
      { id: 'evaluations',     label: 'Evaluations',      icon: '🏅', path: '/evaluations' },
      { id: 'chat',            label: 'Chat',             icon: '💬', path: '/chat' },
      { id: 'settings',        label: 'Settings',         icon: '⚙️', path: '/settings' },
      { id: 'telemetry',       label: 'Telemetry',        icon: '📡', path: '/telemetry' },
    ];

    this._init();
  }

  // ─── Public API ─────────────────────────────────────────────────────────────

  setUser(user) {
    this._user = user;
    const footer = document.querySelector('#navigation-sidebar .sidebar-footer');
    if (footer) footer.innerHTML = this._renderFooter();
    this._attachFooterListeners();
  }

  /**
   * Update the highlighted nav item after a route change.
   * Only re-renders the <ul> to avoid re-building the whole sidebar.
   */
  setActiveRoute(route) {
    this.currentRoute = route;
    const nav = document.querySelector('#navigation-sidebar nav ul');
    if (nav) {
      nav.innerHTML = this._renderNavItems();
      this._attachNavLinkListeners();
    }
  }

  toggleMobile() {
    this.isMobileMenuOpen = !this.isMobileMenuOpen;
    const sidebar = document.getElementById('navigation-sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    if (this.isMobileMenuOpen) {
      sidebar.classList.remove('-translate-x-full');
      overlay.classList.remove('opacity-0', 'pointer-events-none');
      overlay.classList.add('opacity-100');
      document.body.style.overflow = 'hidden';
    } else {
      sidebar.classList.add('-translate-x-full');
      overlay.classList.add('opacity-0', 'pointer-events-none');
      overlay.classList.remove('opacity-100');
      document.body.style.overflow = '';
    }
  }

  // ─── Private ────────────────────────────────────────────────────────────────

  _getCurrentRoute() {
    const p = window.location.pathname;
    return (p === '' || p === '/index.html') ? '/' : p;
  }

  _init() {
    this._render();
    this._attachEventListeners();
    window.addEventListener('resize', () => this._handleResize());
  }

  _render() {
    this.container.innerHTML = `
      <!-- Mobile Hamburger -->
      <button id="mobile-menu-toggle"
        class="btn btn-ghost btn-circle fixed top-4 left-4 z-50 lg:hidden"
        aria-label="Toggle navigation menu">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M4 6h16M4 12h16M4 18h16"/>
        </svg>
      </button>

      <!-- Mobile Overlay -->
      <div id="sidebar-overlay"
        class="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden transition-opacity duration-300 opacity-0 pointer-events-none">
      </div>

      <!-- Sidebar -->
      <aside id="navigation-sidebar"
        class="fixed top-0 left-0 h-screen bg-base-100 shadow-lg z-40
               transition-transform duration-300 transform -translate-x-full lg:translate-x-0"
        style="width: var(--sidebar-width, 16rem);">

        <!-- Header -->
        <div class="flex items-center justify-between p-4 border-b border-base-300">
          <a href="/" data-spa-link class="flex flex-col items-center gap-2 text-xl font-bold">
            <img src="/assets/logo.png" alt="Logo" class="w-auto" onerror="this.style.display='none'">
            <div class="flex">
              <span class="hidden lg:inline pr-2" style="font-family:Inter,sans-serif;color:#7C3AED;">Fitness</span>
              <span class="hidden lg:inline"       style="font-family:Inter,sans-serif;color:#2563EB;">Platform</span>
            </div>
          </a>
          <button id="mobile-menu-close"
            class="btn btn-ghost btn-sm btn-circle lg:hidden"
            aria-label="Close navigation menu">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <!-- Nav Links -->
        <nav class="p-4">
          <ul class="menu menu-vertical gap-2">
            ${this._renderNavItems()}
          </ul>
        </nav>

        <!-- Footer -->
        <div class="sidebar-footer absolute bottom-0 left-0 right-0 p-4 border-t border-base-300">
          ${this._renderFooter()}
        </div>
      </aside>`;
  }

  _renderFooter() {
    const name = this._user?.name ?? '';
    const email = this._user?.email ?? '';
    return `
      ${name ? `
      <div class="flex items-center gap-2 mb-2 px-1 overflow-hidden">
        <div class="avatar placeholder">
          <div class="bg-primary text-primary-content rounded-full w-8 h-8 text-sm font-bold flex items-center justify-center">
            ${name.charAt(0).toUpperCase()}
          </div>
        </div>
        <div class="hidden lg:block overflow-hidden">
          <div class="text-sm font-semibold truncate">${name}</div>
          ${email ? `<div class="text-xs text-base-content/50 truncate">${email}</div>` : ''}
        </div>
      </div>` : ''}
      <button id="theme-toggle-btn"
        class="btn btn-ghost btn-sm w-full justify-start gap-2"
        aria-label="Toggle theme">
        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/>
        </svg>
        <span class="hidden lg:inline">Toggle Theme</span>
      </button>
      ${name ? `
      <button id="logout-btn"
        class="btn btn-ghost btn-sm w-full justify-start gap-2 text-error mt-1"
        aria-label="Log out">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h6a2 2 0 012 2v1"/>
        </svg>
        <span class="hidden lg:inline">Log out</span>
      </button>` : ''}`;
  }

  _renderNavItems() {
    return this.navItems.map(item => {
      const isActive = this._isActiveRoute(item.path);
      const activeClass = isActive ? 'active bg-primary text-primary-content' : '';
      return `
        <li>
          <a href="${item.path}" data-spa-link
            class="${activeClass} flex items-center gap-3"
            aria-current="${isActive ? 'page' : 'false'}">
            <span class="text-xl">${item.icon}</span>
            <span class="hidden lg:inline">${item.label}</span>
          </a>
        </li>`;
    }).join('');
  }

  _isActiveRoute(path) {
    const cur = this.currentRoute.toLowerCase();
    const p   = path.toLowerCase();
    if ((cur === '/' || cur === '/index.html') && p === '/') return true;
    if (p === '/') return false;
    return cur === p || cur.startsWith(p + '/');
  }

  _attachFooterListeners() {
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        document.dispatchEvent(new CustomEvent('themechange', { detail: next }));
      });
    }
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => window.appLogout?.());
    }
  }

  _attachEventListeners() {
    const toggleBtn = document.getElementById('mobile-menu-toggle');
    if (toggleBtn) toggleBtn.addEventListener('click', () => this.toggleMobile());

    const closeBtn = document.getElementById('mobile-menu-close');
    if (closeBtn) closeBtn.addEventListener('click', () => this.toggleMobile());

    const overlay = document.getElementById('sidebar-overlay');
    if (overlay) overlay.addEventListener('click', () => this.toggleMobile());

    this._attachFooterListeners();
    this._attachNavLinkListeners();
  }

  _attachNavLinkListeners() {
    document.querySelectorAll('[data-spa-link]').forEach(link => {
      // Remove any previously attached listener by cloning
      const clone = link.cloneNode(true);
      link.parentNode.replaceChild(clone, link);
      clone.addEventListener('click', (e) => {
        e.preventDefault();
        if (this.isMobileMenuOpen) this.toggleMobile();
        router.navigate(clone.getAttribute('href'));
      });
    });
  }

  _handleResize() {
    if (window.innerWidth >= 1024 && this.isMobileMenuOpen) {
      this.toggleMobile();
    }
  }
}

export { NavigationSidebar };
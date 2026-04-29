/**
 * NavigationSidebar  —  SPA Edition
 *
 * Changes from the MPA version:
 *  • Uses router.navigate() instead of full-page <a href> reloads.
 *  • setActiveRoute() re-renders only the <ul> to avoid re-building the whole sidebar.
 *  • Theme toggle dispatches a 'themechange' CustomEvent so app.js can persist it.
 *  • Clean paths (no .html extensions) to match the SPA router.
 */

import { router } from '/js/router.js';

// ── Shared SVG icon helper ────────────────────────────────────────────────────
const icon = (path, size = '5', sw = '1.5') =>
  `<svg xmlns="http://www.w3.org/2000/svg" class="w-${size} h-${size} flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;

class NavigationSidebar {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.currentRoute = this._getCurrentRoute();
    this.isMobileMenuOpen = false;
    this._user = null;

    this.mainNavItems = [
      {
        id: 'dashboard', label: 'Dashboard', path: '/',
        icon: icon('<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>'),
      },
      {
        id: 'activities', label: 'Activities', path: '/activities',
        icon: icon('<path d="M13 10V3L4 14h7v7l9-11h-7z"/>'),
      },
      {
        id: 'training-plans', label: 'Training Plans', path: '/training-plans',
        icon: icon('<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>'),
      },
      {
        id: 'metrics', label: 'Metrics', path: '/metrics',
        icon: icon('<path d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>'),
      },
      {
        id: 'logs', label: 'Logs', path: '/logs',
        icon: icon('<path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>'),
      },
      {
        id: 'evaluations', label: 'Evaluations', path: '/evaluations',
        icon: icon('<path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/>'),
      },
      {
        id: 'chat', label: 'Chat', path: '/chat',
        icon: icon('<path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>'),
      },
    ];

    this.systemNavItems = [
      {
        id: 'app-settings', label: 'App Settings', path: '/app-settings',
        icon: icon('<path d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/>'),
      },
      {
        id: 'telemetry', label: 'Telemetry', path: '/telemetry', pulse: true,
        icon: icon('<path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>'),
      },
    ];

    this._init();
  }

  // ─── Public API ─────────────────────────────────────────────────────────────

  setUser(user) {
    this._user = user;
    const footer = document.querySelector('#navigation-sidebar .sidebar-footer');
    if (footer) footer.innerHTML = this._renderFooter();
    this._attachFooterListeners();
    this._loadAvatar();
  }

  setActiveRoute(route) {
    this.currentRoute = route;
    const mainNav = document.querySelector('#navigation-sidebar .main-nav-list');
    const sysNav  = document.querySelector('#navigation-sidebar .system-nav-list');
    if (mainNav) {
      mainNav.innerHTML = this._renderNavItems(this.mainNavItems);
      this._attachNavLinkListeners();
    }
    if (sysNav) {
      sysNav.innerHTML = this._renderNavItems(this.systemNavItems);
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
        class="fixed top-0 left-0 h-screen bg-base-100 shadow-lg z-40 flex flex-col
               transition-transform duration-300 transform -translate-x-full lg:translate-x-0"
        style="width: var(--sidebar-width, 16rem);">

        <!-- Header / Logo -->
        <div class="flex items-center justify-between p-4 border-b border-base-300 flex-shrink-0">
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

        <!-- Scrollable nav area -->
        <div class="flex-1 overflow-y-auto">
          <!-- Main Nav -->
          <nav class="p-3 pb-1">
            <ul class="menu menu-vertical gap-1 main-nav-list">
              ${this._renderNavItems(this.mainNavItems)}
            </ul>
          </nav>

          <!-- Separator -->
          <div class="mx-4 border-t border-base-300/60"></div>

          <!-- System section -->
          <nav class="p-3 pt-2">
            <div class="hidden lg:block px-2 mb-1.5">
              <span class="text-[10px] font-semibold tracking-widest uppercase text-base-content/30 select-none">System</span>
            </div>
            <ul class="menu menu-vertical gap-0.5 system-nav-list">
              ${this._renderNavItems(this.systemNavItems)}
            </ul>
          </nav>
        </div>

        <!-- Footer / Profile Card -->
        <div class="sidebar-footer flex-shrink-0 p-3 border-t border-base-300">
          ${this._renderFooter()}
        </div>
      </aside>`;
  }

  _renderNavItems(items) {
    return items.map(item => {
      const isActive = this._isActiveRoute(item.path);
      const activeClass = isActive ? 'active bg-primary text-primary-content' : '';
      const dimClass = !isActive ? 'text-base-content/60 hover:text-base-content' : '';

      // Sub-items: smaller, indented, dimmer when inactive
      if (item.sub) {
        const pulseHtml = item.pulse
          ? `<span class="relative flex h-2 w-2 ml-auto">
               <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
               <span class="relative inline-flex rounded-full h-2 w-2 bg-success"></span>
             </span>`
          : '';
        return `
          <li>
            <a href="${item.path}" data-spa-link
              class="${activeClass} flex items-center gap-2 pl-5 py-1.5 text-sm ${dimClass}"
              aria-current="${isActive ? 'page' : 'false'}">
              ${item.icon}
              <span class="hidden lg:inline">${item.label}</span>
              ${pulseHtml}
            </a>
          </li>`;
      }

      // Primary items — SVG icon
      const pulseHtml = item.pulse
        ? `<span class="relative flex h-2 w-2 ml-auto hidden lg:flex">
             <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75"></span>
             <span class="relative inline-flex rounded-full h-2 w-2 bg-success"></span>
           </span>`
        : '';
      return `
        <li>
          <a href="${item.path}" data-spa-link
            class="${activeClass} flex items-center gap-3"
            aria-current="${isActive ? 'page' : 'false'}">
            ${item.icon}
            <span class="hidden lg:inline">${item.label}</span>
            ${pulseHtml}
          </a>
        </li>`;
    }).join('');
  }

  _renderFooter() {
    const name    = this._user?.name  ?? '';
    const email   = this._user?.email ?? '';
    const initial = name ? name.charAt(0).toUpperCase() : '?';

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

    const themeIcon = isDark
      ? `<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
           <path fill-rule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clip-rule="evenodd"/>
         </svg>`
      : `<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
           <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/>
         </svg>`;

    // Shared class for each footer action button — explicit rounded hover rectangle
    const btnCls = 'flex-1 flex items-center justify-center h-8 rounded-lg transition-all duration-150 text-base-content/60 hover:text-base-content hover:bg-base-300/70 cursor-pointer';

    return `
      <!-- Profile card -->
      <div class="rounded-xl bg-base-200 p-2.5 mb-2">
        <div class="flex items-center gap-3">
          <!-- Avatar with online dot -->
          <div class="relative flex-shrink-0">
            <div class="w-10 h-10 rounded-full overflow-hidden bg-primary flex items-center justify-center">
              <img id="sidebar-avatar-img" class="w-full h-full object-cover hidden" alt="Profile photo" />
              <span id="sidebar-avatar-initials" class="text-base font-bold text-primary-content">${initial}</span>
            </div>
            <span class="absolute bottom-0 right-0 w-2.5 h-2.5 bg-success rounded-full border-2 border-base-200"></span>
          </div>
          <!-- Name & email — ml-1 for a little extra breathing room -->
          <div class="flex-1 min-w-0 hidden lg:block ml-1">
            <div class="text-sm font-semibold truncate">${name || 'User'}</div>
            ${email ? `<div class="text-xs text-base-content/50 truncate">${email}</div>` : ''}
          </div>
        </div>

        <!-- Action icon row -->
        <div class="flex items-center gap-0.5 mt-2 pt-2 border-t border-base-300">
          <!-- Theme toggle -->
          <button id="theme-toggle-btn" title="${isDark ? 'Switch to light' : 'Switch to dark'}"
            class="${btnCls}">
            ${themeIcon}
          </button>

          <!-- Profile / Settings shortcut -->
          <a href="/settings" data-spa-link title="Edit profile" class="${btnCls}">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
            </svg>
          </a>

          <!-- Logout -->
          ${name ? `
          <button id="logout-btn" title="Log out"
            class="${btnCls} text-error/70 hover:text-error hover:bg-error/10">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h6a2 2 0 012 2v1"/>
            </svg>
          </button>` : ''}
        </div>
      </div>`;
  }

  async _loadAvatar() {
    try {
      const token = window.getAuthToken?.();
      const res = await fetch('/api/settings/profile', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) return;
      const profile = await res.json();
      if (!profile.avatar_url) return;

      const img      = document.getElementById('sidebar-avatar-img');
      const initials = document.getElementById('sidebar-avatar-initials');
      if (!img) return;

      img.onload = () => {
        img.classList.remove('hidden');
        initials?.classList.add('hidden');
      };
      img.src = profile.avatar_url + '?t=' + Date.now();
    } catch {
      // silently ignore — avatar is optional
    }
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
        const footer = document.querySelector('#navigation-sidebar .sidebar-footer');
        if (footer) footer.innerHTML = this._renderFooter();
        this._attachFooterListeners();
        this._loadAvatar();
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

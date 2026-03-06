/**
 * NavigationSidebar Component
 * 
 * Persistent navigation sidebar for the Fitness Platform V2
 * - Visible on left side at viewport width >= 768px
 * - Collapses to hamburger menu at viewport width < 768px
 * - Highlights active page based on current route
 * 
 * Requirements: 1.1, 1.2, 1.3
 */

class NavigationSidebar {
  constructor(containerId, currentRoute) {
    this.container = document.getElementById(containerId);
    this.currentRoute = currentRoute || this._getCurrentRoute();
    this.isMobileMenuOpen = false;
    
    // Navigation items configuration
    this.navItems = [
      { id: 'dashboard', label: 'Dashboard', icon: '📊', path: '/index.html' },
      { id: 'activities', label: 'Activities', icon: '⚡', path: '/activities' },
      { id: 'metrics', label: 'Metrics', icon: '📈', path: '/metrics' },
      { id: 'logs', label: 'Logs', icon: '📝', path: '/logs' },
      { id: 'evaluations', label: 'Evaluations', icon: '🎯', path: '/evaluation.html' },
      { id: 'chat', label: 'Chat', icon: '💬', path: '/chat.html' },
      { id: 'settings', label: 'Settings', icon: '⚙️', path: '/settings.html' }
    ];
    
    this._init();
  }
  
  /**
   * Initialize the sidebar component
   * @private
   */
  _init() {
    this.render();
    this._attachEventListeners();
    this._handleResize();
    
    // Listen for window resize to handle responsive behavior
    window.addEventListener('resize', () => this._handleResize());
  }
  
  /**
   * Get the current route from the URL
   * @private
   * @returns {string} Current route path
   */
  _getCurrentRoute() {
    const path = window.location.pathname;
    // Handle root path
    if (path === '/' || path === '') {
      return '/index.html';
    }
    return path;
  }
  
  /**
   * Render the sidebar HTML
   */
  render() {
    const sidebarHTML = `
      <!-- Mobile Hamburger Button -->
      <button 
        id="mobile-menu-toggle" 
        class="btn btn-ghost btn-circle fixed top-4 left-4 z-50 lg:hidden"
        aria-label="Toggle navigation menu"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
        </svg>
      </button>
      
      <!-- Sidebar Overlay (Mobile) -->
      <div 
        id="sidebar-overlay" 
        class="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden transition-opacity duration-300 opacity-0 pointer-events-none"
      ></div>
      
      <!-- Sidebar -->
      <aside 
        id="navigation-sidebar" 
        class="fixed top-0 left-0 h-screen bg-base-100 shadow-lg z-40 transition-transform duration-300 transform -translate-x-full lg:translate-x-0"
        style="width: var(--sidebar-width, 16rem);"
      >
        <!-- Sidebar Header -->
        <div class="flex items-center justify-between p-4 border-b border-base-300">
          <a href="/index.html" class="flex flex-col items-center gap-2 text-xl font-bold">
            <img src="/assets/logo.png">
            <div class="flex">
              <span class="hidden lg:inline pr-2" style="font-family: Inter;sans-serif;color: #7C3AED;">Fitness</span>
              <span class="hidden lg:inline" style="font-family: Inter;color: #2563EB;"> Platform</span>
            </div>
          </a>
          <button 
            id="mobile-menu-close" 
            class="btn btn-ghost btn-sm btn-circle lg:hidden"
            aria-label="Close navigation menu"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
        
        <!-- Navigation Links -->
        <nav class="p-4">
          <ul class="menu menu-vertical gap-2">
            ${this._renderNavItems()}
          </ul>
        </nav>
        
        <!-- Sidebar Footer -->
        <div class="absolute bottom-0 left-0 right-0 p-4 border-t border-base-300">
          <button 
            onclick="document.documentElement.setAttribute('data-theme', document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark')" 
            class="btn btn-ghost btn-sm w-full justify-start gap-2"
            aria-label="Toggle theme"
          >
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"></path>
            </svg>
            <span class="hidden lg:inline">Toggle Theme</span>
          </button>
        </div>
      </aside>
    `;
    
    this.container.innerHTML = sidebarHTML;
  }
  
  /**
   * Render navigation items
   * @private
   * @returns {string} HTML for navigation items
   */
  _renderNavItems() {
    return this.navItems.map(item => {
      const isActive = this._isActiveRoute(item.path);
      const activeClass = isActive ? 'active bg-primary text-primary-content' : '';
      
      return `
        <li>
          <a 
            href="${item.path}" 
            class="${activeClass} flex items-center gap-3"
            data-route="${item.path}"
            aria-current="${isActive ? 'page' : 'false'}"
          >
            <span class="text-xl">${item.icon}</span>
            <span class="hidden lg:inline">${item.label}</span>
          </a>
        </li>
      `;
    }).join('');
  }
  
  /**
   * Check if a route is the active route
   * @private
   * @param {string} path - Route path to check
   * @returns {boolean} True if route is active
   */
  _isActiveRoute(path) {
    // Normalize paths for comparison
    const currentPath = this.currentRoute.toLowerCase();
    const checkPath = path.toLowerCase();
    
    // Handle root/index special case
    if ((currentPath === '/' || currentPath === '/index.html') && 
        (checkPath === '/' || checkPath === '/index.html')) {
      return true;
    }
    
    return currentPath === checkPath || currentPath.endsWith(checkPath);
  }
  
  /**
   * Set the active route and update UI
   * @param {string} route - New active route
   */
  setActiveRoute(route) {
    this.currentRoute = route;
    this.render();
    this._attachEventListeners();
  }
  
  /**
   * Toggle mobile menu open/closed
   */
  toggleMobile() {
    this.isMobileMenuOpen = !this.isMobileMenuOpen;
    
    const sidebar = document.getElementById('navigation-sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    
    if (this.isMobileMenuOpen) {
      // Open menu
      sidebar.classList.remove('-translate-x-full');
      overlay.classList.remove('opacity-0', 'pointer-events-none');
      overlay.classList.add('opacity-100');
      document.body.style.overflow = 'hidden'; // Prevent scrolling
    } else {
      // Close menu
      sidebar.classList.add('-translate-x-full');
      overlay.classList.add('opacity-0', 'pointer-events-none');
      overlay.classList.remove('opacity-100');
      document.body.style.overflow = ''; // Restore scrolling
    }
  }
  
  /**
   * Attach event listeners to interactive elements
   * @private
   */
  _attachEventListeners() {
    // Mobile menu toggle button
    const toggleBtn = document.getElementById('mobile-menu-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => this.toggleMobile());
    }
    
    // Mobile menu close button
    const closeBtn = document.getElementById('mobile-menu-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.toggleMobile());
    }
    
    // Overlay click to close
    const overlay = document.getElementById('sidebar-overlay');
    if (overlay) {
      overlay.addEventListener('click', () => this.toggleMobile());
    }
    
    // Close mobile menu when clicking a nav link
    const navLinks = document.querySelectorAll('#navigation-sidebar a[data-route]');
    navLinks.forEach(link => {
      link.addEventListener('click', () => {
        if (this.isMobileMenuOpen) {
          this.toggleMobile();
        }
      });
    });
  }
  
  /**
   * Handle window resize events
   * @private
   */
  _handleResize() {
    const isDesktop = window.innerWidth >= 768; // md breakpoint
    
    // Close mobile menu if resizing to desktop
    if (isDesktop && this.isMobileMenuOpen) {
      this.toggleMobile();
    }
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = NavigationSidebar;
}

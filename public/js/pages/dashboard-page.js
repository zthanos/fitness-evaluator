/**
 * DashboardPage
 * Placeholder — replace with your existing dashboard component.
 */

class DashboardPage {
    async init(params, query) {
      window.renderPage(`
        <div class="p-6">
          <h1 class="text-4xl font-bold mb-6">📊 Dashboard</h1>
          <div id="dashboard-container">
            <div class="flex justify-center items-center py-8">
              <span class="loading loading-spinner loading-lg"></span>
            </div>
          </div>
        </div>`);
      await this._tick();
      // Mount your existing dashboard component here
    }
  
    destroy() {}
    _tick() { return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }
  }
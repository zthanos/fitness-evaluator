/**
 * MetricsPage
 * Equivalent to metrics.html + its inline <script>.
 */

class MetricsPage {
    constructor() {
      this._form  = null;
      this._chart = null;
      this._list  = null;
      this._extendedMode = localStorage.getItem('metricsExtendedMode') === 'true';
    }
  
    async init(params, query) {
      window.renderPage(this._html());
      await this._tick();
  
      const toggle = document.getElementById('extended-mode-toggle');
      if (toggle) toggle.checked = this._extendedMode;
  
      this._form  = new MetricsForm('metrics-form-container', null, this._extendedMode);
      this._form.render();
  
      this._chart = new MetricsChart('metrics-charts-container', api);
      await this._chart.render();
  
      this._list = new MetricsList('metrics-list-container', this._extendedMode);
      await this._list.load();
  
      toggle?.addEventListener('change', (e) => {
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
  
      this._form.onError((err) => console.error('Error saving measurement:', err));
  
      document.getElementById('add-metric-btn')?.addEventListener('click', () => {
        document.getElementById('metric-form-modal')?.showModal();
      });
    }
  
    destroy() {}
  
    _html() {
      return `
        <div class="p-6 flex flex-col h-screen overflow-hidden">
          <div class="flex justify-between items-center mb-6 flex-shrink-0">
            <div class="flex items-center gap-4">
              <h1 class="text-4xl font-bold">📊 Body Metrics</h1>
              <div class="form-control">
                <label class="label cursor-pointer gap-2">
                  <span class="label-text">Extended Mode</span>
                  <input type="checkbox" id="extended-mode-toggle" class="toggle toggle-primary" />
                </label>
              </div>
            </div>
            <button id="add-metric-btn" class="btn btn-primary gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
              </svg>
              Add Measurement
            </button>
          </div>
  
          <div class="card bg-base-100 shadow-xl mb-6 flex-shrink-0">
            <div class="card-body">
              <h2 class="card-title mb-4">Metrics History</h2>
              <div id="metrics-charts-container"></div>
            </div>
          </div>
  
          <div class="card bg-base-100 shadow-xl flex-1 flex flex-col overflow-hidden">
            <div class="card-body flex flex-col overflow-hidden">
              <div class="flex-shrink-0">
                <h2 class="card-title">All Measurements</h2>
                <p class="text-sm text-base-content/70 mb-4">Click on any field to edit inline (within 24 hours).</p>
              </div>
              <div id="metrics-list-container" class="flex-1 overflow-y-auto"></div>
            </div>
          </div>
        </div>
  
        <!-- Modal -->
        <dialog id="metric-form-modal" class="modal">
          <div class="modal-box max-w-2xl">
            <form method="dialog">
              <button class="btn btn-sm btn-circle btn-ghost absolute right-2 top-2">✕</button>
            </form>
            <h3 class="font-bold text-lg mb-4">Add Body Measurement</h3>
            <div id="metrics-form-container"></div>
          </div>
          <form method="dialog" class="modal-backdrop"><button>close</button></form>
        </dialog>`;
    }
  
    _tick() { return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }
  }
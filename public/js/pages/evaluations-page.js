/**
 * EvaluationsPage
 * Thin wrapper — implement detail as needed.
 */

class EvaluationsPage {
    async init(params, query) {
      window.renderPage(`
        <div class="p-6">
          <h1 class="text-4xl font-bold mb-6">🏅 Evaluations</h1>
          <div id="evaluations-container">
            <div class="flex justify-center items-center py-8">
              <span class="loading loading-spinner loading-lg"></span>
            </div>
          </div>
        </div>`);
      await this._tick();
      // Mount your existing evaluations component here when ready
    }
  
    destroy() {}
    _tick() { return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }
  }
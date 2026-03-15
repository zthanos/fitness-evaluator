/**
 * TrainingPlansPage
 * Equivalent to training-plans.html + its inline <script>.
 */

class TrainingPlansPage {
    constructor() { this._list = null; }
  
    async init(params, query) {
      window.renderPage(this._html());
      await this._tick();
  
      this._list = new TrainingPlansList('plans-container', {
        onPlanClick: (planId) => router.navigate(`/training-plans/${planId}`),
      });
      await this._list.init();
    }
  
    destroy() {}
  
    _html() {
      return `
        <div class="p-6">
          <div class="flex justify-between items-center mb-6">
            <h1 class="text-4xl font-bold">🎯 Training Plans</h1>
          </div>
          <div id="plans-container">
            <div class="flex justify-center items-center py-8">
              <span class="loading loading-spinner loading-lg"></span>
            </div>
          </div>
        </div>`;
    }
  
    _tick() { return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }
  }
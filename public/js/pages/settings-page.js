/**
 * SettingsPage (SPA wrapper)
 * The existing settings.js class is named SettingsPage too — we rename the
 * wrapper to avoid a clash. app.js routes to SettingsPageWrapper which in turn
 * creates the settings.js SettingsPage instance.
 *
 * NOTE: if you rename the class in settings.js to SettingsManager (recommended),
 * you can simplify this and use SettingsPage directly.
 */

class SettingsPageWrapper {
    constructor() { this._settings = null; }
  
    async init(params, query) {
      window.renderPage(this._html());
      await this._tick();
  
      // Instantiate the existing SettingsPage from settings.js
      // (rename it to SettingsManager in settings.js to avoid ambiguity)
      if (typeof SettingsManager !== 'undefined') {
        this._settings = new SettingsManager();
      } else if (typeof SettingsPage !== 'undefined') {
        this._settings = new SettingsPage();
      }
      await this._settings?.init();
    }
  
    destroy() {}
  
    _html() {
      // Identical markup to settings.html <main> content
      return `
        <div class="p-6 overflow-y-auto">
          <div class="mb-6">
            <h1 class="text-4xl font-bold">⚙️ Settings</h1>
            <p class="text-base-content/70 mt-2">Manage your profile, goals, and integrations</p>
          </div>
  
          <div class="card bg-base-100 shadow-xl mb-6">
            <div class="card-body">
              <div class="flex justify-between items-center mb-4">
                <h2 class="card-title">🎯 Goals</h2>
                <button id="set-goal-btn" class="btn btn-primary gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
                  </svg>
                  Set New Goal with Coach
                </button>
              </div>
              <div id="active-goals-container"></div>
              <div class="divider"></div>
              <div class="collapse collapse-arrow bg-base-200">
                <input type="checkbox" id="goal-history-toggle" />
                <div class="collapse-title text-lg font-medium">Goal History</div>
                <div class="collapse-content"><div id="goal-history-container"></div></div>
              </div>
            </div>
          </div>
  
          <div class="card bg-base-100 shadow-xl mb-6">
            <div class="card-body">
              <h2 class="card-title mb-4">👤 Profile</h2>
              <form id="profile-form" class="space-y-4">
                <div class="form-control">
                  <label class="label"><span class="label-text">Name</span></label>
                  <input type="text" id="profile-name" placeholder="Your name" class="input input-bordered" required />
                </div>
                <div class="form-control">
                  <label class="label"><span class="label-text">Email</span></label>
                  <input type="email" id="profile-email" placeholder="your.email@example.com" class="input input-bordered" />
                </div>
                <div class="form-control">
                  <label class="label"><span class="label-text">Date of Birth</span></label>
                  <input type="date" id="profile-dob" class="input input-bordered" />
                </div>
                <div class="flex justify-end">
                  <button type="submit" class="btn btn-primary">Save Profile</button>
                </div>
              </form>
            </div>
          </div>
  
          <div class="card bg-base-100 shadow-xl mb-6">
            <div class="card-body">
              <h2 class="card-title mb-4">📋 Training Plan</h2>
              <form id="training-plan-form" class="space-y-4">
                <div class="form-control">
                  <label class="label"><span class="label-text">Plan Name</span></label>
                  <input type="text" id="plan-name" placeholder="e.g., Marathon Training" class="input input-bordered" />
                </div>
                <div class="form-control">
                  <label class="label"><span class="label-text">Start Date</span></label>
                  <input type="date" id="plan-start-date" class="input input-bordered" />
                </div>
                <div class="form-control">
                  <label class="label"><span class="label-text">Goal Description</span></label>
                  <textarea id="plan-goal-description" placeholder="Describe your training goals..." class="textarea textarea-bordered h-24"></textarea>
                </div>
                <div class="flex justify-end">
                  <button type="submit" class="btn btn-primary">Save Training Plan</button>
                </div>
              </form>
            </div>
          </div>
  
          <div class="card bg-base-100 shadow-xl mb-6">
            <div class="card-body">
              <h2 class="card-title mb-4">🏃 Strava Integration</h2>
              <div id="strava-status-container"></div>
            </div>
          </div>
  
          <div class="card bg-base-100 shadow-xl mb-6">
            <div class="card-body">
              <h2 class="card-title mb-4">🤖 AI Coach Settings</h2>
              <form id="llm-form" class="space-y-4">
                <div class="alert alert-info">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="stroke-current shrink-0 w-6 h-6">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  </svg>
                  <div><div class="font-bold">LLM Configuration</div>
                  <div class="text-sm">Configure your AI backend (Ollama or LM Studio).</div></div>
                </div>
                <div class="form-control">
                  <label class="label"><span class="label-text">LLM Type</span></label>
                  <select id="llm-type" class="select select-bordered">
                    <option value="ollama">Ollama</option>
                    <option value="lm-studio">LM Studio</option>
                  </select>
                </div>
                <div class="form-control">
                  <label class="label"><span class="label-text">Endpoint URL</span></label>
                  <select id="llm-endpoint-preset" class="select select-bordered mb-2">
                    <option value="custom">Custom</option>
                    <option value="http://localhost:11434">Ollama Local</option>
                    <option value="http://ollama:11434">Ollama Docker</option>
                    <option value="http://localhost:1234">LM Studio</option>
                  </select>
                  <input type="text" id="llm-endpoint" placeholder="http://localhost:11434" class="input input-bordered" />
                </div>
                <div class="form-control">
                  <label class="label"><span class="label-text">Model Name</span></label>
                  <input type="text" id="llm-model" placeholder="mistral" class="input input-bordered" />
                </div>
                <div class="form-control">
                  <label class="label">
                    <span class="label-text">Temperature</span>
                    <span class="label-text-alt" id="temperature-value">0.7</span>
                  </label>
                  <input type="range" id="llm-temperature" min="0" max="1" step="0.1" value="0.7" class="range range-primary" />
                </div>
                <div class="flex gap-2">
                  <button type="button" id="test-llm-btn" class="btn btn-outline">Test Connection</button>
                  <button type="submit" class="btn btn-primary">Save Settings</button>
                </div>
                <div id="llm-status" class="hidden"></div>
              </form>
            </div>
          </div>
  
          <div class="card bg-base-100 shadow-xl mb-6">
            <div class="card-body">
              <h2 class="card-title mb-4">📦 Data Export</h2>
              <p class="text-base-content/70 mb-4">Export all your data including activities, metrics, logs, evaluations, and chat sessions.</p>
              <button id="export-data-btn" class="btn btn-outline gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                </svg>
                Export Data
              </button>
            </div>
          </div>
        </div>`;
    }
  
    _tick() { return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }
  }
  
  // Alias so app.js can use the class name consistently
  const SettingsPage = SettingsPageWrapper;
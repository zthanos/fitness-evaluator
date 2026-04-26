/**
 * app-settings.js — Application-level settings page
 * Handles LLM configuration, timeout display, and data export.
 */

class AppSettingsManager {
    async init() {
        await this.loadLLMSettings();
        await this.loadAppConfig();
        this.setupEventListeners();
    }

    async loadLLMSettings() {
        try {
            const settings = await api.get('/settings/llm');
            const llmType = settings.llm_type || 'ollama';

            document.getElementById('llm-cur-type').textContent = llmType;
            document.getElementById('llm-cur-model').textContent = settings.model || '—';
            document.getElementById('llm-cur-endpoint').textContent = settings.endpoint || '—';

            document.getElementById('llm-type').value = llmType;
            document.getElementById('llm-model').value = settings.model || '';
            document.getElementById('llm-endpoint').value = settings.endpoint || '';
            document.getElementById('llm-temperature').value = settings.temperature ?? 0.7;
            document.getElementById('temperature-value').textContent = settings.temperature ?? 0.7;

            const preset = document.getElementById('llm-endpoint-preset');
            const knownPresets = Array.from(preset.options).map(o => o.value);
            preset.value = knownPresets.includes(settings.endpoint) ? settings.endpoint : 'custom';
        } catch (err) {
            console.error('Error loading LLM settings:', err);
        }
    }

    async loadAppConfig() {
        const container = document.getElementById('app-config-table');
        try {
            const cfg = await api.get('/settings/app');
            const rows = [
                ['Strava API timeout', `${cfg.strava_api_timeout_s} s`, 'app/services/strava_client.py'],
                ['Embedding timeout', `${cfg.embedding_timeout_s} s`, '.env → EMBEDDING_TIMEOUT'],
                ['Keycloak URL', cfg.keycloak_url, '.env → KEYCLOAK_URL'],
                ['Keycloak Realm', cfg.keycloak_realm, '.env → KEYCLOAK_REALM'],
                ['Environment', cfg.environment, '.env → ENVIRONMENT'],
                ['Log level', cfg.log_level, '.env → LOG_LEVEL'],
            ];
            container.innerHTML = `
                <div class="overflow-x-auto">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Setting</th>
                                <th>Current value</th>
                                <th class="hidden sm:table-cell text-base-content/50">Source</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows.map(([k, v, src]) => `
                            <tr>
                                <td class="font-medium">${k}</td>
                                <td class="font-mono text-sm">${v}</td>
                                <td class="hidden sm:table-cell text-xs text-base-content/50">${src}</td>
                            </tr>`).join('')}
                        </tbody>
                    </table>
                </div>`;
        } catch (err) {
            container.innerHTML = `<div class="alert alert-error text-sm">Failed to load app config: ${err.message}</div>`;
        }
    }

    setupEventListeners() {
        // Preset selector syncs endpoint input
        const preset = document.getElementById('llm-endpoint-preset');
        const endpoint = document.getElementById('llm-endpoint');
        if (preset && endpoint) {
            preset.addEventListener('change', e => {
                if (e.target.value !== 'custom') endpoint.value = e.target.value;
            });
            endpoint.addEventListener('input', () => { preset.value = 'custom'; });
        }

        // Temperature slider label
        const slider = document.getElementById('llm-temperature');
        const label  = document.getElementById('temperature-value');
        if (slider && label) {
            slider.addEventListener('input', e => { label.textContent = e.target.value; });
        }

        // LLM form — shows .env snippet
        document.getElementById('llm-form')?.addEventListener('submit', e => {
            e.preventDefault();
            this.showEnvSnippet();
        });

        // Test connection
        document.getElementById('test-llm-btn')?.addEventListener('click', () => this.testLLMConnection());

        // Export
        document.getElementById('export-data-btn')?.addEventListener('click', () => {
            window.showToast('Data export coming soon', 'info');
        });
    }

    showEnvSnippet() {
        const type     = document.getElementById('llm-type').value;
        const endpoint = document.getElementById('llm-endpoint').value;
        const model    = document.getElementById('llm-model').value;
        const temp     = document.getElementById('llm-temperature').value;

        const snippet = type === 'lm-studio'
            ? `LLM_TYPE=lm-studio\nLM_STUDIO_ENDPOINT=${endpoint}\nLM_STUDIO_MODEL=${model}`
            : `LLM_TYPE=ollama\nOLLAMA_ENDPOINT=${endpoint}\nOLLAMA_MODEL=${model}`;

        const status = document.getElementById('llm-status');
        status.className = 'alert alert-warning';
        status.innerHTML = `
            <div>
                <div class="font-bold">Update .env and restart the server</div>
                <pre class="text-xs mt-2 bg-base-200 p-3 rounded whitespace-pre-wrap">${snippet}</pre>
            </div>`;
        status.classList.remove('hidden');
    }

    async testLLMConnection() {
        const btn    = document.getElementById('test-llm-btn');
        const status = document.getElementById('llm-status');
        const orig   = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span class="loading loading-spinner loading-sm"></span> Testing…`;
        status.classList.add('hidden');

        try {
            const token = window.getAuthToken?.();
            const resp = await fetch(`${api.baseUrl}/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({ content: 'Hello', session_id: null }),
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const reader = resp.body.getReader();
            const { done, value } = await reader.read();
            reader.cancel();
            if (!done && value) {
                status.className = 'alert alert-success';
                status.innerHTML = `<span>✅ LLM connection successful — AI coach is ready.</span>`;
            } else {
                throw new Error('No response from LLM');
            }
        } catch (err) {
            status.className = 'alert alert-error';
            status.innerHTML = `
                <div>
                    <div class="font-bold">Connection failed</div>
                    <div class="text-sm">Make sure Ollama/LM Studio is running. Error: ${err.message}</div>
                </div>`;
        } finally {
            status.classList.remove('hidden');
            btn.disabled = false;
            btn.innerHTML = orig;
        }
    }
}

export { AppSettingsManager };

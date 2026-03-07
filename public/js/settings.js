/**
 * Settings Page Component
 * Manages profile, goals, Strava integration, LLM settings, and data export
 */

class SettingsPage {
    constructor() {
        this.activeGoals = [];
        this.goalHistory = [];
    }

    async init() {
        await this.loadProfile();
        await this.loadTrainingPlan();
        await this.loadGoals();
        await this.loadLLMSettings();
        this.renderActiveGoals();
        this.renderGoalHistory();
        this.renderStravaStatus();
        this.setupEventListeners();
    }

    async loadProfile() {
        try {
            const profile = await api.get('/settings/profile');
            
            // Populate profile form
            document.getElementById('profile-name').value = profile.name || '';
            document.getElementById('profile-email').value = profile.email || '';
            document.getElementById('profile-dob').value = profile.date_of_birth || '';
            
            // Store profile for training plan form
            this.currentProfile = profile;
        } catch (error) {
            console.error('Error loading profile:', error);
        }
    }

    async loadTrainingPlan() {
        try {
            const profile = await api.get('/settings/profile');
            
            // Parse training plan from current_plan field
            if (profile.current_plan) {
                // Extract plan name and start date from format "Plan Name (started YYYY-MM-DD)"
                const match = profile.current_plan.match(/^(.+?)(?: \(started (.+?)\))?$/);
                if (match) {
                    document.getElementById('plan-name').value = match[1] || '';
                    document.getElementById('plan-start-date').value = match[2] || '';
                }
            }
            
            // Set goal description
            document.getElementById('plan-goal-description').value = profile.goals || '';
        } catch (error) {
            console.error('Error loading training plan:', error);
        }
    }

    async loadGoals() {
        try {
            // Load all goals
            const response = await api.get('/goals');
            
            // Separate active and historical goals
            this.activeGoals = response.filter(goal => goal.status === 'active');
            this.goalHistory = response.filter(goal => goal.status !== 'active');
        } catch (error) {
            console.error('Error loading goals:', error);
            this.activeGoals = [];
            this.goalHistory = [];
        }
    }

    renderActiveGoals() {
        const container = document.getElementById('active-goals-container');
        
        if (this.activeGoals.length === 0) {
            container.innerHTML = `
                <div class="alert">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="stroke-info shrink-0 w-6 h-6">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <span>No active goals yet. Click "Set New Goal with Coach" to get started!</span>
                </div>
            `;
            return;
        }

        const goalsHTML = this.activeGoals.map(goal => this.renderGoalCard(goal)).join('');
        container.innerHTML = `<div class="space-y-4">${goalsHTML}</div>`;
    }

    renderGoalCard(goal) {
        const goalTypeEmoji = {
            'weight_loss': '⬇️',
            'weight_gain': '⬆️',
            'performance': '🏃',
            'endurance': '💪',
            'strength': '🏋️',
            'custom': '🎯'
        };

        const emoji = goalTypeEmoji[goal.goal_type] || '🎯';
        const goalTypeLabel = goal.goal_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
        
        const targetInfo = [];
        if (goal.target_value) {
            const unit = goal.goal_type.includes('weight') ? 'kg' : '';
            targetInfo.push(`Target: ${goal.target_value}${unit}`);
        }
        if (goal.target_date) {
            const date = new Date(goal.target_date);
            const daysRemaining = Math.ceil((date - new Date()) / (1000 * 60 * 60 * 24));
            targetInfo.push(`Due: ${date.toLocaleDateString()} (${daysRemaining} days)`);
        }

        const statusBadge = goal.status === 'active' 
            ? '<span class="badge badge-success">Active</span>'
            : goal.status === 'completed'
            ? '<span class="badge badge-info">Completed</span>'
            : '<span class="badge badge-warning">Abandoned</span>';

        return `
            <div class="card bg-base-200">
                <div class="card-body">
                    <div class="flex justify-between items-start">
                        <div class="flex-1">
                            <h3 class="card-title text-lg">
                                ${emoji} ${goalTypeLabel}
                                ${statusBadge}
                            </h3>
                            <p class="text-sm text-base-content/70 mt-2">${goal.description}</p>
                            ${targetInfo.length > 0 ? `
                                <div class="flex gap-4 mt-3 text-sm">
                                    ${targetInfo.map(info => `<span class="badge badge-outline">${info}</span>`).join('')}
                                </div>
                            ` : ''}
                        </div>
                        <div class="dropdown dropdown-end">
                            <label tabindex="0" class="btn btn-ghost btn-sm btn-circle">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                    <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
                                </svg>
                            </label>
                            <ul tabindex="0" class="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-52">
                                <li><a onclick="settingsPage.markGoalCompleted('${goal.id}')">✅ Mark as Completed</a></li>
                                <li><a onclick="settingsPage.markGoalAbandoned('${goal.id}')">❌ Mark as Abandoned</a></li>
                                <li><a onclick="settingsPage.deleteGoal('${goal.id}')" class="text-error">🗑️ Delete</a></li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    renderGoalHistory() {
        const container = document.getElementById('goal-history-container');
        
        if (this.goalHistory.length === 0) {
            container.innerHTML = `
                <div class="text-center text-base-content/50 py-4">
                    No goal history yet
                </div>
            `;
            return;
        }

        const historyHTML = this.goalHistory.map(goal => this.renderGoalCard(goal)).join('');
        container.innerHTML = `<div class="space-y-4">${historyHTML}</div>`;
    }

    renderStravaStatus() {
        const container = document.getElementById('strava-status-container');
        
        // Show loading state
        container.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="loading loading-spinner loading-sm"></span>
                <span>Checking Strava connection...</span>
            </div>
        `;
        
        // Load Strava status
        this.loadStravaStatus(container);
    }
    
    async loadStravaStatus(container) {
        try {
            const status = await api.get('/auth/strava/status');
            
            if (status.connected) {
                // Connected state
                const expiresAt = new Date(status.expires_at);
                const now = new Date();
                const hoursUntilExpiry = Math.floor((expiresAt - now) / (1000 * 60 * 60));
                
                container.innerHTML = `
                    <div class="alert alert-success">
                        <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <div class="flex-1">
                            <div class="font-bold">✅ Strava Connected</div>
                            <div class="text-sm">Your Strava account is connected and syncing activities.</div>
                            <div class="text-xs mt-1 opacity-70">Token expires in ${hoursUntilExpiry} hours</div>
                        </div>
                    </div>
                    <div class="mt-4">
                        <button id="disconnect-strava-btn" class="btn btn-outline btn-error gap-2">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M3 3a1 1 0 00-1 1v12a1 1 0 102 0V4a1 1 0 00-1-1zm10.293 9.293a1 1 0 001.414 1.414l3-3a1 1 0 000-1.414l-3-3a1 1 0 10-1.414 1.414L14.586 9H7a1 1 0 100 2h7.586l-1.293 1.293z" clip-rule="evenodd" />
                            </svg>
                            Disconnect Strava
                        </button>
                    </div>
                `;
                
                // Add disconnect handler
                document.getElementById('disconnect-strava-btn').addEventListener('click', async () => {
                    await this.disconnectStrava(container);
                });
            } else {
                // Not connected state
                container.innerHTML = `
                    <div class="alert alert-warning">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="stroke-current shrink-0 w-6 h-6">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        <div class="flex-1">
                            <div class="font-bold">Strava Not Connected</div>
                            <div class="text-sm">Connect your Strava account to automatically sync your activities.</div>
                        </div>
                    </div>
                    <div class="mt-4">
                        <button id="connect-strava-btn" class="btn btn-primary gap-2">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v2H7a1 1 0 100 2h2v2a1 1 0 102 0v-2h2a1 1 0 100-2h-2V7z" clip-rule="evenodd" />
                            </svg>
                            Connect Strava Account
                        </button>
                    </div>
                `;
                
                // Add connect handler
                document.getElementById('connect-strava-btn').addEventListener('click', async () => {
                    await this.connectStrava();
                });
            }
            
            // Check for connection success/error in URL
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('strava_connected') === 'true') {
                this.showToast('Strava connected successfully! 🎉', 'success');
                // Clean up URL
                window.history.replaceState({}, document.title, window.location.pathname);
            } else if (urlParams.get('strava_error')) {
                this.showToast(`Strava connection failed: ${urlParams.get('strava_error')}`, 'error');
                // Clean up URL
                window.history.replaceState({}, document.title, window.location.pathname);
            }
            
        } catch (error) {
            console.error('Error loading Strava status:', error);
            container.innerHTML = `
                <div class="alert alert-error">
                    <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>Failed to load Strava status</span>
                </div>
            `;
        }
    }
    
    async connectStrava() {
        try {
            // Get authorization URL from API
            const response = await api.get('/auth/strava?athlete_id=1');
            
            // Redirect to Strava authorization page
            window.location.href = response.authorization_url;
        } catch (error) {
            console.error('Error connecting Strava:', error);
            this.showToast('Failed to initiate Strava connection', 'error');
        }
    }
    
    async disconnectStrava(container) {
        if (!confirm('Are you sure you want to disconnect your Strava account? Your synced activities will remain, but no new activities will be synced.')) {
            return;
        }
        
        try {
            await api.post('/auth/strava/disconnect?athlete_id=1');
            this.showToast('Strava disconnected successfully', 'success');
            
            // Reload status
            await this.loadStravaStatus(container);
        } catch (error) {
            console.error('Error disconnecting Strava:', error);
            this.showToast('Failed to disconnect Strava', 'error');
        }
    }

    setupEventListeners() {
        // Set New Goal button
        const setGoalBtn = document.getElementById('set-goal-btn');
        if (setGoalBtn) {
            setGoalBtn.addEventListener('click', () => {
                // Navigate to chat page
                window.location.href = '/chat.html';
            });
        }

        // LLM endpoint preset selector
        const endpointPreset = document.getElementById('llm-endpoint-preset');
        const endpointInput = document.getElementById('llm-endpoint');
        if (endpointPreset && endpointInput) {
            endpointPreset.addEventListener('change', (e) => {
                if (e.target.value !== 'custom') {
                    endpointInput.value = e.target.value;
                }
            });
            
            endpointInput.addEventListener('input', () => {
                // Set to custom when user types
                endpointPreset.value = 'custom';
            });
        }

        // Temperature slider
        const temperatureSlider = document.getElementById('llm-temperature');
        const temperatureValue = document.getElementById('temperature-value');
        if (temperatureSlider && temperatureValue) {
            temperatureSlider.addEventListener('input', (e) => {
                temperatureValue.textContent = e.target.value;
            });
        }

        // LLM form submission
        const llmForm = document.getElementById('llm-form');
        if (llmForm) {
            llmForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.saveLLMSettings();
            });
        }

        // Test LLM connection
        const testLLMBtn = document.getElementById('test-llm-btn');
        if (testLLMBtn) {
            testLLMBtn.addEventListener('click', async () => {
                await this.testLLMConnection();
            });
        }

        // Export data button
        const exportBtn = document.getElementById('export-data-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', async () => {
                try {
                    exportBtn.disabled = true;
                    exportBtn.innerHTML = `
                        <span class="loading loading-spinner loading-sm"></span>
                        Exporting...
                    `;
                    
                    // Will be implemented in Task 23
                    alert('Data export will be available soon');
                    
                } catch (error) {
                    console.error('Error exporting data:', error);
                    alert('Failed to export data. Please try again.');
                } finally {
                    exportBtn.disabled = false;
                    exportBtn.innerHTML = `
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                            <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                        </svg>
                        Export Data
                    `;
                }
            });
        }

        // Profile form
        const profileForm = document.getElementById('profile-form');
        if (profileForm) {
            profileForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.saveProfile();
            });
        }

        // Training plan form
        const trainingPlanForm = document.getElementById('training-plan-form');
        if (trainingPlanForm) {
            trainingPlanForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.saveTrainingPlan();
            });
        }
    }

    async markGoalCompleted(goalId) {
        if (!confirm('Mark this goal as completed?')) return;
        
        try {
            await api.put(`/goals/${goalId}`, { status: 'completed' });
            await this.loadGoals();
            this.renderActiveGoals();
            this.renderGoalHistory();
            
            // Show success message
            this.showToast('Goal marked as completed! 🎉', 'success');
        } catch (error) {
            console.error('Error updating goal:', error);
            this.showToast('Failed to update goal', 'error');
        }
    }

    async markGoalAbandoned(goalId) {
        if (!confirm('Mark this goal as abandoned?')) return;
        
        try {
            await api.put(`/goals/${goalId}`, { status: 'abandoned' });
            await this.loadGoals();
            this.renderActiveGoals();
            this.renderGoalHistory();
            
            this.showToast('Goal marked as abandoned', 'info');
        } catch (error) {
            console.error('Error updating goal:', error);
            this.showToast('Failed to update goal', 'error');
        }
    }

    async deleteGoal(goalId) {
        if (!confirm('Are you sure you want to delete this goal? This action cannot be undone.')) return;
        
        try {
            await api.delete(`/goals/${goalId}`);
            await this.loadGoals();
            this.renderActiveGoals();
            this.renderGoalHistory();
            
            this.showToast('Goal deleted', 'info');
        } catch (error) {
            console.error('Error deleting goal:', error);
            this.showToast('Failed to delete goal', 'error');
        }
    }

    showToast(message, type = 'info') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} fixed bottom-4 right-4 w-auto max-w-sm z-50 shadow-lg`;
        toast.innerHTML = `
            <span>${message}</span>
        `;
        
        document.body.appendChild(toast);
        
        // Remove after 3 seconds
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    async loadLLMSettings() {
        try {
            // Load from API
            const settings = await api.get('/settings/llm');
            
            document.getElementById('llm-type').value = settings.llm_type || 'ollama';
            document.getElementById('llm-endpoint').value = settings.endpoint || 'http://localhost:11434';
            document.getElementById('llm-model').value = settings.model || 'mistral';
            document.getElementById('llm-temperature').value = settings.temperature || 0.7;
            document.getElementById('temperature-value').textContent = settings.temperature || 0.7;
            
            // Set preset if it matches
            const presetSelect = document.getElementById('llm-endpoint-preset');
            const endpoint = settings.endpoint || 'http://localhost:11434';
            const presetOptions = Array.from(presetSelect.options).map(opt => opt.value);
            if (presetOptions.includes(endpoint)) {
                presetSelect.value = endpoint;
            } else {
                presetSelect.value = 'custom';
            }
        } catch (error) {
            console.error('Error loading LLM settings:', error);
        }
    }

    async saveProfile() {
        try {
            const profileData = {
                name: document.getElementById('profile-name').value,
                email: document.getElementById('profile-email').value || null,
                date_of_birth: document.getElementById('profile-dob').value || null
            };
            
            // Validate date of birth if provided
            if (profileData.date_of_birth) {
                const dob = new Date(profileData.date_of_birth);
                const today = new Date();
                const minDate = new Date('1900-01-01');
                
                if (dob < minDate || dob > today) {
                    this.showToast('Date of birth must be between 1900 and today', 'error');
                    return;
                }
            }
            
            await api.put('/settings/profile', profileData);
            this.showToast('Profile updated successfully!', 'success');
        } catch (error) {
            console.error('Error saving profile:', error);
            
            // Show specific error message if available
            const errorMessage = error.detail || 'Failed to save profile. Please try again.';
            this.showToast(errorMessage, 'error');
        }
    }

    async saveTrainingPlan() {
        try {
            const planData = {
                plan_name: document.getElementById('plan-name').value || null,
                start_date: document.getElementById('plan-start-date').value || null,
                goal_description: document.getElementById('plan-goal-description').value || null
            };
            
            await api.put('/settings/training-plan', planData);
            this.showToast('Training plan updated successfully!', 'success');
        } catch (error) {
            console.error('Error saving training plan:', error);
            
            const errorMessage = error.detail || 'Failed to save training plan. Please try again.';
            this.showToast(errorMessage, 'error');
        }
    }

    async saveLLMSettings() {
        try {
            const settings = {
                type: document.getElementById('llm-type').value,
                endpoint: document.getElementById('llm-endpoint').value,
                model: document.getElementById('llm-model').value,
                temperature: parseFloat(document.getElementById('llm-temperature').value)
            };
            
            // Validate endpoint URL
            try {
                new URL(settings.endpoint);
            } catch (e) {
                this.showToast('Invalid endpoint URL', 'error');
                return;
            }
            
            // Save to localStorage for now
            localStorage.setItem('llmSettings', JSON.stringify(settings));
            
            this.showToast('LLM settings saved! Please restart the server for changes to take effect.', 'success');
            
            // Show instructions
            const statusDiv = document.getElementById('llm-status');
            statusDiv.className = 'alert alert-warning';
            statusDiv.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="stroke-current shrink-0 w-6 h-6">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <div>
                    <div class="font-bold">Server Restart Required</div>
                    <div class="text-sm">Update your .env file with these settings and restart the FastAPI server:</div>
                    <pre class="text-xs mt-2 bg-base-200 p-2 rounded">LLM_TYPE=${settings.type}
OLLAMA_ENDPOINT=${settings.endpoint}
OLLAMA_MODEL=${settings.model}</pre>
                </div>
            `;
            statusDiv.classList.remove('hidden');
            
        } catch (error) {
            console.error('Error saving LLM settings:', error);
            this.showToast('Failed to save settings', 'error');
        }
    }

    async testLLMConnection() {
        const testBtn = document.getElementById('test-llm-btn');
        const statusDiv = document.getElementById('llm-status');
        
        try {
            testBtn.disabled = true;
            testBtn.innerHTML = `
                <span class="loading loading-spinner loading-sm"></span>
                Testing...
            `;
            
            // Try to send a test message
            const response = await fetch(`${api.baseUrl}/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content: 'Hello',
                    session_id: null
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            // Read first chunk to verify connection
            const reader = response.body.getReader();
            const { done, value } = await reader.read();
            reader.cancel(); // Cancel the rest
            
            if (!done && value) {
                statusDiv.className = 'alert alert-success';
                statusDiv.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>✅ LLM connection successful! The AI coach is ready.</span>
                `;
                statusDiv.classList.remove('hidden');
                this.showToast('LLM connection successful!', 'success');
            } else {
                throw new Error('No response from LLM');
            }
            
        } catch (error) {
            console.error('LLM connection test failed:', error);
            statusDiv.className = 'alert alert-error';
            statusDiv.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                    <div class="font-bold">❌ Connection Failed</div>
                    <div class="text-sm">Cannot connect to LLM server. Make sure Ollama/LM Studio is running.</div>
                    <div class="text-xs mt-1">Error: ${error.message}</div>
                </div>
            `;
            statusDiv.classList.remove('hidden');
            this.showToast('LLM connection failed', 'error');
        } finally {
            testBtn.disabled = false;
            testBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                </svg>
                Test Connection
            `;
        }
    }
}

// Global instance for onclick handlers
let settingsPage;

// Note: DOMContentLoaded handler is in settings.html, not here
// The global settingsPage variable is set there

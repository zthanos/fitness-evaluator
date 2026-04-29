/**
 * Settings Page Component
 * Manages profile, goals, Strava integration, LLM settings, and data export
 */

class SettingsManager {
    constructor() {
        this.activeGoals = [];
        this.goalHistory = [];
    }

    async init() {
        await this.loadProfile();
        await this.loadTrainingPlan();
        await this.loadGoals();
        this.renderActiveGoals();
        this.renderGoalHistory();
        this.renderStravaStatus();
        this.setupEventListeners();
        await this.loadSportProfiles();
    }

    async loadProfile() {
        try {
            const profile = await api.get('/settings/profile');

            document.getElementById('profile-name').value = profile.name || '';
            document.getElementById('profile-email').value = profile.email || '';
            document.getElementById('profile-dob').value = profile.date_of_birth || '';
            document.getElementById('profile-height').value = profile.height_cm || '';

            this._renderAvatar(profile.avatar_url, profile.name);
            this.currentProfile = profile;
        } catch (error) {
            console.error('Error loading profile:', error);
        }
    }

    _renderAvatar(url, name) {
        const img = document.getElementById('avatar-img');
        const initials = document.getElementById('avatar-initials');
        if (url) {
            img.src = url + '?t=' + Date.now();  // cache-bust after upload
            img.classList.remove('hidden');
            initials.classList.add('hidden');
        } else {
            img.classList.add('hidden');
            initials.classList.remove('hidden');
            initials.textContent = (name || '?').charAt(0).toUpperCase();
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
            const response = await api.get('/auth/strava');
            
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
            await api.post('/auth/strava/disconnect');
            this.showToast('Strava disconnected successfully', 'success');
            
            // Reload status
            await this.loadStravaStatus(container);
        } catch (error) {
            console.error('Error disconnecting Strava:', error);
            this.showToast('Failed to disconnect Strava', 'error');
        }
    }

    async loadSportProfiles() {
        const container = document.getElementById('sport-profiles-container');
        if (!container) return;
        try {
            const data = await api.get('/settings/sport-profiles');
            this._renderSportProfiles(data.profiles || []);
        } catch {
            container.innerHTML = '<p class="text-base-content/60 text-sm">Could not load sport profiles.</p>';
        }
    }

    async rebuildSportProfiles() {
        const btn = document.getElementById('rebuild-profiles-btn');
        const container = document.getElementById('sport-profiles-container');
        if (btn) { btn.disabled = true; btn.textContent = 'Updating…'; }
        container.innerHTML = '<div class="flex justify-center py-6"><span class="loading loading-spinner loading-md"></span></div>';
        try {
            const data = await api.post('/settings/sport-profiles/rebuild', {});
            this._renderSportProfiles(data.profiles || []);
            this.showToast(`Sport profiles updated (${data.rebuilt} sport${data.rebuilt !== 1 ? 's' : ''})`, 'success');
        } catch (err) {
            container.innerHTML = '<p class="text-error text-sm">Failed to rebuild profiles. Make sure you have synced Strava activities.</p>';
            this.showToast('Profile update failed', 'error');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Update Profiles`;
            }
        }
    }

    _renderSportProfiles(profiles) {
        const container = document.getElementById('sport-profiles-container');
        if (!container) return;

        if (profiles.length === 0) {
            container.innerHTML = `
                <div class="alert">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" class="stroke-info shrink-0 w-6 h-6">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    <span>No profiles yet. Click <strong>Update Profiles</strong> to build them from your Strava history.</span>
                </div>`;
            return;
        }

        const sportMeta = {
            ride:     { label: 'Cycling',  icon: '🚴' },
            run:      { label: 'Running',  icon: '🏃' },
            swim:     { label: 'Swimming', icon: '🏊' },
            strength: { label: 'Strength', icon: '🏋️' },
        };

        const confidenceClass = (c) => {
            if (!c) return 'badge-ghost';
            if (c >= 0.7) return 'badge-success';
            if (c >= 0.4) return 'badge-warning';
            return 'badge-error';
        };
        const confidenceLabel = (c) => {
            if (!c) return 'No data';
            if (c >= 0.7) return 'High';
            if (c >= 0.4) return 'Medium';
            return 'Low';
        };
        const fmt = (v, unit = '', decimals = 1) =>
            v != null ? `${parseFloat(v).toFixed(decimals)}${unit}` : '—';

        container.innerHTML = `<div class="grid grid-cols-1 md:grid-cols-2 gap-4">${profiles.map(p => {
            const meta = sportMeta[p.sport_group] || { label: p.sport_group, icon: '🏅' };

            // Sport-specific key metrics
            let metrics = '';
            if (p.sport_group === 'ride') {
                metrics = `
                    ${p.ftp_estimate_w ? `<div class="stat p-0"><div class="stat-title text-xs">FTP</div><div class="stat-value text-lg">${Math.round(p.ftp_estimate_w)}W</div><div class="stat-desc">${p.ftp_confidence || ''} confidence</div></div>` : ''}
                    ${p.typical_cadence_rpm ? `<div class="stat p-0"><div class="stat-title text-xs">Cadence</div><div class="stat-value text-lg">${Math.round(p.typical_cadence_rpm)}</div><div class="stat-desc">rpm typical</div></div>` : ''}
                    ${p.typical_endurance_speed_kmh ? `<div class="stat p-0"><div class="stat-title text-xs">Speed</div><div class="stat-value text-lg">${fmt(p.typical_endurance_speed_kmh)}</div><div class="stat-desc">km/h typical</div></div>` : ''}
                    ${p.weekly_volume_km ? `<div class="stat p-0"><div class="stat-title text-xs">Weekly Vol.</div><div class="stat-value text-lg">${fmt(p.weekly_volume_km)}</div><div class="stat-desc">km / week</div></div>` : ''}`;
            } else if (p.sport_group === 'run') {
                metrics = `
                    ${p.best_60min_distance_km ? `<div class="stat p-0"><div class="stat-title text-xs">60-min Best</div><div class="stat-value text-lg">${fmt(p.best_60min_distance_km)}</div><div class="stat-desc">km</div></div>` : ''}
                    ${p.typical_endurance_speed_kmh ? `<div class="stat p-0"><div class="stat-title text-xs">Pace</div><div class="stat-value text-lg">${fmt(60 / p.typical_endurance_speed_kmh, '', 1)}</div><div class="stat-desc">min/km typical</div></div>` : ''}
                    ${p.weekly_volume_km ? `<div class="stat p-0"><div class="stat-title text-xs">Weekly Vol.</div><div class="stat-value text-lg">${fmt(p.weekly_volume_km)}</div><div class="stat-desc">km / week</div></div>` : ''}`;
            } else {
                metrics = `
                    ${p.weekly_training_time_min ? `<div class="stat p-0"><div class="stat-title text-xs">Weekly Time</div><div class="stat-value text-lg">${Math.round(p.weekly_training_time_min)}</div><div class="stat-desc">min / week</div></div>` : ''}
                    ${p.longest_distance_km ? `<div class="stat p-0"><div class="stat-title text-xs">Longest</div><div class="stat-value text-lg">${fmt(p.longest_distance_km)}</div><div class="stat-desc">km</div></div>` : ''}`;
            }

            const hrLine = p.max_hr_estimate
                ? `<div class="text-xs text-base-content/60 mt-1">Max HR: <span class="font-medium text-base-content">${p.max_hr_estimate} bpm</span></div>`
                : '';

            const strengths = (p.current_strengths || []).map(s =>
                `<span class="badge badge-success badge-sm gap-1">${s}</span>`).join('');
            const limiters = (p.current_limiters || []).map(l =>
                `<span class="badge badge-warning badge-sm gap-1">${l}</span>`).join('');

            const updatedAt = p.last_updated_at
                ? new Date(p.last_updated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                : null;

            return `
                <div class="card bg-base-200 border border-base-300">
                    <div class="card-body p-4">
                        <div class="flex items-center justify-between mb-3">
                            <h3 class="font-bold text-base flex items-center gap-2">
                                <span class="text-xl">${meta.icon}</span> ${meta.label}
                            </h3>
                            <span class="badge ${confidenceClass(p.profile_confidence)}">${confidenceLabel(p.profile_confidence)} confidence</span>
                        </div>
                        ${p.summary_text ? `<p class="text-xs text-base-content/70 mb-3 italic">"${p.summary_text}"</p>` : ''}
                        <div class="stats stats-horizontal bg-transparent flex flex-wrap gap-x-4 gap-y-2 mb-3">
                            ${metrics}
                        </div>
                        ${hrLine}
                        ${strengths ? `<div class="flex flex-wrap gap-1 mt-2">${strengths}</div>` : ''}
                        ${limiters ? `<div class="flex flex-wrap gap-1 mt-1">${limiters}</div>` : ''}
                        ${updatedAt ? `<div class="text-[10px] text-base-content/40 mt-3">Updated ${updatedAt}</div>` : ''}
                    </div>
                </div>`;
        }).join('')}</div>`;
    }

    setupEventListeners() {
        document.getElementById('set-goal-btn')?.addEventListener('click', () => {
            router.navigate('/chat');
        });

        document.getElementById('profile-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveProfile();
        });

        document.getElementById('training-plan-form')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.saveTrainingPlan();
        });

        document.getElementById('avatar-input')?.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (file) await this.uploadAvatar(file);
        });

        document.getElementById('rebuild-profiles-btn')?.addEventListener('click', () => {
            this.rebuildSportProfiles();
        });
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

    async saveProfile() {
        try {
            const heightVal = document.getElementById('profile-height').value;
            const profileData = {
                name: document.getElementById('profile-name').value,
                email: document.getElementById('profile-email').value || null,
                date_of_birth: document.getElementById('profile-dob').value || null,
                height_cm: heightVal ? parseInt(heightVal, 10) : null,
            };

            if (profileData.date_of_birth) {
                const dob = new Date(profileData.date_of_birth);
                if (dob < new Date('1900-01-01') || dob > new Date()) {
                    this.showToast('Date of birth must be between 1900 and today', 'error');
                    return;
                }
            }

            await api.put('/settings/profile', profileData);
            this.showToast('Profile updated successfully!', 'success');
        } catch (error) {
            console.error('Error saving profile:', error);
            this.showToast(error.detail || 'Failed to save profile. Please try again.', 'error');
        }
    }

    async uploadAvatar(file) {
        const statusEl = document.getElementById('avatar-upload-status');
        statusEl.textContent = 'Uploading…';
        statusEl.className = 'text-center text-xs mb-4 text-base-content/60';
        statusEl.classList.remove('hidden');

        try {
            const formData = new FormData();
            formData.append('file', file);

            const token = window.getAuthToken?.();
            const res = await fetch('/api/settings/profile/avatar', {
                method: 'POST',
                headers: token ? { Authorization: `Bearer ${token}` } : {},
                body: formData,
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Upload failed (${res.status})`);
            }

            const profile = await res.json();
            this._renderAvatar(profile.avatar_url, profile.name);
            statusEl.classList.add('hidden');
            this.showToast('Photo updated!', 'success');
        } catch (error) {
            statusEl.textContent = error.message;
            statusEl.className = 'text-center text-xs mb-4 text-error';
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

}

export { SettingsManager };
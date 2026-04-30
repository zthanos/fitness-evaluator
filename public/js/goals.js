class GoalsManager {
    constructor() {
        this.activeGoals  = [];
        this.goalHistory  = [];
    }

    async init() {
        await this._load();
        this._renderActive();
        this._renderHistory();
        this._initModal();
    }

    // ── Data ─────────────────────────────────────────────────────────────────

    async _load() {
        try {
            const response = await api.get('/goals');
            this.activeGoals = response.filter(g => g.status === 'active');
            this.goalHistory = response.filter(g => g.status !== 'active');
        } catch (err) {
            console.error('Error loading goals:', err);
            this.activeGoals = [];
            this.goalHistory = [];
        }
    }

    async _reload() {
        await this._load();
        this._renderActive();
        this._renderHistory();
    }

    // ── Render ───────────────────────────────────────────────────────────────

    _renderActive() {
        const el = document.getElementById('goals-active-container');
        if (!el) return;
        if (this.activeGoals.length === 0) {
            el.innerHTML = `
                <div class="card bg-base-100 shadow-sm">
                  <div class="card-body items-center text-center py-10 gap-3">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-10 h-10 text-base-content/20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z"/>
                    </svg>
                    <p class="text-base-content/50 text-sm">No active goals yet</p>
                    <button onclick="document.getElementById('new-goal-modal').showModal()" class="btn btn-sm btn-primary">Set your first goal</button>
                  </div>
                </div>`;
            return;
        }
        el.innerHTML = `<div class="space-y-3">${this.activeGoals.map(g => this._card(g)).join('')}</div>`;
    }

    _renderHistory() {
        const el = document.getElementById('goals-history-container');
        if (!el) return;
        if (this.goalHistory.length === 0) {
            el.innerHTML = `<p class="text-sm text-base-content/40 px-1">No completed or abandoned goals yet.</p>`;
            return;
        }
        el.innerHTML = `<div class="space-y-3">${this.goalHistory.map(g => this._card(g)).join('')}</div>`;
    }

    _card(goal) {
        const typeLabel = goal.goal_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const statusColors = { active: 'badge-success', completed: 'badge-info', abandoned: 'badge-warning' };
        const statusBadge = `<span class="badge badge-sm ${statusColors[goal.status] || 'badge-ghost'}">${goal.status}</span>`;

        const chips = [];
        if (goal.target_value) {
            const unit = goal.goal_type.includes('weight') ? ' kg' : '';
            chips.push(`Target: ${goal.target_value}${unit}`);
        }
        if (goal.target_date) {
            const d    = new Date(goal.target_date);
            const days = Math.ceil((d - new Date()) / 86400000);
            chips.push(days > 0 ? `${d.toLocaleDateString()} (${days}d)` : d.toLocaleDateString());
        }

        const actions = goal.status === 'active' ? `
            <div class="dropdown dropdown-end">
              <label tabindex="0" class="btn btn-ghost btn-xs btn-circle">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z"/>
                </svg>
              </label>
              <ul tabindex="0" class="dropdown-content z-[1] menu menu-sm p-2 shadow bg-base-100 rounded-box w-44">
                <li><a onclick="goalsPage.markCompleted('${goal.id}')">Mark completed</a></li>
                <li><a onclick="goalsPage.markAbandoned('${goal.id}')">Mark abandoned</a></li>
                <li><a onclick="goalsPage.deleteGoal('${goal.id}')" class="text-error">Delete</a></li>
              </ul>
            </div>` : `
            <button onclick="goalsPage.deleteGoal('${goal.id}')" class="btn btn-ghost btn-xs btn-circle text-error" title="Delete">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/>
              </svg>
            </button>`;

        return `
            <div class="card bg-base-100 shadow-sm">
              <div class="card-body p-4">
                <div class="flex items-start gap-3">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap mb-1">
                      <span class="font-semibold text-sm">${typeLabel}</span>
                      ${statusBadge}
                    </div>
                    <p class="text-sm text-base-content/70 leading-snug">${goal.description}</p>
                    ${chips.length ? `<div class="flex flex-wrap gap-2 mt-2">${chips.map(c => `<span class="badge badge-outline badge-sm">${c}</span>`).join('')}</div>` : ''}
                  </div>
                  ${actions}
                </div>
              </div>
            </div>`;
    }

    // ── Modal ────────────────────────────────────────────────────────────────

    _initModal() {
        document.getElementById('btn-new-goal')?.addEventListener('click', () => {
            this._resetForm();
            document.getElementById('new-goal-modal').showModal();
        });
        document.getElementById('btn-save-goal')?.addEventListener('click', () => this._saveGoal());

        // Toggle plan options visibility
        document.getElementById('goal-gen-plan')?.addEventListener('change', (e) => {
            document.getElementById('goal-plan-options')?.classList.toggle('hidden', !e.target.checked);
            if (e.target.checked) this._checkConflict();
        });

        // Re-check conflict when sport changes
        document.getElementById('goal-plan-sport')?.addEventListener('change', () => this._checkConflict());

        // Duration slider label
        document.getElementById('goal-plan-duration')?.addEventListener('input', (e) => {
            document.getElementById('goal-plan-duration-label').textContent = `${e.target.value} weeks`;
        });
    }

    _resetForm() {
        document.getElementById('new-goal-form')?.reset();
        const firstType = document.querySelector('input[name="goal-type"][value="performance"]');
        if (firstType) firstType.checked = true;
        document.getElementById('goal-plan-options')?.classList.add('hidden');
        document.getElementById('goal-plan-conflict')?.classList.add('hidden');
        document.getElementById('goal-plan-duration-label').textContent = '8 weeks';
        this._conflictPlanId = null;
    }

    async _checkConflict() {
        const sport = document.getElementById('goal-plan-sport')?.value;
        if (!sport) return;
        const conflictEl  = document.getElementById('goal-plan-conflict');
        const detailEl    = document.getElementById('goal-plan-conflict-detail');
        try {
            const data = await api.get(`/training-plans/compatibility?sport=${encodeURIComponent(sport)}`);
            if (!data.compatible && data.conflicts?.length) {
                const c = data.conflicts[0];
                this._conflictPlanId = c.id;
                detailEl.textContent = `"${c.title}" (${c.sport}) is active until ${c.end_date || '—'}. A new plan cannot run alongside it.`;
                conflictEl?.classList.remove('hidden');
            } else {
                this._conflictPlanId = null;
                conflictEl?.classList.add('hidden');
            }
        } catch (_) {
            this._conflictPlanId = null;
            conflictEl?.classList.add('hidden');
        }
    }

    async _saveGoal() {
        const description = document.getElementById('goal-description')?.value?.trim();
        if (!description) { window.showToast('Please describe your goal', 'warning'); return; }

        const goalType   = document.querySelector('input[name="goal-type"]:checked')?.value || 'custom';
        const targetDate = document.getElementById('goal-target-date')?.value || null;
        const targetVal  = document.getElementById('goal-target-value')?.value;
        const genPlan    = document.getElementById('goal-gen-plan')?.checked ?? false;
        const sport      = document.getElementById('goal-plan-sport')?.value || 'running';
        const durationWk = parseInt(document.getElementById('goal-plan-duration')?.value || '8', 10);
        const deactivate = document.getElementById('goal-deactivate-conflict')?.checked ?? false;

        // Block if conflict exists and user hasn't acknowledged deactivation
        if (genPlan && this._conflictPlanId && !deactivate) {
            window.showToast('Please confirm deactivation of the conflicting plan to continue', 'warning');
            return;
        }

        const btn = document.getElementById('btn-save-goal');
        btn.disabled = true;
        btn.textContent = 'Saving…';

        try {
            // 1. Save the goal
            const goal = await api.post('/goals', {
                goal_type:    goalType,
                description:  description,
                target_date:  targetDate || null,
                target_value: targetVal ? parseFloat(targetVal) : null,
                status:       'active',
            });

            document.getElementById('new-goal-modal').close();
            window.showToast('Goal saved', 'success');
            await this._reload();

            // 2. Optionally generate a plan
            if (genPlan) {
                // Deactivate conflicting plan first if needed
                if (this._conflictPlanId && deactivate) {
                    await api.post(`/training-plans/${this._conflictPlanId}/deactivate`);
                }
                window.showToast('Generating training plan…', 'info', 8000);
                btn.textContent = 'Generating plan…';
                const plan = await api.post('/training-plans/generate', {
                    goal_id:        goal.id,
                    sport:          sport,
                    duration_weeks: durationWk,
                });
                window.showToast(`Plan created: ${plan.title}`, 'success', 5000);
                // Navigate to the new plan
                if (plan.plan_id) router.navigate(`/training-plans/${plan.plan_id}`);
            }
        } catch (err) {
            window.showToast(`Failed: ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Save Goal';
        }
    }

    // ── Actions ──────────────────────────────────────────────────────────────

    async markCompleted(id) {
        if (!confirm('Mark this goal as completed?')) return;
        try {
            await api.put(`/goals/${id}`, { status: 'completed' });
            window.showToast('Goal completed!', 'success');
            await this._reload();
        } catch (err) { window.showToast(`Failed: ${err.message}`, 'error'); }
    }

    async markAbandoned(id) {
        if (!confirm('Mark this goal as abandoned?')) return;
        try {
            await api.put(`/goals/${id}`, { status: 'abandoned' });
            window.showToast('Goal abandoned', 'info');
            await this._reload();
        } catch (err) { window.showToast(`Failed: ${err.message}`, 'error'); }
    }

    async deleteGoal(id) {
        if (!confirm('Delete this goal? This cannot be undone.')) return;
        try {
            await api.delete(`/goals/${id}`);
            window.showToast('Goal deleted', 'info');
            await this._reload();
        } catch (err) { window.showToast(`Failed: ${err.message}`, 'error'); }
    }
}

export { GoalsManager };

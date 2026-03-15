/**
 * logs-page.js — ES Module
 *
 * Παράδειγμα page module. Κάνει import τα components που χρειάζεται.
 * Το app.js φορτώνει αυτό το αρχείο μόνο όταν ο χρήστης πάει στο /logs.
 */

import { api } from '/js/api.js';

// Τα component scripts (daily-log-form.js, daily-log-list.js) δεν είναι
// ακόμα ES modules — γι' αυτό τα φορτώνει το app.js με import() πριν
// από αυτό το module. Όταν τα μετατρέψεις σε modules, κάνε:
// import { DailyLogForm } from '/js/daily-log-form.js';
// import { DailyLogList } from '/js/daily-log-list.js';

export class LogsPage {
  async init(params, query) {
    this._form = new DailyLogForm('daily-log-form-container');
    this._form.render();
    this._form.onSuccess(() => {
      this._loadWeeklyStats();
      this._list?.load();
      document.getElementById('log-form-modal')?.close();
    });

    this._list = new DailyLogList('daily-log-list-container');
    await this._list.load();
    await this._loadWeeklyStats();

    document.getElementById('add-log-btn')
      ?.addEventListener('click', () =>
        document.getElementById('log-form-modal')?.showModal()
      );
  }

  destroy() {}

  async _loadWeeklyStats() {
    try {
      const response = await api.listDailyLogs();
      const logs = response.logs || response;
      if (!logs?.length) return;

      const weekStart = getWeekStart(); // από utils.js
      const weekLogs  = logs.filter(l => new Date(l.log_date) >= weekStart);
      if (!weekLogs.length) return;

      let totalCal = 0, totalAdh = 0, totalProt = 0;
      weekLogs.forEach(l => {
        if (l.calories_in)             totalCal  += l.calories_in;
        if (l.adherence_score != null) totalAdh  += l.adherence_score;
        if (l.protein_g)               totalProt += l.protein_g;
      });

      const n   = weekLogs.length;
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
      set('avg-calories',  totalCal  > 0 ? Math.round(totalCal / n)         : '--');
      set('avg-adherence', totalAdh  > 0 ? (totalAdh / n).toFixed(1)        : '--');
      set('avg-sleep',     totalProt > 0 ? (totalProt / n).toFixed(1) + 'g' : '--');
      set('avg-energy',    n);
    } catch (err) {
      console.error('Error loading weekly stats:', err);
    }
  }
}
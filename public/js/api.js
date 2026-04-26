/**
 * Fitness Evaluation API Client
 * Communicates with the FastAPI backend
 */

import { getToken, logout } from '/js/auth.js';

class APIClient {
  constructor(baseUrl = null) {
    // If no baseUrl provided, use current origin + /api
    // If in Node.js environment (testing), use provided baseUrl or default
    if (!baseUrl) {
      if (typeof window !== 'undefined') {
        this.baseUrl = `${window.location.origin}/api`;
      } else {
        this.baseUrl = 'http://localhost:8000/api';
      }
    } else {
      this.baseUrl = baseUrl;
    }
  }

  async request(method, endpoint, data = null) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = { 'Content-Type': 'application/json' };

    const token = getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const options = { method, headers };
    if (data) options.body = JSON.stringify(data);

    try {
      const response = await fetch(url, options);

      if (response.status === 401) {
        // Token expired or invalid — force re-login
        logout();
        return;
      }

      if (!response.ok) {
        let message = `HTTP ${response.status}`;
        const ct = response.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
          try {
            const errorData = await response.json();
            message = errorData.detail || message;
          } catch { /* ignore parse failure */ }
        }
        throw new Error(message);
      }
      const ct = response.headers.get('content-type') || '';
      if (!ct.includes('application/json')) return null;
      return await response.json();
    } catch (error) {
      console.error(`API Error: ${method} ${endpoint}`, error);
      throw error;
    }
  }

  // Generic HTTP methods for flexible API calls
  async get(endpoint) {
    return this.request('GET', endpoint);
  }

  async post(endpoint, data) {
    return this.request('POST', endpoint, data);
  }

  async put(endpoint, data) {
    return this.request('PUT', endpoint, data);
  }

  async delete(endpoint) {
    return this.request('DELETE', endpoint);
  }

  // Daily Logs
  async createDailyLog(log) {
    return this.request('POST', '/logs/daily', log);
  }

  async getDailyLog(date) {
    return this.request('GET', `/logs/daily/${date}`);
  }

  async updateDailyLog(logId, log) {
    return this.request('PUT', `/logs/daily/${logId}`, log);
  }

  async listDailyLogs(startDate = null, endDate = null) {
    let endpoint = '/logs/daily';
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (params.toString()) endpoint += '?' + params.toString();
    return this.request('GET', endpoint);
  }

  // Weekly Measurements (legacy endpoints)
  async createWeeklyMeasurement(measurement) {
    return this.request('POST', '/logs/weekly', measurement);
  }

  async updateWeeklyMeasurement(id, measurement) {
    return this.request('PUT', `/logs/weekly/${id}`, measurement);
  }

  async getWeeklyMeasurement(weekStart) {
    return this.request('GET', `/logs/weekly/${weekStart}`);
  }

  async listWeeklyMeasurements() {
    return this.request('GET', '/logs/weekly');
  }

  // Body Metrics (new endpoints - Requirements 5.4, 5.5, 5.6)
  async createMetric(metric) {
    return this.request('POST', '/metrics', metric);
  }

  async updateMetric(id, metric) {
    return this.request('PUT', `/metrics/${id}`, metric);
  }

  async getMetric(metricId) {
    return this.request('GET', `/metrics/${metricId}`);
  }

  async listMetrics(dateFrom = null, dateTo = null) {
    let endpoint = '/metrics';
    const params = new URLSearchParams();
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    if (params.toString()) endpoint += '?' + params.toString();
    return this.request('GET', endpoint);
  }

  async getTrendAnalysis(athleteGoals = null, currentPlan = null) {
    let endpoint = '/metrics/trends/analysis';
    const params = new URLSearchParams();
    if (athleteGoals) params.append('athlete_goals', athleteGoals);
    if (currentPlan) params.append('current_plan', currentPlan);
    if (params.toString()) endpoint += '?' + params.toString();
    return this.request('GET', endpoint);
  }

  // Plan Targets
  async createPlanTargets(targets) {
    return this.request('POST', '/logs/targets', targets);
  }

  // Backwards-compatible alias for single-target creation
  async createPlanTarget(target) {
    return this.createPlanTargets(target);
  }

  async getPlanTargets(targetId) {
    return this.request('GET', `/logs/targets/${targetId}`);
  }

  async listPlanTargets() {
    return this.request('GET', '/logs/targets');
  }

  async getCurrentPlanTargets() {
    return this.request('GET', '/logs/targets/current');
  }

  // Strava
  async syncStravaActivities(weekStart) {
    return this.request('POST', `/strava/sync/${weekStart}`);
  }

  async getWeeklyActivities(weekStart) {
    return this.request('GET', `/strava/activities/${weekStart}`);
  }

  async getWeeklyAggregates(weekStart) {
    return this.request('GET', `/strava/aggregates/${weekStart}`);
  }

  // Evaluations
  async evaluateWeek(weekStart) {
    return this.request('POST', `/evaluate/${weekStart}`);
  }

  async getEvaluation(weekStart) {
    return this.request('GET', `/evaluate/${weekStart}`);
  }

  async refreshEvaluation(weekStart) {
    return this.request('POST', `/evaluate/${weekStart}/refresh`);
  }

  // Activities
  async getActivities(params = {}) {
    let endpoint = '/strava/activities/all';
    const queryParams = new URLSearchParams();
    
    // Pagination
    if (params.page) queryParams.append('page', params.page);
    if (params.page_size) queryParams.append('page_size', params.page_size);
    
    // Filtering
    if (params.type) queryParams.append('type', params.type);
    if (params.date_from) queryParams.append('date_from', params.date_from);
    if (params.date_to) queryParams.append('date_to', params.date_to);
    if (params.distance_min !== null && params.distance_min !== undefined) {
      queryParams.append('distance_min', params.distance_min);
    }
    if (params.distance_max !== null && params.distance_max !== undefined) {
      queryParams.append('distance_max', params.distance_max);
    }
    
    // Sorting
    if (params.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params.sort_dir) queryParams.append('sort_dir', params.sort_dir);
    
    if (queryParams.toString()) endpoint += '?' + queryParams.toString();
    return this.request('GET', endpoint);
  }

  async getActivity(activityId) {
    return this.request('GET', `/strava/activities/detail/${activityId}`);
  }
}

// Create global API instance
const api = new APIClient();

export { api, APIClient };
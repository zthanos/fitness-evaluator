/**
 * Fitness Evaluation API Client
 * Communicates with the FastAPI backend
 */

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
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    if (data) {
      options.body = JSON.stringify(data);
    }

    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error(`API Error: ${method} ${endpoint}`, error);
      throw error;
    }
  }

  // Daily Logs
  async createDailyLog(log) {
    return this.request('POST', '/logs/daily', log);
  }

  async getDailyLog(date) {
    return this.request('GET', `/logs/daily/${date}`);
  }

  async listDailyLogs(startDate = null, endDate = null) {
    let endpoint = '/logs/daily';
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (params.toString()) endpoint += '?' + params.toString();
    return this.request('GET', endpoint);
  }

  // Weekly Measurements
  async createWeeklyMeasurement(measurement) {
    return this.request('POST', '/logs/weekly', measurement);
  }

  async getWeeklyMeasurement(weekStart) {
    return this.request('GET', `/logs/weekly/${weekStart}`);
  }

  async listWeeklyMeasurements() {
    return this.request('GET', '/logs/weekly');
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
}

// Create global API instance
const api = new APIClient();

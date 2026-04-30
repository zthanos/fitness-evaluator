/**
 * ActivityDetail Component
 * Handles fetching and displaying detailed activity information
 */
class ActivityDetail {
    constructor(containerId, activityId) {
        this.container = document.getElementById(containerId);
        this.activityId = activityId;
        this.activity = null;
        this.mapInstance = null;
    }

    /**
     * Initialize the activity detail view
     */
    async init() {
        try {
            await this.fetchActivity();
            this.render();
            // Fetch and display effort analysis after rendering main content
            await this.fetchAndDisplayAnalysis();
        } catch (error) {
            console.error('Failed to load activity:', error);
            this.showError(error.message || 'Failed to load activity details');
        }
    }

    /**
     * Fetch activity data from API
     */
    async fetchActivity() {
        const loadingContainer = document.getElementById('loading-container');
        
        try {
            this.activity = await api.get(`/strava/activities/detail/${this.activityId}`);
            
            // Hide loading indicator
            loadingContainer.classList.add('hidden');
            
        } catch (error) {
            loadingContainer.classList.add('hidden');
            throw error;
        }
    }

    /**
     * Render the activity details
     */
    render() {
        if (!this.activity) {
            this.showError('No activity data available');
            return;
        }

        // Show the container
        this.container.classList.remove('hidden');

        // Render header
        this.renderHeader();

        // Render stats
        this.renderStats();

        // Render heart rate if available
        this.renderHeartRate();

        // Render performance metrics (cadence / power) if available
        this.renderPerformanceMetrics();

        // Render splits if available
        this.renderSplits();

        // Render map if available
        this.renderMap();

        // Render additional details
        this.renderAdditionalDetails();
    }

    /**
     * Render activity header (title, type, date)
     */
    renderHeader() {
        const title = document.getElementById('activity-title');
        const typeBadge = document.getElementById('activity-type-badge');
        const dateBadge = document.getElementById('activity-date');

        // Set title (use sport/activity type if no name available)
        const activityName = this.activity.name ||
            this.activity.sport_type || this.activity.activity_type;
        title.textContent = activityName;

        // Prefer sport_type (e.g. "Tennis") over legacy activity_type (e.g. "Workout")
        typeBadge.textContent = this.activity.sport_type || this.activity.activity_type;

        // Set date badge
        const activityDate = new Date(this.activity.start_date);
        dateBadge.textContent = activityDate.toLocaleDateString('en-US', {
            weekday: 'short',
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    /**
     * Render main activity stats
     */
    renderStats() {
        // Distance
        const distanceEl = document.getElementById('stat-distance');
        if (this.activity.distance_m != null) {
            const distanceKm = (this.activity.distance_m / 1000).toFixed(2);
            distanceEl.textContent = `${distanceKm} km`;
        } else {
            distanceEl.textContent = 'N/A';
        }

        // Duration
        const durationEl = document.getElementById('stat-duration');
        if (this.activity.moving_time_s != null) {
            durationEl.textContent = this.formatDuration(this.activity.moving_time_s);
        } else {
            durationEl.textContent = 'N/A';
        }

        // Pace/Speed
        const paceEl = document.getElementById('stat-pace');
        const paceLabel = document.getElementById('pace-label');
        
        if (this.activity.distance_m != null && this.activity.moving_time_s != null && this.activity.distance_m > 0) {
            const isRunning = this.activity.activity_type === 'Run' || this.activity.activity_type === 'Walk';
            
            if (isRunning) {
                // Show pace (min/km)
                paceLabel.textContent = 'Pace';
                const paceMinPerKm = (this.activity.moving_time_s / 60) / (this.activity.distance_m / 1000);
                const paceMin = Math.floor(paceMinPerKm);
                const paceSec = Math.round((paceMinPerKm - paceMin) * 60);
                paceEl.textContent = `${paceMin}:${paceSec.toString().padStart(2, '0')} /km`;
            } else {
                // Show speed (km/h)
                paceLabel.textContent = 'Speed';
                const speedKmh = (this.activity.distance_m / 1000) / (this.activity.moving_time_s / 3600);
                paceEl.textContent = `${speedKmh.toFixed(1)} km/h`;
            }
        } else {
            paceEl.textContent = 'N/A';
        }

        // Elevation
        const elevationEl = document.getElementById('stat-elevation');
        if (this.activity.elevation_m != null) {
            elevationEl.textContent = `${Math.round(this.activity.elevation_m)} m`;
        } else {
            elevationEl.textContent = 'N/A';
        }
    }

    /**
     * Render heart rate data if available
     */
    renderHeartRate() {
        const hrSection = document.getElementById('heart-rate-section');
        const avgHrEl = document.getElementById('stat-avg-hr');
        const maxHrEl = document.getElementById('stat-max-hr');

        if (this.activity.avg_hr != null || this.activity.max_hr != null) {
            hrSection.classList.remove('hidden');
            
            if (this.activity.avg_hr != null) {
                avgHrEl.textContent = `${this.activity.avg_hr} bpm`;
            } else {
                avgHrEl.textContent = 'N/A';
            }

            if (this.activity.max_hr != null) {
                maxHrEl.textContent = `${this.activity.max_hr} bpm`;
            } else {
                maxHrEl.textContent = 'N/A';
            }
        }
    }

    /**
     * Render splits data if available in raw_json
     */
    renderSplits() {
        const splitsSection = document.getElementById('splits-section');
        const splitsTableBody = document.getElementById('splits-table-body');

        // Check if raw_json contains splits data
        if (!this.activity.raw_json) {
            return;
        }

        const rawData = this._parseRawJson();
        if (!rawData) return;

        const splits = rawData.splits_metric || rawData.splits_standard;
        
        if (!splits || splits.length === 0) {
            return;
        }

        // Show splits section
        splitsSection.classList.remove('hidden');

        // Clear existing rows
        splitsTableBody.innerHTML = '';

        // Render each split
        splits.forEach((split, index) => {
            const row = document.createElement('tr');
            
            // Split number
            const splitNumCell = document.createElement('td');
            splitNumCell.textContent = index + 1;
            row.appendChild(splitNumCell);

            // Distance
            const distanceCell = document.createElement('td');
            distanceCell.textContent = split.distance ? `${(split.distance / 1000).toFixed(2)} km` : 'N/A';
            row.appendChild(distanceCell);

            // Time
            const timeCell = document.createElement('td');
            timeCell.textContent = split.moving_time ? this.formatDuration(split.moving_time) : 'N/A';
            row.appendChild(timeCell);

            // Pace
            const paceCell = document.createElement('td');
            if (split.moving_time && split.distance && split.distance > 0) {
                const paceMinPerKm = (split.moving_time / 60) / (split.distance / 1000);
                const paceMin = Math.floor(paceMinPerKm);
                const paceSec = Math.round((paceMinPerKm - paceMin) * 60);
                paceCell.textContent = `${paceMin}:${paceSec.toString().padStart(2, '0')} /km`;
            } else {
                paceCell.textContent = 'N/A';
            }
            row.appendChild(paceCell);

            // Elevation
            const elevationCell = document.createElement('td');
            elevationCell.textContent = split.elevation_difference ? `${Math.round(split.elevation_difference)} m` : 'N/A';
            row.appendChild(elevationCell);

            splitsTableBody.appendChild(row);
        });
    }

    /**
     * Render activity map with route if available
     */
    renderMap() {
        const mapSection = document.getElementById('map-section');
        const mapContainer = document.getElementById('activity-map');

        // Check if raw_json contains map data
        if (!this.activity.raw_json) {
            return;
        }

        const rawData = this._parseRawJson();
        if (!rawData) return;

        // Check for map data (polyline or lat/lng coordinates)
        const map = rawData.map;
        if (!map || (!map.summary_polyline && !map.polyline)) {
            // No map data available
            return;
        }

        // Show map section
        mapSection.classList.remove('hidden');

        // Initialize Leaflet map
        // Clear any existing map instance
        if (this.mapInstance) {
            this.mapInstance.remove();
        }

        // Create map centered on default location (will be adjusted after polyline is added)
        this.mapInstance = L.map(mapContainer, {
            zoomControl: true,
            scrollWheelZoom: true
        });

        // Add OpenStreetMap tile layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        }).addTo(this.mapInstance);

        // Decode polyline and add to map
        const polylineString = map.summary_polyline || map.polyline;
        if (polylineString) {
            try {
                const coordinates = this.decodePolyline(polylineString);
                
                if (coordinates.length > 0) {
                    // Add polyline to map
                    const polyline = L.polyline(coordinates, {
                        color: '#3b82f6',
                        weight: 3,
                        opacity: 0.8
                    }).addTo(this.mapInstance);

                    // Add start marker (green)
                    L.circleMarker(coordinates[0], {
                        radius: 8,
                        fillColor: '#10b981',
                        color: '#fff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.9
                    }).addTo(this.mapInstance).bindPopup('Start');

                    // Add end marker (red)
                    L.circleMarker(coordinates[coordinates.length - 1], {
                        radius: 8,
                        fillColor: '#ef4444',
                        color: '#fff',
                        weight: 2,
                        opacity: 1,
                        fillOpacity: 0.9
                    }).addTo(this.mapInstance).bindPopup('Finish');

                    // Fit map bounds to polyline
                    this.mapInstance.fitBounds(polyline.getBounds(), {
                        padding: [20, 20]
                    });
                }
            } catch (e) {
                console.error('Failed to decode polyline:', e);
            }
        }
    }

    /**
     * Parse raw_json — returns the object or null if unparseable.
     * Handles both proper JSON (new enrichments) and legacy Python-dict strings.
     */
    _parseRawJson() {
        const raw = this.activity.raw_json;
        if (!raw) return null;
        if (typeof raw !== 'string') return raw;

        // Fast path: proper JSON (all new data)
        try { return JSON.parse(raw); } catch (_) {}

        // Slow path: legacy Python str(dict) stored before the json.dumps fix.
        // Only safe for activities that haven't been re-enriched yet.
        // Silently return null rather than log an error — the sections stay hidden.
        return null;
    }

    /**
     * Decode Google polyline format to lat/lng coordinates
     * Based on the Polyline encoding algorithm
     */
    decodePolyline(encoded) {
        const coordinates = [];
        let index = 0;
        let lat = 0;
        let lng = 0;

        while (index < encoded.length) {
            let b;
            let shift = 0;
            let result = 0;

            // Decode latitude
            do {
                b = encoded.charCodeAt(index++) - 63;
                result |= (b & 0x1f) << shift;
                shift += 5;
            } while (b >= 0x20);

            const dlat = ((result & 1) ? ~(result >> 1) : (result >> 1));
            lat += dlat;

            shift = 0;
            result = 0;

            // Decode longitude
            do {
                b = encoded.charCodeAt(index++) - 63;
                result |= (b & 0x1f) << shift;
                shift += 5;
            } while (b >= 0x20);

            const dlng = ((result & 1) ? ~(result >> 1) : (result >> 1));
            lng += dlng;

            // Convert to degrees and add to coordinates array
            coordinates.push([lat / 1e5, lng / 1e5]);
        }

        return coordinates;
    }

    /**
     * Render cadence and power metrics if available
     */
    renderPerformanceMetrics() {
        const section = document.getElementById('performance-section');
        let hasData = false;

        const show = (wrapperId, statId, value, unit) => {
            if (value != null) {
                document.getElementById(wrapperId).classList.remove('hidden');
                document.getElementById(statId).textContent = `${Math.round(value)} ${unit}`;
                hasData = true;
            }
        };

        show('avg-cadence-detail',  'stat-avg-cadence',    this.activity.avg_cadence,        'rpm');
        show('max-cadence-detail',  'stat-max-cadence',    this.activity.max_cadence,        'rpm');
        show('avg-watts-detail',    'stat-avg-watts',      this.activity.avg_watts,          'W');
        show('weighted-watts-detail','stat-weighted-watts', this.activity.weighted_avg_watts, 'W');

        if (hasData) section.classList.remove('hidden');
    }

    /**
     * Render additional details
     */
    renderAdditionalDetails() {
        // Calories
        if (this.activity.calories != null) {
            document.getElementById('calories-detail').classList.remove('hidden');
            document.getElementById('stat-calories').textContent =
                `${Math.round(this.activity.calories)} kcal`;
        }

        // Suffer score
        if (this.activity.suffer_score != null) {
            document.getElementById('suffer-score-detail').classList.remove('hidden');
            document.getElementById('stat-suffer-score').textContent = this.activity.suffer_score;
        }

        // Legacy activity_type (only show when different from sport_type to avoid duplication)
        if (this.activity.activity_type && this.activity.activity_type !== this.activity.sport_type) {
            document.getElementById('sport-type-detail').classList.remove('hidden');
            document.getElementById('stat-sport-type').textContent = this.activity.activity_type;
            document.querySelector('#sport-type-detail p.text-sm').textContent = 'Activity Type (legacy)';
        }

        // Activity ID
        document.getElementById('stat-activity-id').textContent = this.activity.strava_id;

        // Enrichment badge
        if (this.activity.enriched) {
            document.getElementById('enriched-badge').classList.remove('hidden');
        }
    }

    /**
     * Format duration in seconds to human-readable format
     */
    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        if (hours > 0) {
            return `${hours}h ${minutes}m ${secs}s`;
        } else if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        } else {
            return `${secs}s`;
        }
    }

    /**
     * Show error message
     */
    showError(message) {
        document.getElementById('loading-container').classList.add('hidden');
        document.getElementById('error-message').textContent = message;
        document.getElementById('error-container').classList.remove('hidden');
        this.container.classList.add('hidden');
    }

    /**
     * Fetch and display AI effort analysis.
     * @param {boolean} force - bypass cache and regenerate
     */
    async fetchAndDisplayAnalysis(force = false) {
        const analysisSection = document.getElementById('analysis-section');
        const analysisLoading = document.getElementById('analysis-loading');
        const analysisContent = document.getElementById('analysis-content');
        const analysisError = document.getElementById('analysis-error');

        // Reset to loading state
        analysisSection.classList.remove('hidden');
        analysisLoading.classList.remove('hidden');
        analysisContent.classList.add('hidden');
        analysisError.classList.add('hidden');
        analysisContent.innerHTML = '';

        try {
            // 60 s timeout — newly enriched activities need a full LLM generation pass
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000);

            const token = window.getAuthToken?.();
            const url = `/api/strava/activities/detail/${this.activityId}/analysis` +
                (force ? '?force=true' : '');
            const response = await fetch(url, {
                signal: controller.signal,
                headers: token ? { 'Authorization': `Bearer ${token}` } : {},
            });

            clearTimeout(timeoutId);

            if (!response.ok) throw new Error('Failed to fetch analysis');

            const data = await response.json();

            analysisLoading.classList.add('hidden');
            analysisContent.classList.remove('hidden');

            let formattedText = data.analysis_text
                .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                .replace(/\n\n/g, '</p><p>')
                .replace(/\n/g, '<br>');

            analysisContent.innerHTML = `<p>${formattedText}</p>`;

            // Footer row: cached badge + regenerate button
            const footer = document.createElement('div');
            footer.className = 'flex items-center gap-3 mt-3';

            if (data.cached) {
                const cachedBadge = document.createElement('span');
                cachedBadge.className = 'badge badge-ghost badge-sm';
                cachedBadge.textContent = 'Cached analysis';
                footer.appendChild(cachedBadge);
            }

            const regenBtn = document.createElement('button');
            regenBtn.className = 'btn btn-xs btn-outline';
            regenBtn.textContent = 'Regenerate';
            regenBtn.addEventListener('click', () => this.fetchAndDisplayAnalysis(true));
            footer.appendChild(regenBtn);

            analysisContent.appendChild(footer);

        } catch (error) {
            analysisLoading.classList.add('hidden');
            console.error('Failed to fetch effort analysis:', error);

            const msg = error.name === 'AbortError'
                ? 'Analysis generation timed out.'
                : 'Unable to generate effort analysis at this time.';

            analysisError.querySelector('span').textContent = msg;
            analysisError.classList.remove('hidden');

            // Retry button inside the error alert
            const retryBtn = document.createElement('button');
            retryBtn.className = 'btn btn-xs btn-warning ml-3';
            retryBtn.textContent = 'Retry';
            retryBtn.addEventListener('click', () => this.fetchAndDisplayAnalysis(true));
            analysisError.appendChild(retryBtn);
        }
    }
}
export { ActivityDetail };
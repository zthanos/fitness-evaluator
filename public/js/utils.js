/**
 * Utility functions for the UI
 */

/**
 * Get the Monday of the week for a given date
 */
function getWeekStart(date = new Date()) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.setDate(diff));
}

/**
 * Format date to YYYY-MM-DD
 */
function formatDate(date) {
  const d = new Date(date);
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${month}-${day}`;
}

/**
 * Format date for display (e.g., "Jan 6, 2025")
 */
function formatDateDisplay(date) {
  const d = new Date(date + 'T00:00:00');
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

/**
 * Get week range string (e.g., "Jan 6 - Jan 12")
 */
function getWeekRange(weekStart) {
  const start = new Date(weekStart + 'T00:00:00');
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  
  const startStr = start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const endStr = end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  
  return `${startStr} - ${endStr}`;
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
  const alertDiv = document.createElement('div');
  alertDiv.className = `alert alert-${type} fixed top-4 right-4 w-96 shadow-lg`;
  alertDiv.innerHTML = `
    <div>
      <span>${message}</span>
    </div>
  `;
  document.body.appendChild(alertDiv);
  
  setTimeout(() => {
    alertDiv.remove();
  }, 4000);
}

/**
 * Show error toast
 */
function showError(error) {
  const message = error.message || 'An error occurred';
  showToast(message, 'error');
}

/**
 * Show success toast
 */
function showSuccess(message) {
  showToast(message, 'success');
}

/**
 * Hide all modal dialogs
 */
function closeAllModals() {
  document.querySelectorAll('dialog').forEach(dialog => {
    dialog.close();
  });
}

/**
 * Format time duration (seconds to HH:MM:SS)
 */
function formatDuration(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

/**
 * Format distance (meters to km)
 */
function formatDistance(meters) {
  if (!meters) return '0 km';
  return `${(meters / 1000).toFixed(1)} km`;
}

/**
 * Get color for score (1-10)
 */
function getScoreColor(score) {
  if (score >= 9) return 'text-green-600';
  if (score >= 7) return 'text-blue-600';
  if (score >= 5) return 'text-yellow-600';
  if (score >= 3) return 'text-orange-600';
  return 'text-red-600';
}

/**
 * Get badge color for score
 */
function getScoreBadge(score) {
  if (score >= 9) return 'badge-success';
  if (score >= 7) return 'badge-info';
  if (score >= 5) return 'badge-warning';
  if (score >= 3) return 'badge-error';
  return 'badge-error';
}

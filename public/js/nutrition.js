import { api } from '/js/api.js';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentDate = new Date().toISOString().slice(0, 10);
let dayLog = null;
let editingItem = null; // { mealId, itemId } when editing an existing item

// ---------------------------------------------------------------------------
// Public class — used by NutritionPage in all-pages.js
// ---------------------------------------------------------------------------
export class NutritionManager {
  init() {
    document.getElementById('date-picker').value = currentDate;
    document.getElementById('date-picker').addEventListener('change', e => {
      currentDate = e.target.value;
      loadDay();
    });
    document.getElementById('prev-day').addEventListener('click', () => shiftDay(-1));
    document.getElementById('next-day').addEventListener('click', () => shiftDay(1));
    document.getElementById('item-form').addEventListener('submit', handleItemFormSubmit);
    document.getElementById('add-meal-form').addEventListener('submit', handleAddMealSubmit);

    // Expose actions called from inline onclick
    window._nutrition = {
      openAddMealModal,
      openAddItemModal,
      openEditItemModal,
      deleteMeal,
      deleteItem,
      confirmItem,
    };

    loadDay();
  }

  destroy() {
    delete window._nutrition;
  }
}

// ---------------------------------------------------------------------------
// Day navigation
// ---------------------------------------------------------------------------
function shiftDay(delta) {
  const d = new Date(currentDate);
  d.setDate(d.getDate() + delta);
  currentDate = d.toISOString().slice(0, 10);
  document.getElementById('date-picker').value = currentDate;
  loadDay();
}

// ---------------------------------------------------------------------------
// Load day
// ---------------------------------------------------------------------------
async function loadDay() {
  showLoading(true);
  try {
    dayLog = await api.getDayLog(currentDate);
  } catch (err) {
    if (err.message?.includes('404')) {
      dayLog = { log_date: currentDate, meals: [], totals: emptyTotals() };
    } else {
      showToast('Failed to load day log: ' + err.message, 'error');
      showLoading(false);
      return;
    }
  }
  renderDay();
  showLoading(false);
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------
const MEAL_ORDER = ['breakfast', 'lunch', 'dinner', 'snack'];
const MEAL_ICONS = { breakfast: '🌅', lunch: '☀️', dinner: '🌙', snack: '🍎' };

function renderDay() {
  renderTotals(dayLog.totals);

  const container = document.getElementById('meals-container');
  container.innerHTML = '';

  const mealsByType = {};
  for (const m of dayLog.meals) {
    if (!mealsByType[m.meal_type]) mealsByType[m.meal_type] = [];
    mealsByType[m.meal_type].push(m);
  }

  for (const type of MEAL_ORDER) {
    const meals = mealsByType[type] || [];
    container.appendChild(renderMealSection(type, meals));
  }
}

function renderTotals(totals) {
  document.getElementById('total-calories').textContent = Math.round(totals.calories);
  document.getElementById('total-protein').textContent = totals.protein_g.toFixed(1) + 'g';
  document.getElementById('total-carbs').textContent = totals.carbs_g.toFixed(1) + 'g';
  document.getElementById('total-fat').textContent = totals.fat_g.toFixed(1) + 'g';
  document.getElementById('total-meals').textContent = totals.meal_count;

  const conf = Math.round(totals.confidence_score * 100);
  const confEl = document.getElementById('confidence-score');
  confEl.textContent = conf + '%';
  confEl.className = 'stat-value text-lg ' + (conf >= 80 ? 'text-success' : conf >= 50 ? 'text-warning' : 'text-error');
}

function renderMealSection(type, meals) {
  const section = document.createElement('div');
  section.className = 'card bg-base-100 shadow mb-4';
  section.dataset.mealType = type;

  const allItems = meals.flatMap(m => m.items);
  const sectionCal = allItems.reduce((s, i) => s + (i.calories || 0), 0);

  section.innerHTML = `
    <div class="card-body p-4">
      <div class="flex justify-between items-center mb-3">
        <h3 class="text-lg font-semibold capitalize">
          ${MEAL_ICONS[type]} ${type}
          <span class="text-sm font-normal text-base-content/60 ml-2">${Math.round(sectionCal)} kcal</span>
        </h3>
        <button class="btn btn-sm btn-primary gap-1" onclick="window._nutrition.openAddMealModal('${type}')">
          + Add meal
        </button>
      </div>
      <div class="space-y-3" id="meals-${type}">
        ${meals.map(m => renderMealCard(m)).join('')}
        ${meals.length === 0 ? '<p class="text-sm text-base-content/40 italic">No meals logged yet.</p>' : ''}
      </div>
    </div>`;

  return section;
}

function renderMealCard(meal) {
  const t = meal.totals;
  const hasPending = meal.items.some(i => i.needs_confirmation);
  return `
    <div class="border border-base-300 rounded-lg p-3" id="meal-${meal.id}">
      <div class="flex justify-between items-start mb-2">
        <div>
          <span class="font-medium">${escHtml(meal.name || meal.meal_type)}</span>
          ${hasPending ? '<span class="badge badge-warning badge-sm ml-2">needs review</span>' : ''}
        </div>
        <div class="flex gap-1">
          <button class="btn btn-xs btn-ghost" onclick="window._nutrition.openAddItemModal('${meal.id}')">+ Item</button>
          <button class="btn btn-xs btn-ghost text-error" onclick="window._nutrition.deleteMeal('${meal.id}')">Delete</button>
        </div>
      </div>
      <div class="text-xs text-base-content/60 mb-2">
        ${Math.round(t.calories)} kcal · P ${t.protein_g.toFixed(1)}g · C ${t.carbs_g.toFixed(1)}g · F ${t.fat_g.toFixed(1)}g
      </div>
      <div class="space-y-1">
        ${meal.items.map(i => renderItemRow(meal.id, i)).join('')}
      </div>
    </div>`;
}

function renderItemRow(mealId, item) {
  const srcBadge = item.source !== 'manual'
    ? `<span class="badge badge-sm badge-outline">${item.source}</span>`
    : '';
  const confBadge = item.needs_confirmation
    ? `<span class="badge badge-sm badge-warning">unconfirmed</span>`
    : '';
  const lowConf = item.confidence < 0.7
    ? `<span class="badge badge-sm badge-error">${Math.round(item.confidence * 100)}%</span>`
    : '';
  return `
    <div class="flex justify-between items-center py-1 border-b border-base-200 last:border-0 text-sm" id="item-${item.id}">
      <div class="flex-1 min-w-0">
        <span>${escHtml(item.name)}</span>
        ${item.quantity ? `<span class="text-base-content/50 ml-1">${item.quantity}${item.unit ? ' ' + item.unit : ''}</span>` : ''}
        ${srcBadge} ${confBadge} ${lowConf}
      </div>
      <div class="text-right text-base-content/60 mr-3 shrink-0">
        ${item.calories != null ? Math.round(item.calories) + ' kcal' : ''}
      </div>
      <div class="flex gap-1 shrink-0">
        ${item.needs_confirmation ? `<button class="btn btn-xs btn-success" onclick="window._nutrition.confirmItem('${mealId}','${item.id}')">✓</button>` : ''}
        <button class="btn btn-xs btn-ghost" onclick="window._nutrition.openEditItemModal('${mealId}','${item.id}')">Edit</button>
        <button class="btn btn-xs btn-ghost text-error" onclick="window._nutrition.deleteItem('${mealId}','${item.id}')">✕</button>
      </div>
    </div>`;
}

// ---------------------------------------------------------------------------
// Add meal modal
// ---------------------------------------------------------------------------
function openAddMealModal(type) {
  document.getElementById('modal-meal-type').value = type;
  document.getElementById('modal-meal-name').value = '';
  document.getElementById('add-meal-modal').showModal();
}

async function handleAddMealSubmit(e) {
  e.preventDefault();
  const type = document.getElementById('modal-meal-type').value;
  const name = document.getElementById('modal-meal-name').value.trim() || null;
  try {
    await api.createMeal({ log_date: currentDate, meal_type: type, name, items: [] });
    document.getElementById('add-meal-modal').close();
    await loadDay();
  } catch (err) {
    showToast('Failed to add meal: ' + err.message, 'error');
  }
}

// ---------------------------------------------------------------------------
// Add / edit item modal
// ---------------------------------------------------------------------------
function openAddItemModal(mealId) {
  editingItem = null;
  document.getElementById('item-modal-title').textContent = 'Add Item';
  document.getElementById('item-meal-id').value = mealId;
  resetItemForm();
  document.getElementById('item-modal').showModal();
}

function openEditItemModal(mealId, itemId) {
  const meal = dayLog.meals.find(m => m.id === mealId);
  const item = meal?.items.find(i => i.id === itemId);
  if (!item) return;
  editingItem = { mealId, itemId };
  document.getElementById('item-modal-title').textContent = 'Edit Item';
  document.getElementById('item-meal-id').value = mealId;
  document.getElementById('item-name').value = item.name;
  document.getElementById('item-quantity').value = item.quantity ?? '';
  document.getElementById('item-unit').value = item.unit ?? '';
  document.getElementById('item-calories').value = item.calories ?? '';
  document.getElementById('item-protein').value = item.protein_g ?? '';
  document.getElementById('item-carbs').value = item.carbs_g ?? '';
  document.getElementById('item-fat').value = item.fat_g ?? '';
  document.getElementById('item-modal').showModal();
}

async function handleItemFormSubmit(e) {
  e.preventDefault();
  const mealId = document.getElementById('item-meal-id').value;
  const payload = {
    name: document.getElementById('item-name').value.trim(),
    quantity: parseFloatOrNull('item-quantity'),
    unit: document.getElementById('item-unit').value.trim() || null,
    calories: parseFloatOrNull('item-calories'),
    protein_g: parseFloatOrNull('item-protein'),
    carbs_g: parseFloatOrNull('item-carbs'),
    fat_g: parseFloatOrNull('item-fat'),
    source: 'manual',
  };
  try {
    if (editingItem) {
      await api.updateMealItem(mealId, editingItem.itemId, payload);
    } else {
      await api.addMealItem(mealId, payload);
    }
    document.getElementById('item-modal').close();
    await loadDay();
  } catch (err) {
    showToast('Failed to save item: ' + err.message, 'error');
  }
}

function resetItemForm() {
  ['item-name', 'item-quantity', 'item-unit', 'item-calories', 'item-protein', 'item-carbs', 'item-fat']
    .forEach(id => { document.getElementById(id).value = ''; });
}

// ---------------------------------------------------------------------------
// Actions (called via window._nutrition)
// ---------------------------------------------------------------------------
async function deleteMeal(mealId) {
  if (!confirm('Delete this meal and all its items?')) return;
  try {
    await api.deleteMeal(mealId);
    await loadDay();
  } catch (err) {
    showToast('Failed to delete meal: ' + err.message, 'error');
  }
}

async function deleteItem(mealId, itemId) {
  try {
    await api.deleteMealItem(mealId, itemId);
    await loadDay();
  } catch (err) {
    showToast('Failed to delete item: ' + err.message, 'error');
  }
}

async function confirmItem(mealId, itemId) {
  try {
    await api.confirmMealItems(mealId, [itemId]);
    await loadDay();
  } catch (err) {
    showToast('Failed to confirm item: ' + err.message, 'error');
  }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function emptyTotals() {
  return { calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0, meal_count: 0, item_count: 0, confidence_score: 1 };
}

function parseFloatOrNull(id) {
  const v = document.getElementById(id).value;
  return v === '' ? null : parseFloat(v);
}

function escHtml(str) {
  return String(str).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function showLoading(on) {
  document.getElementById('loading-indicator')?.classList.toggle('hidden', !on);
  document.getElementById('meals-container')?.classList.toggle('opacity-50', on);
}

function showToast(msg, type = 'info') {
  window.showToast?.(msg, type) ?? console.warn(msg);
}

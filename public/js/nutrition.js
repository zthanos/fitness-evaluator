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

    initPhotoAnalysis();
    initFoodSearch();
    initTemplates();
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
          <button class="btn btn-xs btn-ghost" onclick="window._nutrition.saveAsTemplate('${meal.id}')">💾</button>
          <button class="btn btn-xs btn-ghost text-error" onclick="window._nutrition.deleteMeal('${meal.id}')">✕</button>
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
// Food search
// ---------------------------------------------------------------------------

function initFoodSearch() {
  document.getElementById('search-submit-btn').addEventListener('click', handleFoodSearchWithCapture);
  document.getElementById('search-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') handleFoodSearchWithCapture();
  });
  document.getElementById('search-modal').addEventListener('toggle', () => populateSearchMealSelect());
  window._nutrition.addSearchProduct = addSearchProduct;
}

function populateSearchMealSelect() {
  const select = document.getElementById('search-target-meal');
  if (!dayLog?.meals?.length) {
    select.innerHTML = '<option value="">— No meals yet (add one first) —</option>';
    return;
  }
  select.innerHTML = dayLog.meals.map(m =>
    `<option value="${m.id}">${MEAL_ICONS[m.meal_type]} ${m.meal_type}${m.name ? ' – ' + m.name : ''}</option>`
  ).join('');
}

function renderProductCard(product, idx) {
  const cal = product.calories_per_100g != null ? `${product.calories_per_100g} kcal` : '?';
  const p = product.protein_per_100g != null ? `P ${product.protein_per_100g}g` : '';
  const c = product.carbs_per_100g != null ? `C ${product.carbs_per_100g}g` : '';
  const f = product.fat_per_100g != null ? `F ${product.fat_per_100g}g` : '';
  return `
    <div class="border border-base-300 rounded-lg p-3">
      <div class="flex justify-between items-start gap-2">
        <div class="min-w-0">
          <div class="font-medium text-sm truncate">${escHtml(product.name)}</div>
          ${product.brand ? `<div class="text-xs text-base-content/50">${escHtml(product.brand)}</div>` : ''}
          <div class="text-xs text-base-content/60 mt-1">per 100g: ${cal} · ${p} · ${c} · ${f}</div>
        </div>
        <div class="shrink-0 flex flex-col items-end gap-1">
          <div class="flex items-center gap-1">
            <input type="number" class="input input-xs input-bordered w-20" placeholder="qty (g)" id="search-qty-${idx}" value="100">
          </div>
          <button class="btn btn-xs btn-primary" onclick="window._nutrition.addSearchProduct(${idx})">Add</button>
        </div>
      </div>
    </div>`;
}

// Store last search results so addSearchProduct can access them by index
let _lastSearchResults = [];

async function handleFoodSearchWithCapture() {
  const q = document.getElementById('search-input').value.trim();
  if (q.length < 2) { showToast('Enter at least 2 characters', 'warning'); return; }

  const resultsEl = document.getElementById('search-results');
  resultsEl.innerHTML = '<span class="loading loading-spinner loading-sm"></span>';

  try {
    const products = await api.searchFood(q);
    _lastSearchResults = products;
    if (!products.length) {
      resultsEl.innerHTML = '<p class="text-sm text-base-content/60">No results found.</p>';
      return;
    }
    resultsEl.innerHTML = products.map((p, idx) => renderProductCard(p, idx)).join('');
  } catch (err) {
    resultsEl.innerHTML = `<p class="text-sm text-error">Search failed: ${escHtml(err.message)}</p>`;
  }
}

async function addSearchProduct(productIdx) {
  const product = _lastSearchResults[productIdx];
  if (!product) return;

  const mealId = document.getElementById('search-target-meal').value;
  if (!mealId) { showToast('Select a meal first', 'warning'); return; }

  const qty = parseFloat(document.getElementById(`search-qty-${productIdx}`)?.value || '100');
  const scale = qty / 100;

  const item = {
    name: product.name + (product.brand ? ` (${product.brand})` : ''),
    quantity: qty,
    unit: 'g',
    calories: product.calories_per_100g != null ? Math.round(product.calories_per_100g * scale) : null,
    protein_g: product.protein_per_100g != null ? Math.round(product.protein_per_100g * scale * 10) / 10 : null,
    carbs_g: product.carbs_per_100g != null ? Math.round(product.carbs_per_100g * scale * 10) / 10 : null,
    fat_g: product.fat_per_100g != null ? Math.round(product.fat_per_100g * scale * 10) / 10 : null,
    source: 'product_search',
    confidence: 1.0,
    source_ref: product.source_url,
  };

  try {
    await api.addMealItem(mealId, item);
    showToast(`Added ${product.name}`, 'success');
    await loadDay();
  } catch (err) {
    showToast('Failed to add product: ' + err.message, 'error');
  }
}

// ---------------------------------------------------------------------------
// Photo analysis
// ---------------------------------------------------------------------------
let _photoAnalysisResult = null; // holds MealAnalysisResult between steps

function initPhotoAnalysis() {
  document.getElementById('analyze-photo-btn').addEventListener('click', handleAnalyzePhoto);
  document.getElementById('confirm-photo-btn').addEventListener('click', handleConfirmPhoto);
  document.getElementById('photo-back-btn').addEventListener('click', () => {
    document.getElementById('photo-results-area').classList.add('hidden');
    document.getElementById('photo-form-area').classList.remove('hidden');
    _photoAnalysisResult = null;
  });
}

async function handleAnalyzePhoto() {
  const fileInput = document.getElementById('photo-file-input');
  if (!fileInput.files[0]) { showToast('Please select a photo first', 'warning'); return; }

  const btn = document.getElementById('analyze-photo-btn');
  btn.disabled = true;
  btn.textContent = 'Analyzing…';

  try {
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fd.append('meal_type', document.getElementById('photo-meal-type').value);
    _photoAnalysisResult = await api.analyzeMealPhoto(fd);

    renderPhotoResults(_photoAnalysisResult);
    document.getElementById('photo-form-area').classList.add('hidden');
    document.getElementById('photo-results-area').classList.remove('hidden');
  } catch (err) {
    showToast('Photo analysis failed: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Analyze';
  }
}

function renderPhotoResults(result) {
  const container = document.getElementById('photo-items-list');
  if (!result.items?.length) {
    container.innerHTML = '<p class="text-sm text-base-content/60">No food items detected. Try a clearer photo.</p>';
    return;
  }

  container.innerHTML = result.items.map((item, idx) => `
    <div class="border border-base-300 rounded-lg p-3" data-item-idx="${idx}">
      <div class="flex justify-between items-start mb-1">
        <span class="font-medium text-sm">${escHtml(item.name)}</span>
        <span class="badge badge-sm ${item.confidence >= 0.7 ? 'badge-success' : 'badge-warning'}">
          ${Math.round(item.confidence * 100)}%
        </span>
      </div>
      ${item.calories != null ? `<div class="text-xs text-base-content/60 mb-1">${item.calories} kcal · P ${item.protein_g ?? '?'}g · C ${item.carbs_g ?? '?'}g · F ${item.fat_g ?? '?'}g</div>` : ''}
      ${item.needs_confirmation && item.clarification_question ? `
        <div class="text-xs text-warning mt-1">❓ ${escHtml(item.clarification_question)}</div>
        <input type="text" class="input input-xs input-bordered mt-1 w-full photo-clarification"
               placeholder="Your answer (optional)" data-item-idx="${idx}">
      ` : ''}
      <div class="flex items-center gap-2 mt-2">
        <label class="text-xs">Qty:</label>
        <input type="number" step="any" value="${item.quantity ?? ''}" class="input input-xs input-bordered w-20 photo-qty" data-item-idx="${idx}">
        <span class="text-xs">${item.unit ?? ''}</span>
        <label class="cursor-pointer flex items-center gap-1 ml-auto text-xs">
          <input type="checkbox" class="checkbox checkbox-xs photo-include" data-item-idx="${idx}" checked>
          Include
        </label>
      </div>
    </div>`).join('');
}

async function handleConfirmPhoto() {
  if (!_photoAnalysisResult) return;
  const mealType = document.getElementById('photo-meal-type').value;

  // Collect user adjustments
  const items = _photoAnalysisResult.items
    .filter((_, idx) => document.querySelector(`.photo-include[data-item-idx="${idx}"]`)?.checked)
    .map((item, idx) => {
      const qty = document.querySelector(`.photo-qty[data-item-idx="${idx}"]`)?.value;
      return {
        name: item.name,
        quantity: qty ? parseFloat(qty) : item.quantity,
        unit: item.unit,
        calories: item.calories,
        protein_g: item.protein_g,
        carbs_g: item.carbs_g,
        fat_g: item.fat_g,
        source: 'ai',
        confidence: item.confidence,
        needs_confirmation: item.needs_confirmation,
      };
    });

  if (!items.length) { showToast('No items selected', 'warning'); return; }

  try {
    await api.createMeal({ log_date: currentDate, meal_type: mealType, items });
    document.getElementById('photo-modal').close();
    document.getElementById('photo-results-area').classList.add('hidden');
    document.getElementById('photo-form-area').classList.remove('hidden');
    document.getElementById('photo-file-input').value = '';
    _photoAnalysisResult = null;
    await loadDay();
  } catch (err) {
    showToast('Failed to save meal: ' + err.message, 'error');
  }
}

// ---------------------------------------------------------------------------
// Meal templates
// ---------------------------------------------------------------------------
let _templates = [];

function initTemplates() {
  window._nutrition.saveAsTemplate = saveCurrentMealAsTemplate;
  window._nutrition.applyTemplate = applyTemplate;
  window._nutrition.deleteTemplate = deleteTemplate;
  document.getElementById('templates-modal').addEventListener('toggle', loadTemplates);
}

async function loadTemplates() {
  const container = document.getElementById('templates-list');
  container.innerHTML = '<span class="loading loading-spinner loading-sm"></span>';
  try {
    _templates = await api.listMealTemplates();
    renderTemplates();
  } catch (err) {
    container.innerHTML = `<p class="text-sm text-error">Failed to load: ${escHtml(err.message)}</p>`;
  }
}

function renderTemplates() {
  const container = document.getElementById('templates-list');
  if (!_templates.length) {
    container.innerHTML = '<p class="text-sm text-base-content/40 italic">No templates saved yet. Save a meal as template using the meal actions.</p>';
    return;
  }

  // Build apply-to-meal selector options
  const mealOptions = dayLog?.meals?.length
    ? dayLog.meals.map(m =>
        `<option value="${m.id}">${MEAL_ICONS[m.meal_type]} ${m.meal_type}${m.name ? ' – ' + m.name : ''}</option>`
      ).join('')
    : '<option value="">No meals today yet</option>';

  container.innerHTML = _templates.map((t, idx) => `
    <div class="border border-base-300 rounded-lg p-3">
      <div class="flex justify-between items-center mb-2">
        <div>
          <span class="font-medium text-sm">${escHtml(t.name)}</span>
          ${t.meal_type ? `<span class="badge badge-sm badge-ghost ml-1">${t.meal_type}</span>` : ''}
          <span class="text-xs text-base-content/50 ml-1">${t.items.length} items</span>
        </div>
        <button class="btn btn-xs btn-ghost text-error" onclick="window._nutrition.deleteTemplate('${t.id}')">✕</button>
      </div>
      <div class="flex gap-2 items-center">
        <select class="select select-xs select-bordered flex-1" id="template-target-${idx}">
          <option value="">New meal</option>
          ${mealOptions}
        </select>
        <button class="btn btn-xs btn-primary" onclick="window._nutrition.applyTemplate('${t.id}', ${idx})">
          Add to log
        </button>
      </div>
    </div>`).join('');
}

async function applyTemplate(templateId, idx) {
  const template = _templates.find(t => t.id === templateId);
  if (!template) return;

  const targetMealId = document.getElementById(`template-target-${idx}`)?.value;

  try {
    if (targetMealId) {
      // Add items to an existing meal
      for (const item of template.items) {
        await api.addMealItem(targetMealId, { ...item, source: 'template' });
      }
    } else {
      // Create a new meal with the template items
      await api.createMeal({
        log_date: currentDate,
        meal_type: template.meal_type || 'snack',
        name: template.name,
        items: template.items.map(i => ({ ...i, source: 'template' })),
      });
    }
    document.getElementById('templates-modal').close();
    showToast(`Applied template: ${template.name}`, 'success');
    await loadDay();
  } catch (err) {
    showToast('Failed to apply template: ' + err.message, 'error');
  }
}

async function saveCurrentMealAsTemplate(mealId) {
  const meal = dayLog.meals.find(m => m.id === mealId);
  if (!meal) return;

  const name = prompt('Template name:', meal.name || meal.meal_type);
  if (!name) return;

  try {
    await api.createMealTemplate({
      name,
      meal_type: meal.meal_type,
      items: meal.items.map(i => ({
        name: i.name,
        quantity: i.quantity,
        unit: i.unit,
        calories: i.calories,
        protein_g: i.protein_g,
        carbs_g: i.carbs_g,
        fat_g: i.fat_g,
        source: 'manual',
        confidence: 1.0,
        needs_confirmation: false,
      })),
    });
    showToast(`Saved template: ${name}`, 'success');
  } catch (err) {
    showToast('Failed to save template: ' + err.message, 'error');
  }
}

async function deleteTemplate(templateId) {
  if (!confirm('Delete this template?')) return;
  try {
    await api.deleteMealTemplate(templateId);
    await loadTemplates();
  } catch (err) {
    showToast('Failed to delete template: ' + err.message, 'error');
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

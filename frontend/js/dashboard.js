/**
 * dashboard.js — Orchestrates the FreshCast dashboard.
 *
 * On load:
 *   1. Fetch all products → populate dropdown + KPI cards + category chart
 *   2. Load forecast for the first product → main chart
 *   3. Build risk table across all products
 *
 * User interactions:
 *   - Product dropdown change → reload forecast chart
 *   - Days selector change   → reload forecast chart
 *   - "Retrain" button       → POST /retrain, show result in toast
 */

// ── State ─────────────────────────────────────────────────────────────────

let allProducts  = [];
let modelInfo    = {};
let currentPid   = null;
let forecastDays = 7;
let _chartRequestId = 0;  // increments on every product switch; stale responses are ignored
let _rebuildDropdownOptions = null;  // set by populateDropdown, used by dictionary clicks
const CATEGORY_COLORS = {};
const PALETTE = ['#00c853','#40c4ff','#ffab40','#ff5252','#b388ff','#ea80fc','#69f0ae','#ff80ab'];
let paletteIdx = 0;

function colorForCategory(cat) {
  if (!CATEGORY_COLORS[cat]) CATEGORY_COLORS[cat] = PALETTE[paletteIdx++ % PALETTE.length];
  return CATEGORY_COLORS[cat];
}

// ── Initialisation ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  showToast('Loading FreshCast…', 'info');
  await init();
});

async function init() {
  try {
    const [products, info] = await Promise.all([fetchProducts(), fetchModelInfo()]);
    allProducts = products;
    modelInfo   = info;

    populateDropdown(products);
    renderKpis(products, info);
    renderCategoryChart('category-chart', products);
    renderProductDictionary(products);
    updateModelBadge(info);

    if (products.length > 0) {
      currentPid = products[0].product_id;
      document.getElementById('product-select').value = currentPid;
      await loadForecastAndHistory(currentPid);
    }

    await buildRiskTable(products);
  } catch (err) {
    showToast(`Failed to load dashboard: ${err.message}`, 'error');
    console.error(err);
  }
}

// ── KPI Cards ─────────────────────────────────────────────────────────────

function renderKpis(products, info) {
  document.getElementById('kpi-products').textContent = products.length;

  if (info && info.mae != null) {
    const avgUnits = 20; // rough baseline for % display (refined after history loads)
    const acc = Math.max(0, Math.min(100, 100 - (info.mae / avgUnits) * 100));
    document.getElementById('kpi-accuracy').textContent = acc.toFixed(1) + '%';
    document.getElementById('kpi-mae').textContent = `MAE ${info.mae.toFixed(2)} units`;
    if (info.trained_at) {
      document.getElementById('last-updated').textContent =
        'Last trained: ' + new Date(info.trained_at).toLocaleString();
    }
  } else {
    document.getElementById('kpi-accuracy').textContent = '—';
    document.getElementById('kpi-mae').textContent = 'No model yet';
  }
}

// ── Dropdown ──────────────────────────────────────────────────────────────

function populateDropdown(products) {
  const sel        = document.getElementById('product-select');
  const searchInput = document.getElementById('product-search');
  const clearBtn   = document.getElementById('search-clear');

  function rebuildOptions(filtered) {
    sel.innerHTML = '';
    filtered.forEach(p => {
      const opt = document.createElement('option');
      opt.value       = p.product_id;
      opt.textContent = `${p.name}  (${p.category || '?'})`;
      sel.appendChild(opt);
    });
  }

  _rebuildDropdownOptions = rebuildOptions;
  rebuildOptions(products);

  sel.addEventListener('change', () => {
    currentPid = sel.value;
    loadForecastAndHistory(currentPid);
  });

  let _searchDebounce = null;

  searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim().toLowerCase();
    clearBtn.style.display = q ? 'block' : 'none';

    const filtered = q
      ? allProducts.filter(p =>
          p.name.toLowerCase().includes(q) ||
          (p.category || '').toLowerCase().includes(q)
        )
      : allProducts;

    rebuildOptions(filtered);

    if (filtered.length > 0) {
      sel.value = filtered[0].product_id;
      clearTimeout(_searchDebounce);
      _searchDebounce = setTimeout(() => {
        currentPid = sel.value;
        loadForecastAndHistory(currentPid);
      }, 380);
    }
  });

  clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    clearBtn.style.display = 'none';
    rebuildOptions(allProducts);
    sel.value = currentPid || (allProducts[0] && allProducts[0].product_id);
  });
}

// ── Main Chart ────────────────────────────────────────────────────────────

function setChartOverlay(show, message) {
  const chartEl = document.getElementById('forecast-chart');
  let overlay = document.getElementById('chart-overlay');
  if (!overlay) {
    // Create overlay once — sits on top of the Plotly canvas without destroying it
    overlay = document.createElement('div');
    overlay.id = 'chart-overlay';
    overlay.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;gap:8px;color:#8b91a8;background:rgba(26,29,39,0.75);border-radius:8px;z-index:10;pointer-events:none';
    chartEl.style.position = 'relative';
    chartEl.appendChild(overlay);
  }
  if (show) {
    overlay.innerHTML = message || '<span class="spinner"></span>&nbsp; Loading forecast…';
    overlay.style.display = 'flex';
  } else {
    overlay.style.display = 'none';
  }
}

async function loadForecastAndHistory(productId) {
  const reqId = ++_chartRequestId;
  setChartOverlay(true);

  try {
    const [histRes, foreRes] = await Promise.all([
      fetchHistory(productId, 90),
      fetchForecast(productId, forecastDays),
    ]);

    if (reqId !== _chartRequestId) return;

    const product = allProducts.find(p => p.product_id === productId) || { name: productId };
    const kpiEl  = document.getElementById('kpi-accuracy');

    if (foreRes.insufficient) {
      renderHistoryOnlyChart('forecast-chart', histRes.history, product.name);
      document.getElementById('forecast-numbers').innerHTML = '';
      kpiEl.textContent = 'Unpredictable';
      kpiEl.style.cssText = 'color:var(--text-muted);font-size:1rem;cursor:default';
      kpiEl.title = 'Demand volume too low for reliable forecasting.';
      document.getElementById('accuracy-gauge').innerHTML =
        '<p style="text-align:center;color:var(--text-muted);font-size:0.82rem;padding:2.5rem 0;line-height:1.6">' +
        'Demand volume too low<br>for reliable forecasting.</p>';
    } else {
      renderForecastChart('forecast-chart', histRes.history, foreRes.forecasts, product.name);
      renderForecastTable('forecast-numbers', product.name, foreRes.forecasts);
      if (histRes.history.length > 0 && modelInfo.mae != null) {
        const avg = histRes.history.reduce((s, d) => s + d.units_sold, 0) / histRes.history.length;
        const acc = Math.max(0, Math.min(100, 100 - (modelInfo.mae / avg) * 100));
        kpiEl.textContent = acc.toFixed(1) + '%';
        kpiEl.style.cssText = '';
        kpiEl.title = '';
        renderAccuracyGauge('accuracy-gauge', modelInfo.mae, avg);
      }
    }

    setChartOverlay(false);
  } catch (err) {
    if (reqId !== _chartRequestId) return;
    setChartOverlay(true, `<span style="color:#ff5252">⚠ ${err.message}</span>`);
    showToast(err.message, 'error');
  }
}

// ── Risk Table ────────────────────────────────────────────────────────────

async function buildRiskTable(products) {
  const tbody       = document.getElementById('risk-tbody');
  const shortageEl  = document.getElementById('kpi-shortage');
  const overstockEl = document.getElementById('kpi-overstock');
  tbody.innerHTML = '<tr><td colspan="5" style="padding:1rem;color:#8b91a8;text-align:center"><span class="spinner"></span> Analysing risk…</td></tr>';

  let shortageCount  = 0;
  let overstockCount = 0;
  const rows = [];

  const sample = products;
  await Promise.all(sample.map(async (p) => {
    try {
      const [hist, fc] = await Promise.all([
        fetchHistory(p.product_id, 7),
        fetchForecast(p.product_id, 7),
      ]);
      if (!hist.history.length || fc.insufficient || !fc.forecasts.length) return;

      const avgHist = hist.history.reduce((s, d) => s + d.units_sold, 0) / hist.history.length;
      const avgFc   = fc.forecasts.reduce((s, d) => s + d.predicted_units, 0) / fc.forecasts.length;
      const ratio   = avgHist > 0 ? avgFc / avgHist : 1;

      let risk = 'ok';
      if (ratio > 1.3)  { risk = 'shortage';  shortageCount++;  }
      if (ratio < 0.7)  { risk = 'overstock'; overstockCount++; }

      rows.push({ product: p, avgHist, avgFc, ratio, risk });
    } catch (_) { /* skip products that error */ }
  }));

  shortageEl.textContent  = shortageCount;
  overstockEl.textContent = overstockCount;

  // Sort: risky products first
  rows.sort((a, b) => {
    const order = { shortage: 0, overstock: 1, ok: 2 };
    return order[a.risk] - order[b.risk];
  });

  tbody.innerHTML = '';
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="padding:1.5rem;color:#8b91a8;text-align:center">No data available yet</td></tr>';
    return;
  }

  rows.forEach(({ product, avgHist, avgFc, ratio, risk }) => {
    const color = colorForCategory(product.category || 'Other');
    const badge = risk === 'shortage'
      ? '<span class="badge badge-shortage">⬆ Shortage risk</span>'
      : risk === 'overstock'
        ? '<span class="badge badge-overstock">⬇ Overstock risk</span>'
        : '<span class="badge badge-ok">✓ Normal</span>';

    const trend = ratio > 1 ? `▲ +${((ratio - 1) * 100).toFixed(0)}%` : `▼ ${((1 - ratio) * 100).toFixed(0)}%`;
    const trendColor = ratio > 1.3 ? '#ff5252' : ratio < 0.7 ? '#ffab40' : '#00c853';

    tbody.innerHTML += `
      <tr>
        <td>
          <div class="product-pill">
            <span class="dot" style="background:${color}"></span>
            <span>${product.name}</span>
          </div>
        </td>
        <td>${product.category || '—'}</td>
        <td style="font-variant-numeric:tabular-nums">${avgHist.toFixed(1)}</td>
        <td style="font-variant-numeric:tabular-nums">${avgFc.toFixed(1)}</td>
        <td style="color:${trendColor};font-weight:600">${trend}</td>
        <td>${badge}</td>
      </tr>`;
  });
}

// ── Retrain ───────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('retrain-btn').addEventListener('click', async () => {
    const btn = document.getElementById('retrain-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Training…';
    showToast('Retraining model… this may take 30–60 seconds.', 'info');

    try {
      const result = await postRetrain();
      modelInfo = await fetchModelInfo();
      renderKpis(allProducts, modelInfo);
      updateModelBadge(modelInfo);
      showToast(`Retrain complete — MAE: ${result.mae.toFixed(2)}, RMSE: ${result.rmse.toFixed(2)}`, 'success');

      // Refresh current chart with new model
      if (currentPid) await loadForecastAndHistory(currentPid);
      await buildRiskTable(allProducts);
    } catch (err) {
      showToast(`Retrain failed: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '↺ Retrain Model';
    }
  });

  document.getElementById('days-select').addEventListener('change', (e) => {
    forecastDays = parseInt(e.target.value);
    if (currentPid) loadForecastAndHistory(currentPid);
  });
});

// ── Helpers ───────────────────────────────────────────────────────────────

function updateModelBadge(info) {
  const badge = document.getElementById('model-badge');
  if (info && info.model_version) {
    badge.textContent = info.model_version;
    badge.title = `MAE: ${info.mae?.toFixed(3)} | RMSE: ${info.rmse?.toFixed(3)}`;
  } else {
    badge.textContent = 'No model';
  }
}

function renderForecastTable(containerId, productName, forecasts) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (!forecasts || forecasts.length === 0) { el.innerHTML = ''; return; }

  const rows = forecasts.map(f => {
    const d = new Date(f.forecast_date);
    const day = d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
    return `
      <tr>
        <td style="padding:0.5rem 1rem;color:#8b91a8;font-size:0.82rem">${day}</td>
        <td style="padding:0.5rem 1rem;font-weight:700;color:#00c853">${f.predicted_units.toFixed(1)}</td>
        <td style="padding:0.5rem 1rem;color:#8b91a8;font-size:0.82rem">${f.confidence_low.toFixed(1)} – ${f.confidence_high.toFixed(1)}</td>
      </tr>`;
  }).join('');

  el.innerHTML = `
    <div style="margin-top:0.75rem;border:1px solid #2e3350;border-radius:8px;overflow:hidden">
      <div style="padding:0.6rem 1rem;background:#232638;font-size:0.75rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#8b91a8;border-bottom:1px solid #2e3350">
        ${productName} — Forecast Numbers
      </div>
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="background:#1a1d27">
            <th style="padding:0.5rem 1rem;text-align:left;font-size:0.72rem;color:#8b91a8;font-weight:600">Date</th>
            <th style="padding:0.5rem 1rem;text-align:left;font-size:0.72rem;color:#8b91a8;font-weight:600">Predicted Units</th>
            <th style="padding:0.5rem 1rem;text-align:left;font-size:0.72rem;color:#8b91a8;font-weight:600">Range (Low – High)</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

// ── Product Dictionary ────────────────────────────────────────────────────

function renderProductDictionary(products) {
  const el = document.getElementById('product-dictionary');
  if (!el) return;

  const shelfColor = (days) => {
    if (!days) return 'var(--text-muted)';
    if (days <= 3)  return 'var(--danger)';
    if (days <= 7)  return 'var(--warning)';
    if (days <= 14) return 'var(--info)';
    return 'var(--accent)';
  };

  // Group by category, sorted alphabetically
  const groups = {};
  products.forEach(p => {
    const cat = p.category || 'Other';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(p);
  });

  let html = '<div class="dict-grid">';
  Object.entries(groups).sort(([a], [b]) => a.localeCompare(b)).forEach(([cat, prods]) => {
    const color = colorForCategory(cat);
    const items = prods.map(p => `
      <div class="dict-item" data-pid="${p.product_id}" title="View forecast for ${p.name}">
        <span class="dict-name">${p.name}</span>
        <div class="dict-meta">
          <span class="dict-shelf" style="color:${shelfColor(p.shelf_life_days)}">${p.shelf_life_days ?? '?'}d</span>
          <span class="dict-unit">${p.unit || 'units'}</span>
        </div>
      </div>`).join('');

    html += `
      <div class="dict-group">
        <div class="dict-group-header">
          <span class="dot" style="background:${color}"></span>
          <span>${cat}</span>
          <span class="dict-count">${prods.length}</span>
        </div>
        ${items}
      </div>`;
  });
  html += '</div>';
  el.innerHTML = html;

  el.querySelectorAll('.dict-item').forEach(item => {
    item.addEventListener('click', () => {
      const pid = item.dataset.pid;
      const searchInput = document.getElementById('product-search');
      const clearBtn    = document.getElementById('search-clear');
      const sel         = document.getElementById('product-select');
      searchInput.value = '';
      clearBtn.style.display = 'none';
      if (_rebuildDropdownOptions) _rebuildDropdownOptions(allProducts);
      sel.value  = pid;
      currentPid = pid;
      loadForecastAndHistory(pid);
      document.querySelector('.grid-2').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  toast.innerHTML = `<span style="font-weight:700">${icon}</span> ${message}`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.transition = 'opacity 0.4s, transform 0.4s';
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(60px)';
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}

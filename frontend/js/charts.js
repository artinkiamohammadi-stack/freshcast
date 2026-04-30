/**
 * charts.js — Plotly chart builders for the FreshCast dashboard.
 *
 * Why Plotly?
 *   - Zero build step: load from CDN, works in plain HTML
 *   - Interactive by default: zoom, pan, hover tooltips
 *   - Great for time-series: built-in date axis handling
 *   - Supports confidence bands (fill between traces)
 */

const COLORS = {
  accent:    '#00c853',
  forecast:  '#40c4ff',
  confBand:  'rgba(64, 196, 255, 0.12)',
  danger:    '#ff5252',
  warning:   '#ffab40',
  surface:   '#1a1d27',
  border:    '#2e3350',
  text:      '#e8eaf0',
  textMuted: '#8b91a8',
};

/** Shared Plotly layout base — dark theme */
function baseLayout(title) {
  return {
    title: { text: title, font: { color: COLORS.text, size: 13 } },
    paper_bgcolor: 'transparent',
    plot_bgcolor:  'transparent',
    font:  { color: COLORS.text, family: 'Inter, system-ui, sans-serif' },
    margin: { t: 40, r: 20, b: 50, l: 55 },
    xaxis: {
      gridcolor: COLORS.border,
      linecolor: COLORS.border,
      tickcolor: COLORS.border,
      tickfont:  { size: 11, color: COLORS.textMuted },
    },
    yaxis: {
      gridcolor: COLORS.border,
      linecolor: COLORS.border,
      tickcolor: COLORS.border,
      tickfont:  { size: 11, color: COLORS.textMuted },
      zeroline:  false,
    },
    legend: {
      bgcolor: 'transparent',
      font: { size: 11, color: COLORS.textMuted },
      orientation: 'h',
      x: 0, y: -0.15,
    },
    hoverlabel: {
      bgcolor: COLORS.surface,
      bordercolor: COLORS.border,
      font: { color: COLORS.text, size: 12 },
    },
  };
}

/**
 * renderForecastChart — Main combo chart: history (solid) + forecast (dashed) + confidence band.
 *
 * @param {string} containerId  DOM element id
 * @param {Array}  history      [{ sale_date, units_sold }]
 * @param {Array}  forecasts    [{ forecast_date, predicted_units, confidence_low, confidence_high }]
 * @param {string} productName
 */
function monthlyAverages(history) {
  const buckets = {};
  history.forEach(d => {
    const key = d.sale_date.substring(0, 7);          // "YYYY-MM"
    if (!buckets[key]) buckets[key] = { sum: 0, n: 0 };
    buckets[key].sum += d.units_sold;
    buckets[key].n++;
  });
  return Object.entries(buckets)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, { sum, n }]) => ({ date: key + '-15', value: sum / n }));
}

function renderForecastChart(containerId, history, forecasts, productName) {
  const histDates  = history.map(d => d.sale_date);
  const histVals   = history.map(d => d.units_sold);

  const fDates     = forecasts.map(d => d.forecast_date);
  const fVals      = forecasts.map(d => d.predicted_units);
  const fLow       = forecasts.map(d => d.confidence_low);
  const fHigh      = forecasts.map(d => d.confidence_high);

  // Connect the last history point to the first forecast point so the line is continuous
  const bridgeDate = histDates.at(-1);
  const bridgeVal  = histVals.at(-1);

  const traces = [
    // ① Confidence band (high → low fill)
    {
      x: [...fDates, ...fDates.slice().reverse()],
      y: [...fHigh,  ...fLow.slice().reverse()],
      fill: 'toself',
      fillcolor: COLORS.confBand,
      line: { width: 0 },
      type: 'scatter',
      mode: 'lines',
      name: 'Confidence band',
      showlegend: true,
      hoverinfo: 'skip',
    },
    // ② Historical sales (solid green line)
    {
      x: histDates,
      y: histVals,
      type: 'scatter',
      mode: 'lines',
      name: 'Actual demand',
      line: { color: COLORS.accent, width: 2 },
      hovertemplate: '%{x}<br>Units sold: <b>%{y:.1f}</b><extra></extra>',
    },
    // ③ Forecast (dashed blue line)
    {
      x: [bridgeDate, ...fDates],
      y: [bridgeVal,  ...fVals],
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Forecast',
      line: { color: COLORS.forecast, width: 2, dash: 'dash' },
      marker: { size: 5, color: COLORS.forecast },
      hovertemplate: '%{x}<br>Predicted: <b>%{y:.1f}</b><extra></extra>',
    },
  ];

  const layout = {
    ...baseLayout(`${productName} — Demand Forecast`),
    shapes: [
      // Vertical separator between history and forecast
      {
        type: 'line', x0: bridgeDate, x1: bridgeDate,
        y0: 0, y1: 1, yref: 'paper',
        line: { color: COLORS.border, width: 1, dash: 'dot' },
      },
    ],
    annotations: [{
      x: bridgeDate, y: 1.02, xref: 'x', yref: 'paper',
      text: 'Today', showarrow: false,
      font: { size: 10, color: COLORS.textMuted },
    }],
  };

  Plotly.react(containerId, traces, layout, { responsive: true, displayModeBar: false });
}

/**
 * renderHistoryOnlyChart — Shows past sales only, with a notice that forecast is unavailable.
 * Used for low-demand products flagged as insufficient by the API.
 */
function renderHistoryOnlyChart(containerId, history, productName) {
  const histDates = history.map(d => d.sale_date);
  const histVals  = history.map(d => d.units_sold);

  const traces = [{
    x: histDates,
    y: histVals,
    type: 'scatter',
    mode: 'lines',
    name: 'Actual demand',
    line: { color: COLORS.accent, width: 2 },
    hovertemplate: '%{x}<br>Units sold: <b>%{y:.1f}</b><extra></extra>',
  }];

  const layout = {
    ...baseLayout(`${productName} — Sales History`),
    annotations: [{
      xref: 'paper', yref: 'paper',
      x: 0.5, y: 0.5,
      text: 'Forecast unavailable — demand volume too low',
      showarrow: false,
      font: { size: 12, color: COLORS.textMuted },
      bgcolor: 'rgba(26,29,39,0.85)',
      bordercolor: COLORS.border,
      borderwidth: 1,
      borderpad: 10,
    }],
  };

  Plotly.react(containerId, traces, layout, { responsive: true, displayModeBar: false });
}

/**
 * renderCategoryChart — Donut chart of product counts by category.
 *
 * @param {string} containerId
 * @param {Array}  products  [{ category }]
 */
function renderCategoryChart(containerId, products) {
  const counts = {};
  products.forEach(p => {
    const cat = p.category || 'Other';
    counts[cat] = (counts[cat] || 0) + 1;
  });

  const palette = ['#00c853','#40c4ff','#ffab40','#ff5252','#b388ff','#ea80fc','#69f0ae'];

  const trace = {
    labels:  Object.keys(counts),
    values:  Object.values(counts),
    type:    'pie',
    hole:    0.55,
    marker:  { colors: palette },
    textinfo: 'label+percent',
    textfont: { size: 11, color: COLORS.text },
    hovertemplate: '<b>%{label}</b><br>%{value} products<extra></extra>',
  };

  const layout = {
    ...baseLayout('Products by Category'),
    margin:  { t: 40, r: 10, b: 10, l: 10 },
    showlegend: false,
  };

  Plotly.react(containerId, [trace], layout, { responsive: true, displayModeBar: false });
}

/**
 * renderAccuracyGauge — Simple horizontal bar showing model accuracy (100 - MAE%).
 *
 * @param {string} containerId
 * @param {number} mae   Mean Absolute Error
 * @param {number} avg   Average units sold (to compute % accuracy)
 */
function renderAccuracyGauge(containerId, mae, avg) {
  if (!avg || avg === 0) { document.getElementById(containerId).innerHTML = ''; return; }
  const accuracy = Math.max(0, Math.min(100, 100 - (mae / avg) * 100));
  const color = accuracy >= 80 ? COLORS.accent : accuracy >= 60 ? COLORS.warning : COLORS.danger;

  const trace = {
    type: 'indicator',
    mode: 'gauge+number',
    value: accuracy,
    number: { suffix: '%', font: { size: 22, color: COLORS.text } },
    gauge: {
      axis: { range: [0, 100], tickfont: { size: 10, color: COLORS.textMuted } },
      bar:  { color },
      bgcolor: COLORS.surface,
      bordercolor: COLORS.border,
      steps: [
        { range: [0,  60],  color: 'rgba(255,82,82,0.08)' },
        { range: [60, 80],  color: 'rgba(255,171,64,0.08)' },
        { range: [80, 100], color: 'rgba(0,200,83,0.08)' },
      ],
    },
  };

  const layout = {
    paper_bgcolor: 'transparent',
    font: { color: COLORS.text },
    margin: { t: 15, r: 25, b: 25, l: 25 },
  };

  Plotly.react(containerId, [trace], layout, { responsive: true, displayModeBar: false });
}

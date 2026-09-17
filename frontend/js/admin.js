/* ============================================================
   admin.js — Admin Analytics Dashboard Logic
   Uses Chart.js (loaded via CDN in admin.html)
   ============================================================ */

const API = window.location.origin;

// ─── State ────────────────────────────────────────────────────
let routes = [];
let selectedRouteId = null;
let charts = {};
let currentTab = 'overview';

// ─── Initialise ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadOverview();
  await loadRoutes();
  await loadRankings();
  await loadDeteriorationAlerts();
  await loadGlobalCategories();
  await loadGlobalTrend();
  initTabSwitching();
  initRouteFilter();
  setInterval(loadOverview, 30000); // refresh KPIs every 30s
});

// ─── Overview KPIs ─────────────────────────────────────────────
async function loadOverview() {
  try {
    const res = await fetch(`${API}/analytics/overview`);
    const d = await res.json();
    setKpi('kpi-total-feedback', d.total_feedback.toLocaleString());
    setKpi('kpi-avg-rating',     d.platform_avg_rating.toFixed(2));
    setKpi('kpi-routes',         d.total_routes);
    setKpi('kpi-alerts',         d.routes_with_alerts);
    setKpi('kpi-critical',       d.critical_alerts);
    setKpi('kpi-user-submitted', d.user_submitted.toLocaleString());
    updateRatingBadge(d.platform_avg_rating);
    updateLastRefreshed();
  } catch (e) {
    console.warn('Overview failed:', e);
  }
}

function setKpi(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function updateRatingBadge(rating) {
  const el = document.getElementById('platform-rating-badge');
  if (!el) return;
  el.textContent = rating.toFixed(1);
  if (rating >= 4)      el.className = 'kpi-value gradient-text';
  else if (rating >= 3) el.className = 'kpi-value gradient-text-blue';
  else { el.className = 'kpi-value'; el.style.color = '#ef233c'; }
}

function updateLastRefreshed() {
  const el = document.getElementById('last-refreshed');
  if (!el) return;
  const now = new Date();
  el.textContent = `Last refreshed at ${now.toLocaleTimeString()}`;
}

// ─── Load routes into filter ────────────────────────────────────
async function loadRoutes() {
  try {
    const res = await fetch(`${API}/routes/`);
    routes = await res.json();
    populateRouteDropdown('route-filter', routes, 'All Routes');
    populateRouteDropdown('trend-route-filter', routes, 'All Routes');
    populateRouteDropdown('heatmap-route-filter', routes);
  } catch (e) {
    console.warn('Route load failed:', e);
  }
}

function populateRouteDropdown(id, routes, defaultLabel) {
  const sel = document.getElementById(id);
  if (!sel) return;
  if (defaultLabel) {
    sel.innerHTML = `<option value="">— ${defaultLabel} —</option>`;
  } else {
    sel.innerHTML = '';
  }
  routes.forEach(r => {
    const opt = document.createElement('option');
    opt.value = r.id;
    opt.textContent = `${r.route_number} — ${r.route_name}`;
    sel.appendChild(opt);
  });
}

// ─── Route Rankings ─────────────────────────────────────────────
async function loadRankings(search = '', borough = '') {
  const tbody = document.getElementById('rankings-tbody');
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="7" class="loading-overlay"><div class="spinner"></div></td></tr>`;

  try {
    const res = await fetch(`${API}/analytics/rankings`);
    let data = await res.json();

    if (search) {
      data = data.filter(r =>
        r.route_number.toLowerCase().includes(search.toLowerCase()) ||
        r.route_name.toLowerCase().includes(search.toLowerCase()) ||
        r.borough.toLowerCase().includes(search.toLowerCase())
      );
    }
    if (borough) {
      data = data.filter(r => r.borough.toLowerCase() === borough.toLowerCase());
    }

    if (!data.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="color:var(--text-muted);padding:24px;text-align:center">No routes match the current filter.</td></tr>';
      return;
    }

    tbody.innerHTML = data.map(r => `
      <tr>
        <td><span class="badge badge-muted">#${r.rank}</span></td>
        <td>
          <div style="display:flex;align-items:center;gap:10px;">
            <div class="score-badge ${scoreClass(r.composite_score)}">
              ${r.composite_score.toFixed(1)}
            </div>
            <div>
              <div style="font-weight:700;">${r.route_number}</div>
              <div style="font-size:0.78rem;color:var(--text-muted)">${r.route_name}</div>
            </div>
          </div>
        </td>
        <td><span class="badge badge-blue">${r.borough}</span></td>
        <td>${renderStars(r.overall_rating)}</td>
        <td>${r.total_feedback.toLocaleString()}</td>
        <td>${trendBadge(r.trend)}</td>
        <td>
          <button class="btn btn-ghost btn-sm" onclick="drillDown(${r.route_id}, '${r.route_number}')">
            Analyse →
          </button>
        </td>
      </tr>
    `).join('');

  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="7" style="color:var(--danger);padding:20px">Failed to load rankings.</td></tr>';
  }
}

function renderStars(rating) {
  const full  = Math.floor(rating);
  const half  = rating % 1 >= 0.5 ? 1 : 0;
  const empty = 5 - full - half;
  const star  = '<span style="color:#ffd60a">★</span>';
  const half_ = '<span style="color:#ffd60a">½</span>';
  const emp   = '<span style="color:#4a5a78">★</span>';
  return star.repeat(full) + (half ? half_ : '') + emp.repeat(empty) +
    `<span style="margin-left:6px;color:var(--text-secondary);font-size:0.8rem">${rating.toFixed(1)}</span>`;
}

function trendBadge(trend) {
  const map = {
    improving: '<span class="badge badge-success">↑ Improving</span>',
    declining: '<span class="badge badge-danger">↓ Declining</span>',
    stable:    '<span class="badge badge-muted">→ Stable</span>',
  };
  return map[trend] || trend;
}

function scoreClass(score) {
  if (score >= 4)   return 'score-great';
  if (score >= 3)   return 'score-good';
  if (score >= 2)   return 'score-fair';
  return 'score-poor';
}

// ─── Deterioration Alerts ──────────────────────────────────────
async function loadDeteriorationAlerts() {
  const container = document.getElementById('alerts-container');
  if (!container) return;

  try {
    const res = await fetch(`${API}/analytics/deterioration`);
    const alerts = await res.json();

    if (!alerts.length) {
      container.innerHTML = `<div class="alert alert-success">
        <span>✓</span><span>No deteriorating routes detected this period.</span>
      </div>`;
      return;
    }

    container.innerHTML = alerts.map(a => `
      <div class="alert-card ${a.severity === 'critical' ? 'alert-card-critical' : 'alert-card-warning'}">
        <div class="alert-card-header">
          <div>
            <span class="badge ${a.severity === 'critical' ? 'badge-danger' : 'badge-warning'}">
              ${a.severity.toUpperCase()}
            </span>
            <span style="font-weight:700;margin-left:8px">${a.route_number}</span>
            <span style="color:var(--text-muted)"> — ${a.route_name}</span>
          </div>
          <span class="badge badge-blue">${a.borough}</span>
        </div>
        <div class="alert-card-body">
          <div class="alert-stat">
            <span class="alert-stat-label">Current (30d)</span>
            <span class="alert-stat-value" style="color:var(--danger)">${a.score_30d.toFixed(2)}</span>
          </div>
          <div class="alert-stat">
            <span class="alert-stat-label">Previous (30d)</span>
            <span class="alert-stat-value">${a.score_prev_30d.toFixed(2)}</span>
          </div>
          <div class="alert-stat">
            <span class="alert-stat-label">Δ Change</span>
            <span class="alert-stat-value" style="color:var(--danger)">${a.delta.toFixed(2)}</span>
          </div>
          <button class="btn btn-ghost btn-sm" onclick="drillDown(${a.route_id}, '${a.route_number}')">
            Investigate →
          </button>
        </div>
      </div>
    `).join('');

  } catch (e) {
    container.innerHTML = '<div class="alert alert-error"><span>✕</span><span>Failed to load alerts.</span></div>';
  }
}

// ─── Category Breakdown Chart ──────────────────────────────────
async function loadGlobalCategories() {
  try {
    const res = await fetch(`${API}/analytics/categories`);
    const data = await res.json();
    renderCategoryChart('cat-chart', data);
  } catch (e) {
    console.warn('Category chart failed:', e);
  }
}

async function loadRouteCategories(routeId) {
  try {
    const res = await fetch(`${API}/analytics/categories/${routeId}`);
    const data = await res.json();
    renderCategoryChart('cat-chart', data);
    renderCategoryTable(data);
  } catch (e) {}
}

function renderCategoryChart(canvasId, data) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !data.length) return;

  const COLORS = [
    '#0057A8','#00A1DE','#1a7f4b','#b45309',
    '#c0392b','#6c3483','#1a5276','#0e6655',
  ];

  if (charts[canvasId]) charts[canvasId].destroy();

  charts[canvasId] = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: data.map(d => d.category),
      datasets: [{
        label: 'Complaints',
        data: data.map(d => d.count),
        backgroundColor: COLORS.slice(0, data.length).map(c => c + 'cc'),
        borderColor: COLORS.slice(0, data.length),
        borderWidth: 2,
        borderRadius: 8,
        borderSkipped: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a2633',
          borderColor: 'rgba(0,87,168,0.3)',
          borderWidth: 1,
          cornerRadius: 10,
          padding: 12,
          titleColor: '#f5f7fa',
          bodyColor: '#9ba8b6',
          callbacks: {
            label: ctx => ` ${ctx.raw} complaints (${data[ctx.dataIndex].percentage}%)`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: '#6e7d8f', font: { family: 'Inter', size: 11 } },
          grid: { color: 'rgba(0,0,0,0.04)' },
        },
        y: {
          ticks: { color: '#6e7d8f', font: { family: 'Inter', size: 11 } },
          grid: { color: 'rgba(0,0,0,0.04)' },
        },
      },
    },
  });
}

function renderCategoryTable(data) {
  const table = document.getElementById('cat-table');
  if (!table) return;
  table.innerHTML = data.map((d, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><span class="badge badge-orange">${d.category}</span></td>
      <td>${d.count}</td>
      <td>
        <div class="progress-bar" style="width:120px">
          <div class="progress-fill" style="width:${d.percentage}%"></div>
        </div>
        <span style="font-size:0.78rem;color:var(--text-muted)">${d.percentage}%</span>
      </td>
      <td>${severityBadge(d.avg_severity_score)}</td>
    </tr>
  `).join('');
}

function severityBadge(score) {
  if (score >= 2.5) return '<span class="badge sev-high">HIGH</span>';
  if (score >= 1.5) return '<span class="badge sev-medium">MEDIUM</span>';
  return '<span class="badge sev-low">LOW</span>';
}

// ─── Rating Trend Chart ────────────────────────────────────────
async function loadGlobalTrend(routeId = null) {
  let url = routeId
    ? `${API}/analytics/trend?route_id=${routeId}&months=8`
    : `${API}/analytics/trend?months=8`;
  try {
    const res = await fetch(url);
    const data = await res.json();
    renderTrendChart(data);
  } catch (e) {
    console.warn('Trend chart failed:', e);
  }
}

function renderTrendChart(data) {
  const canvas = document.getElementById('trend-chart');
  if (!canvas || !data.length) return;

  if (charts['trend']) charts['trend'].destroy();

  charts['trend'] = new Chart(canvas, {
    type: 'line',
    data: {
      labels: data.map(d => {
        const [y, m] = d.month.split('-');
        return new Date(y, m - 1).toLocaleString('default', { month: 'short', year: '2-digit' });
      }),
      datasets: [{
        label: 'Avg Rating',
        data: data.map(d => d.avg_rating),
        borderColor: '#0057A8',
        backgroundColor: 'rgba(0,87,168,0.06)',
        pointBackgroundColor: '#0057A8',
        pointBorderColor: '#0057A8',
        pointRadius: 5,
        pointHoverRadius: 8,
        fill: true,
        tension: 0.4,
        borderWidth: 2.5,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1a2633',
          borderColor: 'rgba(0,87,168,0.3)',
          borderWidth: 1,
          cornerRadius: 10,
          padding: 12,
          titleColor: '#f5f7fa',
          bodyColor: '#9ba8b6',
          callbacks: {
            label: ctx => ` Rating: ${ctx.raw.toFixed(2)} / 5`,
            afterLabel: (ctx) => ` Submissions: ${data[ctx.dataIndex].count}`,
          },
        },
      },
      scales: {
        x: {
          ticks: { color: '#6e7d8f', font: { family: 'Inter', size: 11 } },
          grid: { color: 'rgba(0,0,0,0.04)' },
        },
        y: {
          min: 1, max: 5,
          ticks: { color: '#6e7d8f', font: { family: 'Inter', size: 11 }, stepSize: 0.5 },
          grid: { color: 'rgba(0,0,0,0.04)' },
        },
      },
    },
  });
}

// ─── Time Heatmap ──────────────────────────────────────────────
async function loadHeatmap(routeId) {
  const container = document.getElementById('heatmap-container');
  if (!container) return;
  if (!routeId) {
    container.innerHTML = '<p style="color:var(--text-muted);padding:20px">Select a route to view the time heatmap.</p>';
    return;
  }

  try {
    const res = await fetch(`${API}/analytics/time-heatmap/${routeId}`);
    const data = await res.json();
    renderHeatmap(data, container);
  } catch (e) {
    container.innerHTML = '<p style="color:var(--danger);padding:20px">Failed to load heatmap.</p>';
  }
}

function renderHeatmap(data, container) {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const PERIODS = [
    [0, 4, '12–4 AM'], [4, 7, '4–7 AM'], [7, 10, '7–10 AM'],
    [10, 13, '10 AM–1 PM'], [13, 16, '1–4 PM'], [16, 19, '4–7 PM'],
    [19, 22, '7–10 PM'], [22, 24, '10 PM–12 AM'],
  ];

  // Build lookup: (hour, dow) → complaint count
  const lookup = {};
  data.forEach(cell => {
    for (let h = cell.hour; h < cell.hour + 1; h++) {
      const key = `${cell.hour}-${cell.day_of_week}`;
      lookup[key] = (lookup[key] || 0) + cell.complaint_count;
    }
  });

  // Aggregate into periods
  const periodData = PERIODS.map(([start, end, label]) => ({
    label,
    values: days.map((_, dow) => {
      let total = 0;
      for (let h = start; h < end; h++) {
        total += lookup[`${h}-${dow}`] || 0;
      }
      return total;
    }),
  }));

  const maxVal = Math.max(...periodData.flatMap(p => p.values), 1);

  container.innerHTML = `
    <div class="heatmap-grid">
      <div class="heatmap-header">
        <div class="heatmap-label"></div>
        ${days.map(d => `<div class="heatmap-day">${d}</div>`).join('')}
      </div>
      ${periodData.map(period => `
        <div class="heatmap-row">
          <div class="heatmap-label">${period.label}</div>
          ${period.values.map(v => {
            const intensity = v / maxVal;
            const alpha = Math.min(0.9, 0.1 + intensity * 0.8);
            const bg = v > 0
              ? `rgba(0, 87, 168, ${alpha})`
              : 'rgba(0,0,0,0.03)';
            return `<div class="heatmap-cell" style="background:${bg}" title="${v} complaints">
              <span class="heatmap-val">${v > 0 ? v : ''}</span>
            </div>`;
          }).join('')}
        </div>
      `).join('')}
    </div>
    <div class="heatmap-legend">
      <span style="color:var(--text-muted)">Low</span>
      <div class="heatmap-legend-bar"></div>
      <span style="color:var(--text-muted)">High</span>
    </div>
  `;
}

// ─── Route Summary Drill-Down ──────────────────────────────────
async function drillDown(routeId, routeNumber) {
  // Use the sidebar section switcher (not the old tab system)
  if (typeof switchSection === 'function') {
    switchSection('route-detail');
  }

  const heading = document.getElementById('detail-route-heading');
  if (heading) heading.textContent = `Route ${routeNumber} — Detail`;

  try {
    const res = await fetch(`${API}/routes/${routeId}/summary`);
    const s = await res.json();
    renderDetailSummary(s);
    await loadRouteCategories(routeId);
    await loadHeatmap(routeId);

    // Update trend filter selection and reload chart
    const trendFilter = document.getElementById('trend-route-filter');
    if (trendFilter) trendFilter.value = routeId;
    await loadGlobalTrend(routeId);
  } catch (e) {
    console.warn('Drill-down failed:', e);
  }

  document.getElementById('section-route-detail')?.scrollIntoView({ behavior: 'smooth' });
}

function renderDetailSummary(s) {
  setKpi('detail-rating',    s.overall_rating.toFixed(2));
  setKpi('detail-composite', s.composite_score.toFixed(2));
  setKpi('detail-complaints', s.complaints_this_month);
  setKpi('detail-total',     s.total_feedback);
  setKpi('detail-top-issue', s.top_issue);
  setKpi('detail-second',    s.second_issue);
  setKpi('detail-worst',     s.worst_period);
  setKpi('detail-punc',      s.rating_punctuality.toFixed(2));
  setKpi('detail-clean',     s.rating_cleanliness.toFixed(2));
  setKpi('detail-crowd',     s.rating_crowding.toFixed(2));
  setKpi('detail-driver',    s.rating_driver.toFixed(2));
}

// ─── Tab Switching ─────────────────────────────────────────────
function initTabSwitching() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      showTab(btn.dataset.tab);
    });
  });
}

function showTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach(p => {
    p.style.display = p.id === tabId ? 'block' : 'none';
  });
  currentTab = tabId;
}

// ─── Route Filters ────────────────────────────────────────────
function initRouteFilter() {
  const searchInput  = document.getElementById('rankings-search');
  const boroughSel   = document.getElementById('borough-filter');

  function applyRankingsFilter() {
    const search  = searchInput?.value  || '';
    const borough = boroughSel?.value   || '';
    loadRankings(search, borough);
  }

  searchInput?.addEventListener('input', applyRankingsFilter);
  boroughSel?.addEventListener('change', applyRankingsFilter);

  document.getElementById('heatmap-route-filter')?.addEventListener('change', e => {
    loadHeatmap(e.target.value);
  });

  document.getElementById('trend-route-filter')?.addEventListener('change', e => {
    loadGlobalTrend(e.target.value || null);
  });

  document.getElementById('route-filter')?.addEventListener('change', async e => {
    const routeId = e.target.value;
    if (routeId) {
      await loadRouteCategories(routeId);
    } else {
      await loadGlobalCategories();
    }
  });
}

// ─── Toast ─────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${icons[type]}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4500);
}

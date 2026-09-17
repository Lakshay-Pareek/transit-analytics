/* ============================================================
   passenger.js — Passenger Feedback Portal Logic
   ============================================================ */

const API = window.location.origin;

// ─── Star rating descriptors ──────────────────────────────────
const STAR_LABELS = {
  1: '1 — Terrible',
  2: '2 — Poor',
  3: '3 — Average',
  4: '4 — Good',
  5: '5 — Excellent',
};

// ─── State ────────────────────────────────────────────────────
let routes = [];
let selectedRouteId = null;
let classifyTimer = null;

// ─── DOM references ───────────────────────────────────────────
const routeSelect    = document.getElementById('route-select');
const routeInfo      = document.getElementById('route-info');
const commentInput   = document.getElementById('comment');
const charCount      = document.getElementById('char-count');
const classifyResult = document.getElementById('classify-result');
const submitBtn      = document.getElementById('submit-btn');
const feedbackForm   = document.getElementById('feedback-form-inner');
const successModal   = document.getElementById('success-modal');

// ─── Initialise ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  checkApiHealth();
  await loadRoutes();
  initStarRatings();
  initCommentClassifier();
  initFormSubmit();
  animateHero();
  startStatsCounter();
});

// ─── API Health Check ──────────────────────────────────────────
async function checkApiHealth() {
  const badge  = document.getElementById('api-status-badge');
  const text   = document.getElementById('api-status-text');
  if (!badge) return;

  badge.className = 'api-status checking';
  text.textContent = 'Connecting…';

  try {
    const res = await fetch(`${API}/analytics/overview`, { signal: AbortSignal.timeout(4000) });
    if (res.ok) {
      badge.className = 'api-status online';
      text.textContent = 'API Connected';
    } else {
      throw new Error('non-200');
    }
  } catch {
    badge.className = 'api-status offline';
    text.textContent = 'API Offline';
    showToast('Backend not reachable. Please try again.', 'error');
  }
}

// ─── Load routes into select ──────────────────────────────────
async function loadRoutes() {
  try {
    const res = await fetch(`${API}/routes/`);
    routes = await res.json();
    routeSelect.innerHTML = '<option value="">— Select a route —</option>';
    routes.forEach(r => {
      const opt = document.createElement('option');
      opt.value = r.id;
      opt.textContent = `${r.route_number} — ${r.route_name} (${r.borough})`;
      routeSelect.appendChild(opt);
    });
  } catch (e) {
    routeSelect.innerHTML = '<option value="">Could not load routes</option>';
    showToast('Could not load routes. Is the server running?', 'error');
  }
}

// ─── Route selection → show summary ──────────────────────────
routeSelect?.addEventListener('change', async (e) => {
  selectedRouteId = e.target.value;
  updateStepProgress();

  if (!selectedRouteId) {
    routeInfo.classList.add('hidden');
    return;
  }
  try {
    const res = await fetch(`${API}/routes/${selectedRouteId}/summary`);
    if (!res.ok) return;
    const s = await res.json();
    renderRouteSummary(s);
    routeInfo.classList.remove('hidden');
    routeInfo.style.animation = 'none';
    void routeInfo.offsetHeight; // force reflow
    routeInfo.style.animation = 'fadeInUp 0.4s ease';
  } catch (_) {}
});

function renderRouteSummary(s) {
  const stars = ratingToStars(s.overall_rating);
  document.getElementById('ri-number').textContent      = s.route_number;
  document.getElementById('ri-name').textContent        = s.route_name;
  document.getElementById('ri-borough').textContent     = s.borough;
  document.getElementById('ri-rating-stars').innerHTML  = stars;
  document.getElementById('ri-rating-value').textContent = `${s.overall_rating.toFixed(1)}/5`;
  document.getElementById('ri-top-issue').textContent   = s.top_issue;
  document.getElementById('ri-second-issue').textContent = s.second_issue;
  document.getElementById('ri-worst-period').textContent = s.worst_period;
  document.getElementById('ri-complaints').textContent  = s.complaints_this_month;
  document.getElementById('ri-total').textContent       = s.total_feedback;

  const scoreEl = document.getElementById('ri-score');
  const score = s.composite_score;
  scoreEl.textContent = score.toFixed(1);
  scoreEl.className = 'score-badge ' + scoreClass(score);
}

function ratingToStars(rating) {
  const full  = Math.floor(rating);
  const half  = rating % 1 >= 0.5 ? 1 : 0;
  const empty = 5 - full - half;
  return '★'.repeat(full + half) + '☆'.repeat(empty);
}

function scoreClass(score) {
  if (score >= 4) return 'score-great';
  if (score >= 3) return 'score-good';
  if (score >= 2) return 'score-fair';
  return 'score-poor';
}

// ─── Star ratings ─────────────────────────────────────────────
function initStarRatings() {
  const starConfigs = [
    { groupId: 'stars-overall',     labelId: 'lbl-overall' },
    { groupId: 'stars-punctuality', labelId: 'lbl-punctuality' },
    { groupId: 'stars-cleanliness', labelId: 'lbl-cleanliness' },
    { groupId: 'stars-crowding',    labelId: 'lbl-crowding' },
    { groupId: 'stars-driver',      labelId: 'lbl-driver' },
  ];

  starConfigs.forEach(({ groupId, labelId }) => {
    const group  = document.getElementById(groupId);
    const label  = document.getElementById(labelId);
    if (!group) return;

    group.querySelectorAll('input[type="radio"]').forEach(inp => {
      inp.addEventListener('change', () => {
        group.setAttribute('data-value', inp.value);
        if (label) label.textContent = STAR_LABELS[inp.value] || '';
        updateStepProgress();
      });
    });
  });
}

function getStarValue(groupId) {
  const group   = document.getElementById(groupId);
  const checked = group?.querySelector('input:checked');
  return checked ? parseFloat(checked.value) : 0;
}

// ─── Step progress tracker ────────────────────────────────────
function updateStepProgress() {
  const hasRoute   = !!selectedRouteId;
  const hasOverall = getStarValue('stars-overall') > 0;
  const hasComment = commentInput?.value.trim().length > 0;

  setStep(1, hasRoute,               !hasRoute);
  setStep(2, hasOverall,             hasRoute && !hasOverall);
  setStep(3, hasComment,             hasRoute && hasOverall && !hasComment);
  setStep(4, false,                  hasRoute && hasOverall);
}

function setStep(num, completed, active) {
  const el = document.getElementById(`step-${num}`);
  if (!el) return;
  el.classList.toggle('completed', completed);
  el.classList.toggle('active',    active && !completed);
  if (completed) {
    const bubble = el.querySelector('.step-bubble');
    if (bubble) bubble.textContent = '✓';
  } else {
    const bubble = el.querySelector('.step-bubble');
    if (bubble && bubble.textContent === '✓') bubble.textContent = num;
  }
}

// ─── Live comment auto-classify ───────────────────────────────
function initCommentClassifier() {
  commentInput?.addEventListener('input', () => {
    const text = commentInput.value;
    charCount.textContent = text.length;
    updateStepProgress();

    clearTimeout(classifyTimer);
    if (text.trim().length < 10) {
      classifyResult.classList.add('hidden');
      return;
    }
    classifyTimer = setTimeout(() => autoClassify(text), 600);
  });
}

async function autoClassify(text) {
  try {
    const res = await fetch(`${API}/classify/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comment: text }),
    });
    if (!res.ok) return;
    const r = await res.json();
    showClassifyResult(r);
  } catch (_) {}
}

function showClassifyResult(r) {
  const badge = document.getElementById('classify-category');
  const sev   = document.getElementById('classify-severity');
  const conf  = document.getElementById('classify-conf');

  badge.textContent = r.category;
  sev.textContent   = r.severity.toUpperCase();
  sev.className     = `badge sev-${r.severity}`;
  conf.textContent  = `${Math.round(r.confidence * 100)}% confidence`;

  classifyResult.classList.remove('hidden');
  classifyResult.style.animation = 'none';
  void classifyResult.offsetHeight;
  classifyResult.style.animation = 'fadeInUp 0.3s ease';
}

// ─── Form submit ──────────────────────────────────────────────
// The submit button is now type="submit" INSIDE the form, so this
// naturally fires when the button is clicked.
function initFormSubmit() {
  feedbackForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!selectedRouteId) {
      showToast('Please select a route first.', 'error');
      routeSelect?.focus();
      return;
    }

    const overall = getStarValue('stars-overall');
    if (!overall) {
      showToast('Please give an overall rating before submitting.', 'error');
      document.getElementById('stars-overall')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    const payload = {
      route_id:           parseInt(selectedRouteId),
      rating_overall:     overall,
      rating_punctuality: getStarValue('stars-punctuality') || null,
      rating_cleanliness: getStarValue('stars-cleanliness') || null,
      rating_crowding:    getStarValue('stars-crowding')    || null,
      rating_driver:      getStarValue('stars-driver')      || null,
      comment:            commentInput.value.trim() || null,
    };

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<div class="spinner" style="width:20px;height:20px;border-width:2px"></div><span>Submitting…</span>';

    try {
      const res = await fetch(`${API}/feedback/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }

      const fb = await res.json();
      showSuccessModal(fb);

      // Reset form state
      feedbackForm.reset();
      charCount.textContent = '0';
      classifyResult.classList.add('hidden');
      routeInfo.classList.add('hidden');
      selectedRouteId = null;

      // Reset star labels
      document.querySelectorAll('.star-value-label').forEach(l => { l.textContent = ''; });

      // Reset step progress
      ['step-1','step-2','step-3','step-4'].forEach((id, i) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.classList.remove('completed', 'active');
        const bubble = el.querySelector('.step-bubble');
        if (bubble) bubble.textContent = i === 3 ? '✓' : (i + 1);
      });
      document.getElementById('step-1')?.classList.add('active');

    } catch (err) {
      showToast(`Submission failed: ${err.message}`, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>Submit Feedback</span><span>→</span>';
    }
  });
}

// ─── Success modal ─────────────────────────────────────────────
function showSuccessModal(fb) {
  document.getElementById('modal-category').textContent = fb.category || 'General';
  document.getElementById('modal-severity').textContent = (fb.severity || 'low').toUpperCase();
  document.getElementById('modal-severity').className   = `badge sev-${fb.severity || 'low'}`;
  document.getElementById('modal-rating').textContent   = `${fb.rating_overall}/5`;
  successModal.classList.remove('hidden');
}

document.getElementById('close-modal')?.addEventListener('click', () => {
  successModal.classList.add('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

successModal?.addEventListener('click', (e) => {
  if (e.target === successModal) successModal.classList.add('hidden');
});

// ─── Hero word animation ──────────────────────────────────────
function animateHero() {
  const words = ['safer', 'faster', 'cleaner', 'better'];
  let i = 0;
  const el = document.getElementById('hero-word');
  if (!el) return;
  setInterval(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(-10px)';
    setTimeout(() => {
      el.textContent = words[i++ % words.length];
      el.style.opacity = '1';
      el.style.transform = 'translateY(0)';
    }, 300);
  }, 2500);
}

// ─── Hero stats counter ───────────────────────────────────────
async function startStatsCounter() {
  try {
    const res  = await fetch(`${API}/analytics/overview`);
    const data = await res.json();
    animateCounter('stat-feedback', data.total_feedback);
    animateCounter('stat-routes',   data.total_routes);
    animateCounter('stat-rating',   data.platform_avg_rating, true);
  } catch (_) {
    // Show placeholder values if API not yet responding
    animateCounter('stat-feedback', 2847);
    animateCounter('stat-routes',   22);
    animateCounter('stat-rating',   3.4, true);
  }
}

function animateCounter(id, target, isFloat = false) {
  const el = document.getElementById(id);
  if (!el) return;
  const duration = 1800;
  const start    = performance.now();

  function step(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased    = 1 - Math.pow(1 - progress, 3);
    const val      = target * eased;
    el.textContent = isFloat ? val.toFixed(1) : Math.round(val).toLocaleString();
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ─── Toast ─────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4200);
}

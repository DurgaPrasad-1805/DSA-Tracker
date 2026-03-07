/* ── Helpers ────────────────────────────────────────────────────── */
const $ = (s, ctx = document) => ctx.querySelector(s);
const $$ = (s, ctx = document) => [...ctx.querySelectorAll(s)];

/* ── Problem Checkboxes (DSA page) ─────────────────────────────── */
function initProblemToggles() {
  $$('input.custom-cb[data-id]').forEach(cb => {
    cb.addEventListener('change', async () => {
      const id = cb.dataset.id;
      const row = cb.closest('tr');
      const res = await fetch(`/api/toggle_problem/${id}`, { method: 'POST' });
      const data = await res.json();
      if (data.ok) {
        row.classList.toggle('solved-row', data.status === 1);
        updateSolvedCount(data.solved);
      } else {
        cb.checked = !cb.checked; // revert
      }
    });
  });
}

function updateSolvedCount(n) {
  const el = document.getElementById('solved-count');
  if (el) el.textContent = n;
}

/* ── Subject Toggles ───────────────────────────────────────────── */
function initSubjectToggles() {
  $$('.subject-card[data-id]').forEach(card => {
    card.addEventListener('click', async () => {
      const id = card.dataset.id;
      const res = await fetch(`/api/toggle_subject/${id}`, { method: 'POST' });
      const data = await res.json();
      if (data.ok) {
        card.classList.toggle('done', data.status === 1);
        const statusEl = card.querySelector('.subject-status');
        if (statusEl) statusEl.textContent = data.status === 1 ? '✓ Done' : 'In Progress';
      }
    });
  });
}

/* ── Filter Buttons (DSA page) ─────────────────────────────────── */
function initFilters() {
  const btns = $$('.filter-btn');
  const rows = $$('tbody tr[data-topic]');

  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const filter = btn.dataset.filter;
      rows.forEach(row => {
        const show = filter === 'all'
          || row.dataset.topic === filter
          || (filter === 'unsolved' && !row.classList.contains('solved-row'));
        row.style.display = show ? '' : 'none';
      });
    });
  });
}

/* ── Timetable Tabs ────────────────────────────────────────────── */
function initTimetableTabs() {
  const tabs  = $$('.tt-tab');
  const grids = $$('.tt-grid');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      grids.forEach(g => g.classList.remove('active'));
      tab.classList.add('active');
      const target = document.getElementById(tab.dataset.target);
      if (target) target.classList.add('active');
    });
  });
}

/* ── Animate Progress Bars on load ─────────────────────────────── */
function animateProgressBars() {
  $$('.progress-fill[data-pct]').forEach(bar => {
    const pct = bar.dataset.pct;
    setTimeout(() => { bar.style.width = pct + '%'; }, 100);
  });
}

/* ── Init ───────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initProblemToggles();
  initSubjectToggles();
  initFilters();
  initTimetableTabs();
  animateProgressBars();

  // Highlight active nav link
  $$('nav a').forEach(a => {
    if (a.href === location.href) a.classList.add('active');
  });
});
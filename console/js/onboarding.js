/**
 * onboarding.js -- Multi-step walkthrough replacing the old single popup.
 *
 * Six steps walk a first-time student through the application:
 * what it teaches, each tab, suggested first action, and learning path.
 * Progress dots show current position. Next/Back/Skip navigation.
 *
 * Per-tab "start here" tooltips appear once per tab on first visit.
 * The "?" help button re-opens the full walkthrough at any time.
 *
 * All state persisted via localStorage so returning visitors aren't
 * re-shown onboarding unless they explicitly request it.
 */

const Onboarding = (() => {

  const LS_KEY = 'cll_onboarded';
  let _step = 0;
  let _modal = null;

  const STEPS = [
    {
      icon: '\u2728',
      title: 'Welcome to COBOL Legacy Ledger',
      body: 'An educational mainframe training simulator. Five banks, one clearing house, real COBOL programs, and cryptographic integrity chains. This is not a themed demo \u2014 it\'s the real thing.',
    },
    {
      icon: '\u25B6',
      title: 'Dashboard \u2014 Observe',
      body: 'Hit <strong>Start</strong> to run a multi-day banking simulation. Watch transactions flow through the hub-and-spoke network. Use <strong>Corrupt Ledger</strong> then <strong>Integrity Check</strong> to see SHA-256 tamper detection in action.',
    },
    {
      icon: '\uD83D\uDD0D',
      title: 'Analysis \u2014 Investigate',
      body: 'Analyze legacy COBOL: call graphs, complexity scoring, dead code detection. Click any node for a deep dive. Try <strong>Compare Spaghetti vs Clean</strong> to see why structured code matters.',
    },
    {
      icon: '\u2328',
      title: 'Mainframe \u2014 Write & Practice',
      body: 'Write real COBOL in an 80-column editor. Compile with GnuCOBOL. See authentic JCL-style output. Load templates to start from working code, then modify and recompile.',
    },
    {
      icon: '\uD83D\uDCA1',
      title: 'Suggested First Action',
      body: 'Go to the <strong>Dashboard</strong> tab and hit <strong>Start</strong>. Watch 25 simulated days of banking. Then try <strong>Corrupt Ledger</strong> followed by <strong>Integrity Check</strong> to see cryptographic fraud detection.',
    },
    {
      icon: '\uD83D\uDCDA',
      title: 'Learning Path',
      body: 'For structured self-study, see the <strong>Learning Path</strong> document (6 levels from "Hello COBOL" to "Full System Integration"). Instructors: see the <strong>Teaching Guide</strong> for 8 lesson plans with rubrics.',
    },
  ];

  /* ── Modal Rendering ───────────────────────────────────────── */

  function createModal() {
    const overlay = document.createElement('div');
    overlay.className = 'popup-overlay onboarding-v2-overlay';
    overlay.id = 'onboardingV2';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');

    overlay.innerHTML = `<div class="popup glass onboarding-v2">
      <div class="onboarding-v2__content" id="onboardingContent"></div>
      <div class="onboarding-v2__progress" id="onboardingProgress"></div>
      <div class="onboarding-v2__actions">
        <button class="btn btn--sm" id="onbBack">Back</button>
        <button class="btn btn--sm" id="onbSkip">Skip</button>
        <button class="btn btn--sm btn--primary" id="onbNext">Next</button>
      </div>
    </div>`;

    document.body.appendChild(overlay);
    _modal = overlay;

    document.getElementById('onbNext')?.addEventListener('click', next);
    document.getElementById('onbBack')?.addEventListener('click', back);
    document.getElementById('onbSkip')?.addEventListener('click', dismiss);

    // Escape to dismiss
    overlay.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') dismiss();
    });
  }

  function renderStep() {
    if (!_modal) return;

    const step = STEPS[_step];
    const content = document.getElementById('onboardingContent');
    const progress = document.getElementById('onboardingProgress');
    const backBtn = document.getElementById('onbBack');
    const nextBtn = document.getElementById('onbNext');

    if (content) {
      content.innerHTML = `
        <div class="onboarding-v2__icon">${step.icon}</div>
        <h2 class="onboarding-v2__title">${step.title}</h2>
        <p class="onboarding-v2__body">${step.body}</p>`;
    }

    // Progress dots
    if (progress) {
      progress.innerHTML = STEPS.map((_, i) =>
        `<span class="onboarding-v2__dot${i === _step ? ' onboarding-v2__dot--active' : ''}"></span>`
      ).join('');
    }

    // Button states
    if (backBtn) backBtn.style.visibility = _step === 0 ? 'hidden' : 'visible';
    if (nextBtn) nextBtn.textContent = _step === STEPS.length - 1 ? 'Get Started' : 'Next';
  }

  function next() {
    if (_step < STEPS.length - 1) {
      _step++;
      renderStep();
    } else {
      dismiss();
    }
  }

  function back() {
    if (_step > 0) {
      _step--;
      renderStep();
    }
  }

  function dismiss() {
    localStorage.setItem(LS_KEY, '1');
    if (_modal) {
      _modal.remove();
      _modal = null;
    }
    _step = 0;
  }

  /* ── Public API ────────────────────────────────────────────── */

  function show() {
    _step = 0;
    if (_modal) _modal.remove();
    createModal();
    renderStep();
  }

  /* ── Per-Tab Hints ─────────────────────────────────────────── */

  function showTabHint(tabName) {
    const key = `cll_tab_hint_${tabName}`;
    if (localStorage.getItem(key)) return;

    const targets = {
      dashboard: '#btnStart',
      analysis: '#btnAnalyze',
      mainframe: '#btnCompile',
    };

    const selector = targets[tabName];
    if (!selector) return;

    const el = document.querySelector(selector);
    if (!el) return;

    const hint = document.createElement('span');
    hint.className = 'tab-hint';
    hint.textContent = 'Start here \u2192';

    el.parentElement.style.position = el.parentElement.style.position || 'relative';
    el.parentElement.appendChild(hint);

    localStorage.setItem(key, '1');

    // Auto-remove after 5 seconds
    setTimeout(() => hint.remove(), 5000);
  }

  /* ── Init ──────────────────────────────────────────────────── */

  function init() {
    // First-time visitor?
    if (!localStorage.getItem(LS_KEY)) {
      // Hide old onboarding if it exists
      const old = document.getElementById('onboarding');
      if (old) old.style.display = 'none';
      show();
    }

    // Wire "?" help button
    const helpBtn = document.getElementById('btnShowHelp');
    if (helpBtn) {
      // Remove existing listeners by replacing the node
      const newBtn = helpBtn.cloneNode(true);
      helpBtn.parentNode.replaceChild(newBtn, helpBtn);
      newBtn.addEventListener('click', show);
    }

    // Per-tab hints on tab change
    if (typeof EventBus !== 'undefined') {
      EventBus.on('tab.changed', (payload) => {
        setTimeout(() => showTabHint(payload.tab), 500);
      });
    }
  }

  return { init, show };

})();

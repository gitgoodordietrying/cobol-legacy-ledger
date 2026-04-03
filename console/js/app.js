/**
 * app.js -- SPA router, health check polling, module initialization.
 *
 * Entry point that initializes all console modules and handles view
 * switching between Dashboard and Chat tabs. Polls the health endpoint
 * to update the nav health dot indicator.
 */

const App = (() => {

  let currentView = 'dashboard';

  /** Role descriptions shown in toast when the user switches roles. */
  const ROLE_DESCRIPTIONS = {
    admin: 'Full access \u2014 run simulations, tamper, verify, and manage accounts.',
    operator: 'Can run simulations and transactions. Cannot manage accounts.',
    auditor: 'Read-only + can verify chains and detect tampering. Cannot run simulations.',
    viewer: 'Read-only access. Cannot run simulations or modify data.',
  };

  /** Buttons that require operator/admin role to use. */
  const ROLE_GATED_BUTTONS = [
    { id: 'btnStart', roles: ['admin', 'operator'] },
    { id: 'btnPause', roles: ['admin', 'operator'] },
    { id: 'btnStop', roles: ['admin', 'operator'] },
    { id: 'btnReset', roles: ['admin', 'operator'] },
    { id: 'btnTamper', roles: ['admin'] },
    { id: 'btnVerify', roles: ['admin', 'auditor'] },
  ];

  /**
   * Initialize the application on DOM ready.
   */
  function init() {
    // Initialize modules
    NetworkGraph.init();
    CobolViewer.init();
    Dashboard.init();
    Chat.init();
    Analysis.init();
    if (typeof Mainframe !== 'undefined') Mainframe.init();
    if (typeof FunFacts !== 'undefined') FunFacts.init();
    if (typeof Onboarding !== 'undefined') Onboarding.init();
    if (typeof ChainDefense !== 'undefined') ChainDefense.init();
    if (typeof Breadcrumbs !== 'undefined') Breadcrumbs.init();

    // View switching
    document.querySelectorAll('.nav__tab').forEach(tab => {
      tab.addEventListener('click', () => switchView(tab.dataset.view));
    });

    // Role selector syncs to chat sidebar + shows toast + updates button states
    const roleSelect = document.getElementById('roleSelect');
    if (roleSelect) {
      roleSelect.addEventListener('change', () => {
        const role = roleSelect.value;
        const chatRole = document.getElementById('chatRole');
        if (chatRole) chatRole.textContent = role;
        Utils.showToast(`Switched to ${role} \u2014 ${ROLE_DESCRIPTIONS[role] || ''}`, 'info');
        updateButtonStatesForRole(role);
      });
      // Set initial chat role display and button states
      const chatRole = document.getElementById('chatRole');
      if (chatRole) chatRole.textContent = roleSelect.value;
      updateButtonStatesForRole(roleSelect.value);
    }

    // Health check polling
    checkHealth();
    setInterval(checkHealth, 30000);

    // Refresh node data periodically
    NetworkGraph.refreshNodeData();
    setInterval(() => NetworkGraph.refreshNodeData(), 60000);

    // First-visit onboarding
    showOnboarding();

    // "Show help" button re-triggers onboarding
    document.getElementById('btnShowHelp')?.addEventListener('click', () => {
      const overlay = document.getElementById('onboarding');
      if (overlay) overlay.style.display = '';
    });

    // Help-tip click-to-toggle popovers
    initHelpTips();

    // Global Escape key to dismiss overlays
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      // Close any open help tips first
      const openTip = document.querySelector('.help-tip--open');
      if (openTip) { openTip.classList.remove('help-tip--open'); return; }
      const overlays = ['cobolModal', 'nodePopup', 'onboarding'];
      for (const id of overlays) {
        const el = document.getElementById(id);
        if (el && el.style.display !== 'none') {
          el.style.display = 'none';
          if (id === 'onboarding') localStorage.setItem('cll_onboarded', '1');
          break;
        }
      }
    });
  }

  /**
   * Initialize all (?) help-tip popovers: click to toggle, click elsewhere to dismiss.
   */
  function initHelpTips() {
    document.querySelectorAll('.help-tip').forEach(tip => {
      // Populate content from data-help attribute
      const content = tip.querySelector('.help-tip__content');
      if (content && tip.dataset.help) content.textContent = tip.dataset.help;

      tip.addEventListener('click', (e) => {
        e.stopPropagation();
        const wasOpen = tip.classList.contains('help-tip--open');
        // Close all tips
        document.querySelectorAll('.help-tip--open').forEach(t => t.classList.remove('help-tip--open'));
        if (!wasOpen) tip.classList.add('help-tip--open');
      });
    });

    // Click anywhere else to close open tips
    document.addEventListener('click', () => {
      document.querySelectorAll('.help-tip--open').forEach(t => t.classList.remove('help-tip--open'));
    });
  }

  /**
   * Dim/enable buttons based on current role permissions.
   */
  function updateButtonStatesForRole(role) {
    ROLE_GATED_BUTTONS.forEach(({ id, roles }) => {
      const btn = document.getElementById(id);
      if (!btn) return;
      if (roles.includes(role)) {
        btn.classList.remove('btn--role-blocked');
        btn.removeAttribute('data-role-hint');
      } else {
        btn.classList.add('btn--role-blocked');
        btn.setAttribute('data-role-hint', `Requires ${roles.join(' or ')} role`);
      }
    });
  }

  /**
   * Switch the active view (dashboard or chat).
   */
  function switchView(viewName) {
    currentView = viewName;
    if (typeof EventBus !== 'undefined') EventBus.emit('tab.changed', { tab: viewName });

    // Update tab active states and ARIA
    document.querySelectorAll('.nav__tab').forEach(tab => {
      const isActive = tab.dataset.view === viewName;
      tab.classList.toggle('nav__tab--active', isActive);
      tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });

    // Show/hide views
    document.querySelectorAll('.view').forEach(view => {
      view.classList.toggle('view--active', view.id === `view-${viewName}`);
    });
  }

  /**
   * Poll the health endpoint and update the nav dot.
   */
  async function checkHealth() {
    const dot = document.getElementById('healthDot');
    if (!dot) return;

    try {
      const health = await ApiClient.get('/api/health');
      dot.classList.remove('health-dot--ok', 'health-dot--warn', 'health-dot--error');
      if (health.status === 'healthy') {
        dot.classList.add('health-dot--ok');
        dot.title = `API healthy \u2014 ${health.nodes_available} nodes`;
      } else {
        dot.classList.add('health-dot--warn');
        dot.title = `API degraded \u2014 ${health.nodes_available} nodes`;
      }
    } catch {
      dot.classList.remove('health-dot--ok', 'health-dot--warn');
      dot.classList.add('health-dot--error');
      dot.title = 'API unreachable';
    }
  }

  /**
   * Show the onboarding popup on first visit (localStorage flag).
   */
  function showOnboarding() {
    if (localStorage.getItem('cll_onboarded')) return;

    const overlay = document.getElementById('onboarding');
    if (!overlay) return;
    overlay.style.display = '';

    document.getElementById('onboardingDismiss')?.addEventListener('click', () => {
      overlay.style.display = 'none';
      localStorage.setItem('cll_onboarded', '1');
    });
    // Also dismiss on overlay background click
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.style.display = 'none';
        localStorage.setItem('cll_onboarded', '1');
      }
    });
  }

  return { init, switchView };
})();

// Boot on DOM ready
document.addEventListener('DOMContentLoaded', App.init);

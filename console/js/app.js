/**
 * app.js -- SPA router, health check polling, module initialization.
 *
 * Entry point that initializes all console modules and handles view
 * switching between Dashboard and Chat tabs. Polls the health endpoint
 * to update the nav health dot indicator.
 */

const App = (() => {

  let currentView = 'dashboard';

  /**
   * Initialize the application on DOM ready.
   */
  function init() {
    // Initialize modules
    NetworkGraph.init();
    CobolViewer.init();
    Dashboard.init();
    Chat.init();

    // View switching
    document.querySelectorAll('.nav__tab').forEach(tab => {
      tab.addEventListener('click', () => switchView(tab.dataset.view));
    });

    // Role selector syncs to chat sidebar
    const roleSelect = document.getElementById('roleSelect');
    if (roleSelect) {
      roleSelect.addEventListener('change', () => {
        const chatRole = document.getElementById('chatRole');
        if (chatRole) chatRole.textContent = roleSelect.value;
      });
      // Set initial chat role display
      const chatRole = document.getElementById('chatRole');
      if (chatRole) chatRole.textContent = roleSelect.value;
    }

    // Health check polling
    checkHealth();
    setInterval(checkHealth, 30000);

    // Refresh node data periodically
    NetworkGraph.refreshNodeData();
    setInterval(() => NetworkGraph.refreshNodeData(), 60000);
  }

  /**
   * Switch the active view (dashboard or chat).
   */
  function switchView(viewName) {
    currentView = viewName;

    // Update tab active states
    document.querySelectorAll('.nav__tab').forEach(tab => {
      tab.classList.toggle('nav__tab--active', tab.dataset.view === viewName);
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
        dot.title = `API healthy — ${health.nodes_available} nodes`;
      } else {
        dot.classList.add('health-dot--warn');
        dot.title = `API degraded — ${health.nodes_available} nodes`;
      }
    } catch {
      dot.classList.remove('health-dot--ok', 'health-dot--warn');
      dot.classList.add('health-dot--error');
      dot.title = 'API unreachable';
    }
  }

  return { init };
})();

// Boot on DOM ready
document.addEventListener('DOMContentLoaded', App.init);

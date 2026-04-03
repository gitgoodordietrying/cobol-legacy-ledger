/**
 * breadcrumbs.js -- Navigation trail below the nav bar.
 *
 * Listens to EventBus tab.changed and selection.changed events,
 * building a clickable breadcrumb trail showing the user's path
 * through the application. Max 5 entries visible.
 *
 * Graceful degradation: if EventBus is not defined, the module
 * silently skips initialization and renders nothing.
 */

const Breadcrumbs = (() => {

  const MAX_VISIBLE = 5;
  const MAX_LABEL = 25;
  let _trail = [];

  /**
   * Add an entry to the breadcrumb trail.
   */
  function addEntry(tab, label) {
    // Dedup: don't add consecutive identical entries
    const last = _trail[_trail.length - 1];
    if (last && last.tab === tab && last.label === label) return;

    _trail.push({ tab, label, timestamp: Date.now() });

    // Cap trail length
    if (_trail.length > 20) _trail = _trail.slice(-20);

    render();
  }

  /**
   * Render the breadcrumb bar.
   */
  function render() {
    const bar = document.getElementById('breadcrumbBar');
    if (!bar) return;

    if (_trail.length === 0) {
      bar.innerHTML = '';
      return;
    }

    const visible = _trail.slice(-MAX_VISIBLE);
    const hasOverflow = _trail.length > MAX_VISIBLE;

    let html = '';

    if (hasOverflow) {
      html += '<span class="breadcrumb__overflow" title="Earlier navigation history">\u2026</span>';
      html += '<span class="breadcrumb__sep">\u203A</span>';
    }

    visible.forEach((entry, i) => {
      if (i > 0) html += '<span class="breadcrumb__sep">\u203A</span>';

      const truncated = entry.label.length > MAX_LABEL
        ? entry.label.slice(0, MAX_LABEL - 1) + '\u2026'
        : entry.label;

      html += `<span class="breadcrumb__item" data-tab="${Utils.escapeHtml(entry.tab)}" title="${Utils.escapeHtml(entry.label)}">${Utils.escapeHtml(truncated)}</span>`;
    });

    bar.innerHTML = html;

    // Wire clicks
    bar.querySelectorAll('.breadcrumb__item').forEach(el => {
      el.addEventListener('click', () => {
        const tab = el.dataset.tab;
        if (tab && typeof App !== 'undefined') App.switchView(tab);
      });
    });
  }

  /**
   * Initialize: listen for EventBus events.
   */
  function init() {
    if (typeof EventBus === 'undefined') return;

    EventBus.on('tab.changed', (payload) => {
      const tabLabels = {
        dashboard: 'Dashboard',
        analysis: 'Analysis',
        mainframe: 'Mainframe',
        chat: 'Chat',
      };
      addEntry(payload.tab, tabLabels[payload.tab] || payload.tab);
    });

    EventBus.on('selection.changed', (payload) => {
      const label = payload.id || payload.type || 'selection';
      const tab = payload.context?.tab || 'analysis';
      addEntry(tab, label);
    });
  }

  return { init };

})();

/**
 * dashboard.js -- Simulation controls, event feed, and node detail popup.
 *
 * Wires Start/Pause/Stop buttons to the simulation API, connects SSE for
 * real-time event streaming, maintains the event feed (capped at 200 items),
 * and updates stats counters. Also handles Tamper Demo and Verify All.
 */

const Dashboard = (() => {

  let sse = null;
  let feedCount = 0;
  const MAX_FEED = 200;

  /**
   * Initialize all dashboard controls and bindings.
   */
  function init() {
    // Button bindings
    document.getElementById('btnStart')?.addEventListener('click', startSim);
    document.getElementById('btnStop')?.addEventListener('click', stopSim);
    document.getElementById('btnPause')?.addEventListener('click', togglePause);
    document.getElementById('btnTamper')?.addEventListener('click', tamperDemo);
    document.getElementById('btnVerify')?.addEventListener('click', verifyAll);

    // Node popup close
    document.getElementById('nodePopupClose')?.addEventListener('click', closeNodePopup);
    document.getElementById('nodePopup')?.addEventListener('click', (e) => {
      if (e.target.id === 'nodePopup') closeNodePopup();
    });

    // Poll status to restore state on refresh
    pollStatus();
    setInterval(pollStatus, 10000);
  }

  /**
   * Start the simulation.
   */
  async function startSim() {
    const days = parseInt(document.getElementById('daysInput')?.value || '25');
    try {
      await ApiClient.post('/api/simulation/start', { days, time_scale: 0 });
      connectSSE();
      setButtonState('running');
      clearFeed();
      Utils.showToast(`Simulation started (${days} days)`, 'success');
    } catch (err) {
      Utils.showToast(err.message, 'danger');
    }
  }

  /**
   * Stop the simulation.
   */
  async function stopSim() {
    try {
      await ApiClient.post('/api/simulation/stop');
      disconnectSSE();
      setButtonState('stopped');
      Utils.showToast('Simulation stopped', 'info');
    } catch (err) {
      Utils.showToast(err.message, 'danger');
    }
  }

  /**
   * Toggle pause/resume.
   */
  async function togglePause() {
    const btn = document.getElementById('btnPause');
    const isPaused = btn?.textContent === 'Resume';
    try {
      if (isPaused) {
        await ApiClient.post('/api/simulation/resume');
        btn.textContent = 'Pause';
        Utils.showToast('Simulation resumed', 'info');
      } else {
        await ApiClient.post('/api/simulation/pause');
        btn.textContent = 'Resume';
        Utils.showToast('Simulation paused', 'warning');
      }
    } catch (err) {
      Utils.showToast(err.message, 'danger');
    }
  }

  /**
   * Set button enabled/disabled state based on simulation state.
   */
  function setButtonState(state) {
    const start = document.getElementById('btnStart');
    const pause = document.getElementById('btnPause');
    const stop = document.getElementById('btnStop');

    if (state === 'running') {
      start.disabled = true;
      pause.disabled = false;
      stop.disabled = false;
      pause.textContent = 'Pause';
    } else {
      start.disabled = false;
      pause.disabled = true;
      stop.disabled = true;
    }
  }

  /**
   * Connect to SSE event stream.
   */
  function connectSSE() {
    disconnectSSE();
    sse = ApiClient.createSSE('/api/simulation/events');

    sse.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        handleEvent(event);
      } catch { /* ignore parse errors */ }
    };

    sse.onerror = () => {
      // SSE will auto-reconnect; if sim ended, stop gracefully
      setTimeout(() => {
        pollStatus().then(status => {
          if (!status.running) {
            disconnectSSE();
            setButtonState('stopped');
          }
        });
      }, 2000);
    };
  }

  /**
   * Disconnect SSE.
   */
  function disconnectSSE() {
    if (sse) {
      sse.close();
      sse = null;
    }
  }

  /**
   * Handle an incoming SSE event.
   */
  function handleEvent(event) {
    // Update stats
    updateStats(event);

    // Animate network graph
    NetworkGraph.animateTransaction(event);

    // Update COBOL viewer
    CobolViewer.highlightForEvent(event);

    // Add to feed
    addFeedItem(event);
  }

  /**
   * Update stats counters from status poll.
   */
  function updateStatsFromStatus(status) {
    setText('dayCounter', `Day ${status.day}`);
    setText('statCompleted', status.completed.toLocaleString());
    setText('statFailed', status.failed.toLocaleString());
    setText('statVolume', Utils.formatCurrency(status.volume));
  }

  /**
   * Update stats from individual event (incremental).
   */
  function updateStats(event) {
    // Individual events don't carry cumulative stats, so just rely on polling.
    // But we can update the day counter if present.
    if (event.day) {
      setText('dayCounter', `Day ${event.day}`);
    }
  }

  /**
   * Add an item to the event feed.
   */
  function addFeedItem(event) {
    const feedList = document.getElementById('feedList');
    if (!feedList) return;

    // Remove empty state message
    const emptyEl = feedList.querySelector('.feed__empty');
    if (emptyEl) emptyEl.remove();

    // Determine CSS class
    let cls = 'feed__item';
    if (event.type === 'scenario') {
      cls += event.event_type === 'TAMPER_BALANCE' ? ' feed__item--tamper' : ' feed__item--scenario';
    } else if (event.type === 'external') {
      cls += ' feed__item--external';
    }

    // Build display text
    let text = '';
    if (event.type === 'scenario') {
      text = `[D${event.day || '?'}] ${event.event_type}: ${Utils.truncate(event.description, 60)}`;
    } else if (event.type === 'external') {
      const status = event.status === 'COMPLETED' ? 'OK' : 'FAIL';
      text = `[D${event.day || '?'}] ${event.bank}→${event.dest_bank} $${event.amount?.toFixed(2)} ${status}`;
    } else {
      const status = event.status === '00' ? 'OK' : 'FAIL';
      text = `[D${event.day || '?'}] ${event.bank} ${event.type?.toUpperCase()?.slice(0,3)} ${event.account} $${event.amount?.toFixed(2)} ${status}`;
    }

    const item = document.createElement('div');
    item.className = cls;
    item.textContent = text;

    // Insert at top (newest first)
    feedList.insertBefore(item, feedList.firstChild);
    feedCount++;

    // Update count badge
    setText('feedCount', feedCount.toString());

    // Cap at MAX_FEED
    while (feedList.children.length > MAX_FEED) {
      feedList.removeChild(feedList.lastChild);
    }
  }

  /**
   * Clear the event feed.
   */
  function clearFeed() {
    const feedList = document.getElementById('feedList');
    if (feedList) {
      feedList.innerHTML = '';
    }
    feedCount = 0;
    setText('feedCount', '0');
  }

  /**
   * Poll simulation status.
   */
  async function pollStatus() {
    try {
      const status = await ApiClient.get('/api/simulation/status');
      updateStatsFromStatus(status);
      if (status.running) {
        setButtonState('running');
        if (!sse) connectSSE();
        if (status.paused) {
          const btn = document.getElementById('btnPause');
          if (btn) btn.textContent = 'Resume';
        }
      } else {
        if (sse) disconnectSSE();
        setButtonState('stopped');
      }
      return status;
    } catch {
      return { running: false, day: 0, completed: 0, failed: 0, volume: 0 };
    }
  }

  /**
   * Tamper demo: modify a DAT file balance.
   */
  async function tamperDemo() {
    try {
      const result = await ApiClient.post('/api/tamper-demo', {});
      Utils.showToast(`Tampered ${result.node}/${result.account_id} → $${result.new_amount.toLocaleString()}`, 'danger');
    } catch (err) {
      Utils.showToast(err.message, 'danger');
    }
  }

  /**
   * Run cross-node verification.
   */
  async function verifyAll() {
    try {
      const result = await ApiClient.post('/api/settlement/verify');
      const intact = result.all_chains_intact;
      const matched = result.all_settlements_matched;
      const type = (intact && matched) ? 'success' : 'danger';
      const msg = intact && matched
        ? `All chains intact, ${result.settlements_checked} settlements matched`
        : `Issues: ${result.anomalies?.length || 0} anomalies detected`;
      Utils.showToast(msg, type);

      // Add to feed
      addFeedItem({
        type: 'scenario',
        event_type: intact ? 'VERIFY_OK' : 'VERIFY_FAIL',
        description: msg,
        day: document.getElementById('dayCounter')?.textContent?.match(/\d+/)?.[0] || '?',
      });

      // Refresh node health dots
      NetworkGraph.refreshNodeData();
    } catch (err) {
      Utils.showToast(err.message, 'danger');
    }
  }

  /**
   * Show node detail popup with accounts and chain info.
   */
  async function showNodeDetail(nodeName) {
    const popup = document.getElementById('nodePopup');
    const header = document.getElementById('nodePopupHeader');
    const body = document.getElementById('nodePopupBody');
    if (!popup || !header || !body) return;

    header.innerHTML = `
      <span class="node-detail__color" style="background: ${Utils.bankColorHex(nodeName)}"></span>
      <span class="node-detail__name">${Utils.escapeHtml(nodeName)}</span>
    `;
    body.innerHTML = '<span style="color: var(--text-muted)">Loading...</span>';
    popup.style.display = 'flex';

    try {
      const [accounts, chain] = await Promise.all([
        ApiClient.get(`/api/nodes/${nodeName}/accounts`),
        ApiClient.post(`/api/nodes/${nodeName}/chain/verify`),
      ]);

      let html = '';

      // Chain info
      const chainOk = chain.valid;
      html += `<div class="node-detail__chain">
        <span class="health-dot health-dot--${chainOk ? 'ok' : 'error'}"></span>
        <span>Chain: ${chain.entries_checked} entries, ${chainOk ? 'INTACT' : 'BROKEN'} (${chain.time_ms.toFixed(1)}ms)</span>
      </div>`;

      // Accounts table
      html += `<table class="table" style="margin-top: var(--sp-4);">
        <thead><tr>
          <th>Account</th><th>Name</th><th>Type</th><th>Balance</th><th>Status</th>
        </tr></thead><tbody>`;

      accounts.forEach(a => {
        const statusCls = a.status === 'A' ? 'success' : a.status === 'F' ? 'warning' : 'danger';
        html += `<tr>
          <td>${Utils.escapeHtml(a.account_id)}</td>
          <td>${Utils.escapeHtml(a.name)}</td>
          <td>${Utils.escapeHtml(a.account_type)}</td>
          <td>${Utils.formatCurrency(a.balance)}</td>
          <td><span class="badge badge--${statusCls}">${Utils.escapeHtml(a.status)}</span></td>
        </tr>`;
      });

      html += '</tbody></table>';
      body.innerHTML = html;
    } catch (err) {
      body.innerHTML = `<span style="color: var(--danger)">${Utils.escapeHtml(err.message)}</span>`;
    }
  }

  function closeNodePopup() {
    const popup = document.getElementById('nodePopup');
    if (popup) popup.style.display = 'none';
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }

  return { init, showNodeDetail };
})();

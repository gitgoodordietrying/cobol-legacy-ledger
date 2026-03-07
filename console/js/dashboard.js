/**
 * dashboard.js -- Simulation controls, transaction log, and node detail popup.
 *
 * Wires Start/Pause/Stop buttons to the simulation API, connects SSE for
 * real-time event streaming, maintains the transaction log (capped at 200 items),
 * and updates stats counters. Also handles Tamper Demo and Verify All.
 */

const Dashboard = (() => {

  let sse = null;
  let _sseRecovering = false;  // Guard against stacking SSE error recovery polls
  let feedCountOut = 0;
  let feedCountIn = 0;
  let feedCountSystem = 0;
  const MAX_FEED = 200;

  const IDLE_NARRATIVE = 'Five banks, one clearing house. Hit Start to run a 25-day banking simulation.';

  // Scenario event_type → narrative modifier mapping
  const SCENARIO_MODIFIERS = {
    LARGE_TRANSFER: 'warning',
    SUSPICIOUS_BURST: 'warning',
    FREEZE_ACCOUNT: 'warning',
    DRAIN_TRANSFERS: 'warning',
    CLOSE_ACCOUNT: null,       // default style
    TAMPER_BALANCE: 'danger',
  };

  /**
   * Update the narrative banner text and style modifier.
   * @param {string} text - narrative message
   * @param {string|null} modifier - 'warning', 'danger', 'success', or null for default
   */
  function setNarrative(text, modifier) {
    const banner = document.getElementById('narrativeBanner');
    if (!banner) return;
    const textEl = document.getElementById('narrativeText');
    if (textEl) textEl.textContent = text;
    banner.className = 'dashboard-grid__narrative'
      + (modifier ? ` dashboard-grid__narrative--${modifier}` : '');
  }

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
    document.getElementById('btnReset')?.addEventListener('click', resetSim);

    // Node popup close
    document.getElementById('nodePopupClose')?.addEventListener('click', closeNodePopup);
    document.getElementById('nodePopup')?.addEventListener('click', (e) => {
      if (e.target.id === 'nodePopup') closeNodePopup();
    });

    // Poll status to restore state on refresh
    pollStatus();
    setInterval(pollStatus, 3000);
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
      setNarrative(`Simulation running \u2014 ${days} days scheduled.`, null);
      Utils.showToast(`Simulation started (${days} days)`, 'success');
    } catch (err) {
      const msg = err.message.includes('permission') || err.message.includes('403')
        ? 'Permission denied — select "operator" or "admin" role (top-right)'
        : err.message;
      Utils.showToast(msg, 'danger');
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
      const vol = document.getElementById('statVolume')?.textContent || '$0';
      const done = document.getElementById('statCompleted')?.textContent || '0';
      setNarrative(`Simulation complete \u2014 ${done} transactions, ${vol} total volume.`, 'success');
      Utils.showToast('Simulation stopped', 'info');
    } catch (err) {
      Utils.showToast(err.message, 'danger');
    }
  }

  /**
   * Reset: stop simulation, re-seed all nodes, clear UI.
   */
  async function resetSim() {
    try {
      await ApiClient.post('/api/simulation/reset');
      disconnectSSE();
      setButtonState('stopped');
      // Reset UI counters
      document.getElementById('dayCounter').textContent = 'Day 0';
      document.getElementById('statCompleted').textContent = '0';
      document.getElementById('statFailed').textContent = '0';
      document.getElementById('statVolume').textContent = '$0';
      clearFeed();
      setNarrative(IDLE_NARRATIVE, null);
      // Reset health rings to neutral, then refresh after backend finishes seeding
      NetworkGraph.resetHealthRings();
      setTimeout(() => NetworkGraph.refreshNodeData(), 500);
      Utils.showToast('All nodes re-seeded with fresh demo data', 'success');
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
      // SSE will auto-reconnect; if sim ended, stop gracefully.
      // Guard prevents stacking multiple recovery polls on rapid errors.
      if (_sseRecovering) return;
      _sseRecovering = true;
      setTimeout(() => {
        pollStatus().then(status => {
          if (!status.running) {
            disconnectSSE();
            setButtonState('stopped');
            const vol = document.getElementById('statVolume')?.textContent || '$0';
            const done = document.getElementById('statCompleted')?.textContent || '0';
            setNarrative(`Simulation complete \u2014 ${done} transactions, ${vol} total volume.`, 'success');
          }
        }).finally(() => { _sseRecovering = false; });
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
    // day_end is a control event with cumulative stats — update counters
    // immediately and skip animation/feed (no transaction to visualize).
    if (event.type === 'day_end') {
      setText('dayCounter', `Day ${event.day}`);
      setText('statCompleted', event.completed.toLocaleString());
      setText('statFailed', event.failed.toLocaleString());
      setText('statVolume', Utils.formatCurrency(event.volume));
      if (event.narrative) setNarrative(event.narrative, null);
      return;
    }

    // Scenario events use description as narrative with colored modifier
    if (event.type === 'scenario' && event.description) {
      const modifier = SCENARIO_MODIFIERS[event.event_type] ?? null;
      setNarrative(event.description, modifier);
    }

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
   * Classify an event into type metadata.
   * @returns {{ typeClass, typeLabel, detailText, statusLabel, statusClass }}
   */
  function classifyEvent(event) {
    let typeClass = 'default';
    let typeLabel = '???';
    let detailText = '';
    let statusLabel = '';
    let statusClass = '';

    if (event.type === 'scenario') {
      typeClass = 'scenario';
      typeLabel = 'SCN';
      detailText = `${event.event_type}: ${Utils.truncate(event.description, 55)}`;
    } else if (event.type === 'external' || event.type === 'settlement') {
      typeClass = 'settlement';
      typeLabel = 'STL';
      detailText = `${event.bank}\u2192${event.dest_bank} $${event.amount?.toFixed(2) || '0.00'}`;
      statusLabel = event.status === 'COMPLETED' ? 'OK' : 'FAIL';
      statusClass = statusLabel === 'OK' ? 'ok' : 'fail';
    } else if (event.type === 'deposit') {
      typeClass = 'deposit';
      typeLabel = 'DEP';
      detailText = `${event.bank} ${event.account} $${event.amount?.toFixed(2) || '0.00'}`;
      statusLabel = event.status === '00' ? 'OK' : 'FAIL';
      statusClass = statusLabel === 'OK' ? 'ok' : 'fail';
    } else if (event.type === 'withdraw') {
      typeClass = 'withdraw';
      typeLabel = 'WDR';
      detailText = `${event.bank} ${event.account} $${event.amount?.toFixed(2) || '0.00'}`;
      statusLabel = event.status === '00' ? 'OK' : 'FAIL';
      statusClass = statusLabel === 'OK' ? 'ok' : 'fail';
    } else if (event.dest_bank || (event.description || '').includes('\u2192')) {
      typeClass = 'transfer';
      typeLabel = 'TFR';
      detailText = `${event.bank}\u2192${event.dest_bank || '?'} $${event.amount?.toFixed(2) || '0.00'}`;
      statusLabel = event.status === '00' || event.status === 'COMPLETED' ? 'OK' : 'FAIL';
      statusClass = statusLabel === 'OK' ? 'ok' : 'fail';
    } else {
      typeClass = 'default';
      typeLabel = (event.type || '???').toUpperCase().slice(0, 3);
      detailText = `${event.bank || ''} ${event.account || ''} $${event.amount?.toFixed(2) || '0.00'}`;
      statusLabel = event.status === '00' ? 'OK' : event.status === 'COMPLETED' ? 'OK' : 'FAIL';
      statusClass = statusLabel === 'OK' ? 'ok' : 'fail';
    }

    // Override for error/compliance scenarios
    const desc = (event.description || '') + (event.event_type || '');
    if (/VERIFY_FAIL/i.test(desc)) statusClass = 'fail';
    if (/TAMPER_BALANCE/i.test(event.event_type || '')) typeClass = 'error';

    return { typeClass, typeLabel, detailText, statusLabel, statusClass };
  }

  /**
   * Determine which panel(s) an event should appear in.
   * @returns {'out'|'in'|'both'|'banner'}
   */
  function classifyDirection(event) {
    if (event.type === 'scenario') return 'banner';
    if (event.type === 'deposit') return 'in';
    if (event.type === 'withdraw') return 'out';
    if (event.type === 'external' || event.type === 'settlement') return 'both';
    return 'out';
  }

  /**
   * Build a feed item DOM element.
   * @param {object} event - SSE event data
   * @param {object} classification - from classifyEvent()
   * @param {'out'|'in'|null} side - which panel this copy is for (null = scenario banner)
   */
  function buildFeedItemEl(event, classification, side) {
    const { typeClass, typeLabel, statusLabel, statusClass } = classification;
    let { detailText } = classification;

    // Direction-specific detail text for transfers/settlements
    if (side && (event.type === 'external' || event.type === 'settlement')) {
      const amt = `$${event.amount?.toFixed(2) || '0.00'}`;
      if (side === 'out') {
        detailText = `${event.bank} \u2192 ${event.dest_bank} -${amt}`;
      } else {
        detailText = `${event.dest_bank} \u2190 ${event.bank} +${amt}`;
      }
    }

    const item = document.createElement('div');
    item.className = `feed__item feed__item--${typeClass}`;

    const dayBadge = document.createElement('span');
    dayBadge.className = 'feed__day';
    dayBadge.textContent = `D${event.day || '?'}`;

    const typeBadge = document.createElement('span');
    typeBadge.className = `feed__type feed__type--${typeClass}`;
    typeBadge.textContent = typeLabel;

    const details = document.createElement('span');
    details.className = 'feed__details';
    details.textContent = detailText;

    item.append(dayBadge, typeBadge, details);

    if (statusLabel) {
      const status = document.createElement('span');
      status.className = `feed__status feed__status--${statusClass}`;
      status.textContent = statusLabel;
      item.appendChild(status);
    }

    return item;
  }

  /**
   * Insert an item at the top of a panel list, capping at MAX_FEED.
   */
  function appendToPanel(listEl, item) {
    // Remove empty state message
    const emptyEl = listEl.querySelector('.feed__empty');
    if (emptyEl) emptyEl.remove();

    listEl.insertBefore(item, listEl.firstChild);

    while (listEl.children.length > MAX_FEED) {
      listEl.removeChild(listEl.lastChild);
    }
  }

  /**
   * Add an item to the transaction log (split into outgoing/incoming panels).
   * Structured 4-column layout: day badge | type badge | details | status.
   */
  function addFeedItem(event) {
    const listOut = document.getElementById('feedListOut');
    const listIn = document.getElementById('feedListIn');
    const listSystem = document.getElementById('feedListSystem');
    if (!listOut || !listIn) return;

    const classification = classifyEvent(event);
    const direction = classifyDirection(event);

    if (direction === 'banner') {
      // Route scenario/system events to the System panel
      if (listSystem) {
        const item = buildFeedItemEl(event, classification, null);
        appendToPanel(listSystem, item);
        feedCountSystem++;
        setText('feedCountSystem', feedCountSystem.toString());
      }
    }

    if (direction === 'both' || direction === 'out') {
      const item = buildFeedItemEl(event, classification, 'out');
      appendToPanel(listOut, item);
      feedCountOut++;
      setText('feedCountOut', feedCountOut.toString());
    }

    if (direction === 'both' || direction === 'in') {
      const item = buildFeedItemEl(event, classification, 'in');
      appendToPanel(listIn, item);
      feedCountIn++;
      setText('feedCountIn', feedCountIn.toString());
    }

    // Update total badge
    setText('feedCountTotal', (feedCountOut + feedCountIn + feedCountSystem).toString());
  }

  /**
   * Clear the transaction log.
   */
  function clearFeed() {
    const listOut = document.getElementById('feedListOut');
    const listIn = document.getElementById('feedListIn');
    const listSystem = document.getElementById('feedListSystem');
    if (listOut) listOut.innerHTML = '';
    if (listIn) listIn.innerHTML = '';
    if (listSystem) listSystem.innerHTML = '';
    feedCountOut = 0;
    feedCountIn = 0;
    feedCountSystem = 0;
    setText('feedCountOut', '0');
    setText('feedCountIn', '0');
    setText('feedCountSystem', '0');
    setText('feedCountTotal', '0');
    // Clear COBOL terminal log
    if (typeof CobolViewer !== 'undefined' && CobolViewer.clearLog) {
      CobolViewer.clearLog();
    }
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
      setNarrative(`BANK_C\u2019s balance was corrupted to $${result.new_amount.toLocaleString()}. Run Integrity Check to detect it.`, 'danger');
      Utils.showToast(`Tampered ${result.node}/${result.account_id} \u2192 $${result.new_amount.toLocaleString()}`, 'danger');
    } catch (err) {
      Utils.showToast(err.message, 'danger');
    }
  }

  /**
   * Run cross-node verification.
   */
  async function verifyAll() {
    const btn = document.getElementById('btnVerify');
    const origText = btn?.textContent || 'Integrity Check';

    try {
      // Show loading state
      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Checking\u2026';
      }
      NetworkGraph.pulseAllRings(5000);

      const result = await ApiClient.post('/api/settlement/verify');
      const intact = result.all_chains_intact;
      const matched = result.all_settlements_matched;
      const type = (intact && matched) ? 'success' : 'danger';
      const msg = intact && matched
        ? `All chains intact, ${result.settlements_checked} settlements matched`
        : `Issues: ${result.anomalies?.length || 0} anomalies detected`;
      if (intact && matched) {
        setNarrative('All chains intact. SHA-256 hashes verified across all 6 nodes.', 'success');
      } else {
        setNarrative(`Integrity breach detected \u2014 ${result.anomalies?.length || 0} anomalies found.`, 'danger');
      }
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
    } finally {
      // Restore button
      if (btn) {
        btn.disabled = false;
        btn.textContent = origText;
      }
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
      // Fetch accounts and chain verify in parallel; chain verify may 403
      // for non-auditor roles (operator has chain.view but not chain.verify)
      const [accounts, chain] = await Promise.all([
        ApiClient.get(`/api/nodes/${nodeName}/accounts`),
        ApiClient.post(`/api/nodes/${nodeName}/chain/verify`).catch(err => {
          if (err.message?.includes('403') || err.message?.includes('permission'))
            return { denied: true };
          throw err;
        }),
      ]);

      let html = '';

      // Chain info (graceful degradation for non-auditor roles)
      if (chain.denied) {
        html += `<div class="node-detail__chain" style="color: var(--text-muted);">
          <span class="health-dot"></span>
          <span>Chain verification requires auditor role</span>
        </div>`;
      } else {
        const chainOk = chain.valid;
        html += `<div class="node-detail__chain">
          <span class="health-dot health-dot--${chainOk ? 'ok' : 'error'}"></span>
          <span>Chain: ${chain.entries_checked} entries, ${chainOk ? 'INTACT' : 'BROKEN'} (${chain.time_ms.toFixed(1)}ms)</span>
        </div>`;
      }

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

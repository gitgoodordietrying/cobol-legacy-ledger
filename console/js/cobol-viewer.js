/**
 * cobol-viewer.js -- Live COBOL execution terminal + full-file modal.
 *
 * The terminal is a plain-text append-only log of simulation events,
 * batched via requestAnimationFrame to avoid browser crashes at high
 * event rates. No per-event syntax highlighting or source fetching.
 *
 * The modal (opened on click) still fetches and highlights full COBOL
 * source files using a single pre-compiled regex — called only on
 * user interaction, never on the hot path.
 */

const CobolViewer = (() => {

  // ── Terminal state ──────────────────────────────────────────────
  const MAX_LINES = 200;
  let lineCount = 0;
  let buffer = [];         // Lines queued between animation frames
  let rafPending = false;

  // ── Modal state ─────────────────────────────────────────────────
  const fileCache = {};
  let currentFile = 'SMOKETEST.cob';

  // ── Syntax highlighting (modal only) ────────────────────────────
  // Pre-compiled combined regex — one pass instead of 63 individual
  // replacements. Only used when the user opens the source modal.
  const KEYWORDS = [
    'ACCEPT', 'ADD', 'ALTER', 'CALL', 'CLOSE', 'COMPUTE', 'CONTINUE',
    'DELETE', 'DISPLAY', 'DIVIDE', 'EVALUATE', 'EXIT', 'GO', 'GOBACK',
    'IF', 'INITIALIZE', 'INSPECT', 'MOVE', 'MULTIPLY', 'OPEN', 'PERFORM',
    'READ', 'RETURN', 'REWRITE', 'SEARCH', 'SET', 'SORT', 'START',
    'STOP', 'STRING', 'SUBTRACT', 'UNSTRING', 'WRITE',
    'WHEN', 'OTHER', 'NOT', 'AND', 'OR', 'THAN', 'GREATER', 'LESS',
    'EQUAL', 'TO', 'FROM', 'BY', 'GIVING', 'INTO', 'USING', 'VARYING',
    'UNTIL', 'THRU', 'THROUGH', 'ALSO', 'AFTER', 'BEFORE',
    'SECTION', 'PARAGRAPH', 'COPY', 'REPLACING',
    'PIC', 'PICTURE', 'VALUE', 'OCCURS', 'REDEFINES', 'FILLER',
    'WORKING-STORAGE', 'FILE', 'FD', 'SD', 'RECORD', 'CONTAINS',
    'END-IF', 'END-EVALUATE', 'END-PERFORM', 'END-READ', 'END-WRITE',
    'END-COMPUTE', 'END-STRING', 'END-SEARCH', 'END-CALL',
    'ROUNDED', 'ON', 'SIZE', 'ERROR', 'OVERFLOW',
    'SELECT', 'ASSIGN', 'ORGANIZATION', 'ACCESS', 'MODE', 'STATUS',
    'SEQUENTIAL', 'LINE', 'ADVANCING', 'WITH', 'TEST',
    'TRUE', 'FALSE', 'SPACES', 'ZEROS', 'ZEROES', 'HIGH-VALUES', 'LOW-VALUES',
    'IDENTIFICATION', 'ENVIRONMENT', 'DATA', 'PROCEDURE', 'DIVISION',
  ];

  const COBOL_KW_RE = new RegExp('\\b(' + KEYWORDS.join('|') + ')\\b', 'g');
  const DIVISIONS_SET = new Set([
    'IDENTIFICATION', 'ENVIRONMENT', 'DATA', 'PROCEDURE', 'DIVISION',
  ]);

  /**
   * Apply syntax highlighting to a single line (modal only).
   * One regex pass instead of 63 individual replacements.
   */
  function highlightLine(line) {
    // Comment lines (column 7 = '*')
    if (line.length >= 7 && line[6] === '*') {
      return `<span class="cobol-cmt">${Utils.escapeHtml(line)}</span>`;
    }

    let html = Utils.escapeHtml(line);

    // String literals
    html = html.replace(/(&quot;[^&]*&quot;|&#39;[^&]*&#39;|"[^"]*"|'[^']*')/g,
      '<span class="cobol-str">$1</span>');

    // Numeric literals
    html = html.replace(/\b(\d+\.?\d*)\b/g, '<span class="cobol-num">$1</span>');

    // Keywords + divisions in one pass
    html = html.replace(COBOL_KW_RE, (match) => {
      const cls = DIVISIONS_SET.has(match) ? 'cobol-div' : 'cobol-kw';
      return `<span class="${cls}">${match}</span>`;
    });

    return html;
  }

  // ── Terminal: format + flush ────────────────────────────────────

  /**
   * Format a simulation event into a fixed-width terminal line.
   */
  function formatEvent(event) {
    const time = event.timestamp ? event.timestamp.slice(11, 16) : '--:--';
    const bank = (event.bank || '???').padEnd(7);
    const type = (event.type || '???').toUpperCase().slice(0, 3).padEnd(3);
    const acct = (event.account || '').padEnd(10);
    const amt = event.amount != null ? `$${event.amount.toFixed(2)}` : '';
    const ok = event.status === '00' || event.status === 'COMPLETED';
    const status = ok ? 'OK' : 'FAIL';
    return { text: `${time}  ${bank}  ${type}  ${acct}  ${amt.padStart(12)}  ${status}`, ok };
  }

  /**
   * Flush buffered lines to the DOM in a single reflow.
   * Called once per animation frame at most.
   */
  function flush() {
    rafPending = false;
    const termEl = document.getElementById('cobolTerminal');
    if (!termEl || buffer.length === 0) return;

    // Cap buffer before touching DOM — discard oldest if more events
    // arrived between frames than we can display
    if (buffer.length > MAX_LINES) {
      buffer = buffer.slice(-MAX_LINES);
    }

    // Build a fragment with buffered lines
    const frag = document.createDocumentFragment();
    for (const entry of buffer) {
      const div = document.createElement('div');
      div.textContent = entry.text;
      if (!entry.ok) div.style.color = 'var(--danger)';
      frag.appendChild(div);
    }
    buffer = [];
    termEl.appendChild(frag);

    // Trim excess from the front
    const overflow = termEl.children.length - MAX_LINES;
    if (overflow > 0) {
      for (let i = 0; i < overflow; i++) {
        termEl.removeChild(termEl.firstChild);
      }
    }

    // Auto-scroll
    termEl.scrollTop = termEl.scrollHeight;

    // Update badge
    const badge = document.getElementById('cobolProgramBadge');
    if (badge) badge.textContent = lineCount;
  }

  /**
   * Queue an event for display. Called on every SSE event — the actual
   * DOM work is deferred to the next animation frame via flush().
   */
  function highlightForEvent(event) {
    // Skip day_end summary events (no transaction data)
    if (event.type === 'day_end') return;

    lineCount++;

    // Clear placeholder on first real event
    if (lineCount === 1) {
      const termEl = document.getElementById('cobolTerminal');
      if (termEl) termEl.innerHTML = '';
    }

    buffer.push(formatEvent(event));
    if (!rafPending) {
      rafPending = true;
      requestAnimationFrame(flush);
    }
  }

  /**
   * Clear terminal and reset counter.
   */
  function clearLog() {
    const termEl = document.getElementById('cobolTerminal');
    if (termEl) {
      termEl.innerHTML = '<span style="color: var(--text-muted)">Start a simulation to see live COBOL execution</span>';
    }
    lineCount = 0;
    buffer = [];
    rafPending = false;
    const badge = document.getElementById('cobolProgramBadge');
    if (badge) badge.textContent = '\u2014';
  }

  // ── Modal: fetch + display full source ──────────────────────────

  /**
   * Fetch and cache a COBOL source file.
   */
  async function fetchFile(filename) {
    if (!fileCache[filename]) {
      const resp = await fetch(`/cobol-source/${filename}`);
      if (!resp.ok) throw new Error(`${resp.status}`);
      fileCache[filename] = await resp.text();
    }
    return fileCache[filename];
  }

  /**
   * Show a full COBOL file in the modal with syntax highlighting.
   */
  async function showFullFile(filename) {
    const sourceEl = document.getElementById('cobolModalSource');
    if (!sourceEl) return;

    try {
      const source = await fetchFile(filename);
      const lines = source.split('\n');
      sourceEl.innerHTML = lines.map(highlightLine).join('\n');
    } catch {
      sourceEl.innerHTML = `<span style="color: var(--danger)">Failed to load ${Utils.escapeHtml(filename)}</span>`;
    }
  }

  /**
   * Open the full-file modal.
   */
  function openModal(filename) {
    const modal = document.getElementById('cobolModal');
    const title = document.getElementById('cobolModalTitle');
    const select = document.getElementById('cobolFileSelect');
    if (!modal) return;

    currentFile = filename;
    if (title) title.textContent = filename;
    if (select) select.value = filename;
    modal.style.display = 'flex';
    showFullFile(filename);
  }

  /**
   * Close the full-file modal.
   */
  function closeModal() {
    const modal = document.getElementById('cobolModal');
    if (modal) modal.style.display = 'none';
  }

  /**
   * Initialize: wire up file name click and modal controls.
   */
  function init() {
    // "Browse Source" click → open modal
    document.getElementById('cobolFileName')?.addEventListener('click', () => {
      openModal(currentFile);
    });

    // Modal close button
    document.getElementById('cobolModalClose')?.addEventListener('click', closeModal);

    // Modal overlay click to close
    document.getElementById('cobolModal')?.addEventListener('click', (e) => {
      if (e.target.id === 'cobolModal') closeModal();
    });

    // Escape key closes modal
    document.getElementById('cobolModal')?.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeModal();
    });

    // Modal file selector
    const select = document.getElementById('cobolFileSelect');
    if (select) {
      select.addEventListener('change', () => {
        currentFile = select.value;
        showFullFile(select.value);
      });
    }
  }

  return { init, highlightForEvent, clearLog };
})();

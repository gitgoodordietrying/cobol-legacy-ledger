/**
 * cobol-viewer.js -- Live COBOL ticker with full-file modal.
 *
 * Maps transaction types to relevant .cob files and paragraphs. The ticker
 * shows only the active paragraph (~15-30 lines) during simulation. Clicking
 * the file name opens a modal with the full source and paragraph highlighted.
 */

const CobolViewer = (() => {

  // Cache of loaded source files
  const fileCache = {};
  let currentFile = 'SMOKETEST.cob';
  let currentParagraph = null;

  // Map transaction type → file + paragraph for auto-navigation
  const TX_MAP = {
    deposit:   { file: 'TRANSACT.cob', para: 'PROCESS-DEPOSIT' },
    withdraw:  { file: 'TRANSACT.cob', para: 'PROCESS-WITHDRAW' },
    transfer:  { file: 'TRANSACT.cob', para: 'PROCESS-TRANSFER' },
    external:  { file: 'SETTLE.cob',   para: 'EXECUTE-SETTLEMENT' },
    interest:  { file: 'INTEREST.cob', para: 'COMPUTE-INTEREST' },
    fee:       { file: 'FEES.cob',     para: 'ASSESS-FEES' },
  };

  // Scenario event → file mapping
  const SCENARIO_MAP = {
    FREEZE_ACCOUNT:   { file: 'ACCOUNTS.cob', para: 'UPDATE-ACCOUNT-STATUS' },
    CLOSE_ACCOUNT:    { file: 'ACCOUNTS.cob', para: 'UPDATE-ACCOUNT-STATUS' },
    TAMPER_BALANCE:   { file: 'RECONCILE.cob', para: 'RECONCILE-ACCOUNT' },
    LARGE_TRANSFER:   { file: 'SETTLE.cob', para: 'EXECUTE-SETTLEMENT' },
    DRAIN_TRANSFERS:  { file: 'TRANSACT.cob', para: 'PROCESS-TRANSFER' },
    SUSPICIOUS_BURST: { file: 'TRANSACT.cob', para: 'PROCESS-DEPOSIT' },
  };

  // COBOL keywords for syntax highlighting
  const KEYWORDS = new Set([
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
  ]);

  const DIVISIONS = ['IDENTIFICATION', 'ENVIRONMENT', 'DATA', 'PROCEDURE', 'DIVISION'];

  /**
   * Apply basic syntax highlighting to a single line of COBOL.
   */
  function highlightLine(line) {
    if (line.length >= 7 && line[6] === '*') {
      return `<span class="cobol-cmt">${Utils.escapeHtml(line)}</span>`;
    }

    let html = Utils.escapeHtml(line);

    html = html.replace(/(&quot;[^&]*&quot;|&#39;[^&]*&#39;|"[^"]*"|'[^']*')/g,
      '<span class="cobol-str">$1</span>');

    html = html.replace(/\b(\d+\.?\d*)\b/g, '<span class="cobol-num">$1</span>');

    DIVISIONS.forEach(d => {
      const re = new RegExp(`\\b(${d})\\b`, 'g');
      html = html.replace(re, '<span class="cobol-div">$1</span>');
    });

    KEYWORDS.forEach(kw => {
      const re = new RegExp(`\\b(${kw})\\b`, 'g');
      html = html.replace(re, '<span class="cobol-kw">$1</span>');
    });

    return html;
  }

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
   * Find the start and end line indices of a paragraph in COBOL source.
   * Returns { start, end } or null if not found.
   */
  function findParagraph(lines, paragraphName) {
    if (!paragraphName) return null;
    let paraStart = -1;
    for (let i = 0; i < lines.length; i++) {
      const trimmed = lines[i].trim();
      if (trimmed.startsWith(paragraphName + '.') || trimmed === paragraphName + '.') {
        paraStart = i;
      } else if (paraStart >= 0 && /^[A-Z][A-Z0-9-]*\.\s*$/.test(trimmed)) {
        return { start: paraStart, end: i };
      }
    }
    if (paraStart >= 0) return { start: paraStart, end: lines.length };
    return null;
  }

  /**
   * Show a paragraph snippet in the ticker (compact, just the active paragraph).
   */
  async function showSnippet(filename, paragraphName) {
    const sourceEl = document.getElementById('cobolSource');
    const fileEl = document.getElementById('cobolFileName');
    const paraEl = document.getElementById('cobolParagraph');
    const badgeEl = document.getElementById('cobolProgramBadge');
    if (!sourceEl) return;

    currentFile = filename;
    currentParagraph = paragraphName;

    if (fileEl) fileEl.textContent = filename;
    if (paraEl) paraEl.textContent = paragraphName || '\u2014';
    if (badgeEl) badgeEl.textContent = filename.replace('.cob', '');

    try {
      const source = await fetchFile(filename);
      const lines = source.split('\n');
      const range = findParagraph(lines, paragraphName);

      if (range) {
        const snippet = lines.slice(range.start, range.end);
        const html = snippet.map(line => {
          const highlighted = highlightLine(line);
          return `<span class="cobol-highlight">${highlighted}</span>`;
        }).join('\n');
        sourceEl.innerHTML = html;
      } else {
        // No paragraph found — show first 30 lines as context
        const preview = lines.slice(0, 30);
        sourceEl.innerHTML = preview.map(highlightLine).join('\n');
      }
    } catch {
      sourceEl.innerHTML = `<span style="color: var(--danger)">Failed to load ${Utils.escapeHtml(filename)}</span>`;
    }
  }

  /**
   * Show a full COBOL file in the modal with optional paragraph highlighted.
   */
  async function showFullFile(filename, paragraphName) {
    const sourceEl = document.getElementById('cobolModalSource');
    if (!sourceEl) return;

    try {
      const source = await fetchFile(filename);
      const lines = source.split('\n');
      const range = findParagraph(lines, paragraphName);

      const html = lines.map((line, i) => {
        const highlighted = highlightLine(line);
        if (range && i >= range.start && i < range.end) {
          return `<span class="cobol-highlight">${highlighted}</span>`;
        }
        return highlighted;
      }).join('\n');

      sourceEl.innerHTML = html;

      // Auto-scroll to highlighted paragraph
      if (range) {
        requestAnimationFrame(() => {
          const highlightEl = sourceEl.querySelector('.cobol-highlight');
          if (highlightEl) {
            highlightEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        });
      }
    } catch {
      sourceEl.innerHTML = `<span style="color: var(--danger)">Failed to load ${Utils.escapeHtml(filename)}</span>`;
    }
  }

  /**
   * Open the full-file modal.
   */
  function openModal(filename, paragraphName) {
    const modal = document.getElementById('cobolModal');
    const title = document.getElementById('cobolModalTitle');
    const select = document.getElementById('cobolFileSelect');
    if (!modal) return;

    if (title) title.textContent = filename;
    if (select) select.value = filename;
    modal.style.display = 'flex';
    showFullFile(filename, paragraphName);
  }

  /**
   * Close the full-file modal.
   */
  function closeModal() {
    const modal = document.getElementById('cobolModal');
    if (modal) modal.style.display = 'none';
  }

  /**
   * Auto-navigate ticker based on a simulation event.
   * Debounced to 300ms to avoid redundant renders during event bursts.
   */
  let _hlTimer = null;
  function highlightForEvent(event) {
    let mapping = null;

    if (event.type === 'scenario' && event.event_type) {
      mapping = SCENARIO_MAP[event.event_type];
    } else if (event.type) {
      mapping = TX_MAP[event.type];
    }

    if (mapping) {
      clearTimeout(_hlTimer);
      _hlTimer = setTimeout(() => showSnippet(mapping.file, mapping.para), 300);
    }
  }

  /**
   * Initialize: wire up file name click, modal controls.
   */
  function init() {
    // File name click → open modal
    document.getElementById('cobolFileName')?.addEventListener('click', () => {
      openModal(currentFile, currentParagraph);
    });

    // Modal close button
    document.getElementById('cobolModalClose')?.addEventListener('click', closeModal);

    // Modal overlay click to close
    document.getElementById('cobolModal')?.addEventListener('click', (e) => {
      if (e.target.id === 'cobolModal') closeModal();
    });

    // Modal file selector
    const select = document.getElementById('cobolFileSelect');
    if (select) {
      select.addEventListener('change', () => showFullFile(select.value, null));
    }
  }

  return { init, highlightForEvent, showSnippet };
})();

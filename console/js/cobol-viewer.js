/**
 * cobol-viewer.js -- COBOL source display with syntax highlighting.
 *
 * Maps transaction types to relevant .cob files and paragraphs. Provides
 * basic syntax highlighting (keywords, strings, numbers, comments, divisions).
 * Auto-highlights the active paragraph when a simulation event fires.
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
   * @param {string} line
   * @returns {string} HTML-escaped line with <span> tags
   */
  function highlightLine(line) {
    // Comment lines (column 7 = *)
    if (line.length >= 7 && line[6] === '*') {
      return `<span class="cobol-cmt">${Utils.escapeHtml(line)}</span>`;
    }

    let html = Utils.escapeHtml(line);

    // Strings (single or double quoted)
    html = html.replace(/(&quot;[^&]*&quot;|&#39;[^&]*&#39;|"[^"]*"|'[^']*')/g,
      '<span class="cobol-str">$1</span>');

    // Numbers (standalone numeric literals)
    html = html.replace(/\b(\d+\.?\d*)\b/g, '<span class="cobol-num">$1</span>');

    // Division headers
    DIVISIONS.forEach(d => {
      const re = new RegExp(`\\b(${d})\\b`, 'g');
      html = html.replace(re, '<span class="cobol-div">$1</span>');
    });

    // Keywords
    KEYWORDS.forEach(kw => {
      const re = new RegExp(`\\b(${kw})\\b`, 'g');
      html = html.replace(re, '<span class="cobol-kw">$1</span>');
    });

    return html;
  }

  /**
   * Load and display a COBOL source file.
   * @param {string} filename
   * @param {string|null} paragraphName - paragraph to highlight
   */
  async function loadFile(filename, paragraphName = null) {
    const sourceEl = document.getElementById('cobolSource');
    const paraEl = document.getElementById('cobolParagraph');
    if (!sourceEl) return;

    currentFile = filename;
    currentParagraph = paragraphName;

    // Update file selector
    const select = document.getElementById('cobolFileSelect');
    if (select) select.value = filename;
    if (paraEl) paraEl.textContent = paragraphName || '\u2014';

    // Check cache
    if (!fileCache[filename]) {
      try {
        const resp = await fetch(`/cobol-source/${filename}`);
        if (!resp.ok) throw new Error(`${resp.status}`);
        fileCache[filename] = await resp.text();
      } catch {
        sourceEl.innerHTML = `<span style="color: var(--danger)">Failed to load ${Utils.escapeHtml(filename)}</span>`;
        return;
      }
    }

    const source = fileCache[filename];
    const lines = source.split('\n');

    // Find paragraph line indices for highlighting
    let paraStart = -1;
    let paraEnd = lines.length;
    if (paragraphName) {
      for (let i = 0; i < lines.length; i++) {
        const trimmed = lines[i].trim();
        if (trimmed.startsWith(paragraphName + '.') || trimmed === paragraphName + '.') {
          paraStart = i;
        } else if (paraStart >= 0 && /^[A-Z][A-Z0-9-]*\.\s*$/.test(trimmed)) {
          paraEnd = i;
          break;
        }
      }
    }

    // Render with highlighting
    const html = lines.map((line, i) => {
      const highlighted = highlightLine(line);
      if (i >= paraStart && i < paraEnd && paraStart >= 0) {
        return `<span class="cobol-highlight">${highlighted}</span>`;
      }
      return highlighted;
    }).join('\n');

    sourceEl.innerHTML = html;

    // Auto-scroll to highlighted paragraph
    if (paraStart >= 0) {
      const highlightEl = sourceEl.querySelector('.cobol-highlight');
      if (highlightEl) {
        highlightEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }

  /**
   * Auto-navigate viewer based on a simulation event.
   * @param {object} event - SSE event data
   */
  function highlightForEvent(event) {
    let mapping = null;

    if (event.type === 'scenario' && event.event_type) {
      mapping = SCENARIO_MAP[event.event_type];
    } else if (event.type) {
      mapping = TX_MAP[event.type];
    }

    if (mapping) {
      loadFile(mapping.file, mapping.para);
    }
  }

  /**
   * Initialize: load default file and wire up file selector.
   */
  function init() {
    const select = document.getElementById('cobolFileSelect');
    if (select) {
      select.addEventListener('change', () => loadFile(select.value));
    }
    loadFile('SMOKETEST.cob');
  }

  return { init, loadFile, highlightForEvent };
})();

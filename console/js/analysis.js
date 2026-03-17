/**
 * analysis.js -- Controller for the Analysis view tab.
 *
 * Wires up the analysis controls to the call-graph and compare-viewer
 * components. Fetches COBOL source from /cobol-source/ and sends it to
 * the /api/analysis/ endpoints for call graph, complexity, dead code,
 * and comparison rendering.
 */

const Analysis = (() => {

  // Source cache (file name -> source text)
  const sourceCache = {};
  // Trace cache (paragraph name -> execution path)
  const traceCache = {};

  // Payroll files are served from a different path
  const PAYROLL_FILES = new Set([
    'PAYROLL.cob', 'TAXCALC.cob', 'DEDUCTN.cob', 'PAYBATCH.cob',
    'MERCHANT.cob', 'FEEENGN.cob', 'DISPUTE.cob', 'RISKCHK.cob',
  ]);

  /**
   * Fetch COBOL source text for a given filename.
   */
  async function fetchSource(filename) {
    if (sourceCache[filename]) return sourceCache[filename];

    const basePath = PAYROLL_FILES.has(filename)
      ? '/cobol-source/payroll/'
      : '/cobol-source/';

    try {
      const resp = await fetch(`${basePath}${filename}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status} for ${basePath}${filename}`);
      const text = await resp.text();
      sourceCache[filename] = text;
      return text;
    } catch (e) {
      Utils.showToast(`Failed to load ${filename}: ${e.message}`, 'danger');
      return null;
    }
  }

  /**
   * Run full analysis on the selected file.
   */
  async function analyzeFile() {
    const select = document.getElementById('analysisFileSelect');
    const filename = select.value;
    const source = await fetchSource(filename);
    if (!source) return;

    Utils.showToast(`Analyzing ${filename}...`, 'info');
    const startTime = performance.now();

    try {
      // Run all analysis endpoints in parallel
      const [graphData, complexityData, deadCodeData] = await Promise.all([
        ApiClient.post('/api/analysis/call-graph', { source_text: source }),
        ApiClient.post('/api/analysis/complexity', { source_text: source }),
        ApiClient.post('/api/analysis/dead-code', { source_text: source }),
      ]);

      const elapsedMs = Math.round(performance.now() - startTime);

      // Render call graph
      CallGraphView.render(graphData, complexityData, deadCodeData);
      CallGraphView.renderLegend('callGraphLegend');

      // Update summary with Human vs AI timer
      const lineCount = source.split('\n').length;
      renderSummary(complexityData, deadCodeData, elapsedMs, lineCount);

      // Clear previous traces and populate new entry points
      clearTraces();
      populateEntryPoints(graphData.paragraphs || []);

      // Show analysis grid, hide compare
      document.getElementById('analysisGrid').style.display = '';
      document.getElementById('compareCard').style.display = 'none';

      Utils.showToast(`${filename}: ${complexityData.rating} (score ${complexityData.total_score})`, 'success');
    } catch (e) {
      Utils.showToast(`Analysis failed: ${e.message}`, 'danger');
    }
  }

  /**
   * Render the summary stats bar.
   */
  function renderSummary(cx, dc, elapsedMs, lineCount) {
    const el = document.getElementById('analysisSummary');
    if (!el) return;

    const ratingClass = cx.rating === 'clean' ? 'clean'
      : cx.rating === 'moderate' ? 'moderate' : 'spaghetti';

    // Human estimate: spaghetti code ~50 lines/hour, clean ~200 lines/hour
    const linesPerHour = cx.rating === 'spaghetti' ? 50 : cx.rating === 'moderate' ? 100 : 200;
    const humanHours = lineCount / linesPerHour;
    const humanEstimate = humanHours < 8 ? `${Math.ceil(humanHours)} hours`
      : humanHours < 40 ? `${Math.ceil(humanHours / 8)} days`
      : `${Math.ceil(humanHours / 40)} weeks`;

    el.innerHTML = `
      <div class="analysis-stat">
        <div class="analysis-stat__value analysis-stat__value--${ratingClass}">${cx.total_score}</div>
        <div class="analysis-stat__label">Total Score</div>
      </div>
      <div class="analysis-stat">
        <div class="analysis-stat__value">${cx.rating}</div>
        <div class="analysis-stat__label">Rating</div>
      </div>
      <div class="analysis-stat">
        <div class="analysis-stat__value">${Object.keys(cx.paragraphs).length}</div>
        <div class="analysis-stat__label">Paragraphs</div>
      </div>
      <div class="analysis-stat">
        <div class="analysis-stat__value analysis-stat__value--spaghetti">${dc.dead_count}</div>
        <div class="analysis-stat__label">Dead Code</div>
      </div>
      <div class="analysis-timer">
        <span class="analysis-timer__ai">Analyzed in ${elapsedMs}ms</span>
        <span class="analysis-timer__human">Human estimate: ${humanEstimate}</span>
      </div>
    `;
  }

  /**
   * Clear all traces when switching files.
   */
  function clearTraces() {
    // Clear cache
    Object.keys(traceCache).forEach(k => delete traceCache[k]);

    // Reset execution path container
    const container = document.getElementById('execPathContainer');
    if (container) {
      container.innerHTML = '<span style="color: var(--text-muted); font-size: var(--text-xs);">Select an entry point to trace execution</span>';
    }
  }

  /**
   * Populate the trace entry point dropdown.
   */
  function populateEntryPoints(paragraphs) {
    const select = document.getElementById('traceEntrySelect');
    if (!select) return;

    select.innerHTML = '<option value="">Select entry point...</option>';
    paragraphs.forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      select.appendChild(opt);
    });
  }

  /**
   * Trace execution from the selected entry point.
   * @param {string} [overrideEntry] - paragraph name to trace (bypasses dropdown)
   */
  async function traceFromEntry(overrideEntry) {
    const entrySelect = document.getElementById('traceEntrySelect');
    const entry = overrideEntry || entrySelect?.value;
    if (!entry) return;

    // Sync dropdown
    if (entrySelect && !overrideEntry) {
      // Normal flow from dropdown
    } else if (entrySelect) {
      entrySelect.value = entry;
    }

    // Check cache first
    if (traceCache[entry]) {
      highlightTraceGroup(entry);
      return;
    }

    const fileSelect = document.getElementById('analysisFileSelect');
    const source = await fetchSource(fileSelect.value);
    if (!source) return;

    try {
      const data = await ApiClient.post('/api/analysis/trace', {
        source_text: source,
        entry_point: entry,
        max_steps: 100,
      });

      const path = data.execution_path || [];
      traceCache[entry] = path;
      appendTraceGroup(entry, path);
      highlightTraceGroup(entry);
    } catch (e) {
      Utils.showToast(`Trace failed: ${e.message}`, 'danger');
    }
  }

  /**
   * Append a collapsible trace group to the execution path container.
   */
  function appendTraceGroup(entry, path) {
    const container = document.getElementById('execPathContainer');
    if (!container) return;

    // Remove the placeholder text if present
    const placeholder = container.querySelector('span[style]');
    if (placeholder) placeholder.remove();

    const group = document.createElement('div');
    group.className = 'exec-path__group';
    group.dataset.entry = entry;

    const header = document.createElement('div');
    header.className = 'exec-path__group-header';
    header.textContent = `\u25B6 ${entry} (${path.length} steps)`;
    header.addEventListener('click', () => {
      body.classList.toggle('exec-path__group-body--open');
      highlightTraceGroup(entry);
      CallGraphView.setSelectedNode(entry);
    });
    group.appendChild(header);

    const body = document.createElement('div');
    body.className = 'exec-path__group-body';

    if (path.length === 0) {
      body.innerHTML = '<span style="color: var(--text-muted); font-size: var(--text-xs);">No execution path</span>';
    } else {
      path.forEach((step, i) => {
        if (i > 0) {
          const arrow = document.createElement('span');
          const via = step.via || 'sequential';
          arrow.className = `exec-path__arrow exec-path__arrow--${via}`;
          arrow.textContent = via === 'GOTO' ? '\u2192\u2192' : via === 'ALTER\u2192GOTO' ? '\u21D2' : '\u2192';
          arrow.title = via;
          body.appendChild(arrow);
        }
        const stepEl = document.createElement('span');
        stepEl.className = 'exec-path__step';
        stepEl.textContent = step.paragraph;
        if (step.note) stepEl.title = step.note;
        body.appendChild(stepEl);
      });
    }

    body.classList.add('exec-path__group-body--open');
    group.appendChild(body);
    container.appendChild(group);
  }

  /**
   * Highlight the trace group for the given entry point.
   */
  function highlightTraceGroup(entry) {
    const container = document.getElementById('execPathContainer');
    if (!container) return;

    container.querySelectorAll('.exec-path__group').forEach(g => {
      g.classList.remove('exec-path__group--active');
      if (g.dataset.entry === entry) {
        g.classList.add('exec-path__group--active');
        g.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    });
  }

  /**
   * Render the execution path as a visual chain of steps (legacy single-trace).
   */
  function renderExecPath(path) {
    const container = document.getElementById('execPathContainer');
    if (!container) return;
    container.innerHTML = '';

    if (path.length === 0) {
      container.innerHTML = '<span style="color: var(--text-muted); font-size: var(--text-xs);">No execution path</span>';
      return;
    }

    path.forEach((step, i) => {
      // Arrow between steps
      if (i > 0) {
        const arrow = document.createElement('span');
        const via = step.via || 'sequential';
        arrow.className = `exec-path__arrow exec-path__arrow--${via}`;
        arrow.textContent = via === 'GOTO' ? '\u2192\u2192' : via === 'ALTER\u2192GOTO' ? '\u21D2' : '\u2192';
        arrow.title = via;
        container.appendChild(arrow);
      }

      const stepEl = document.createElement('span');
      stepEl.className = 'exec-path__step';
      stepEl.textContent = step.paragraph;
      if (step.note) stepEl.title = step.note;
      container.appendChild(stepEl);
    });
  }

  /**
   * Run the compare view (PAYROLL.cob vs TRANSACT.cob).
   */
  async function runCompare() {
    const sourceA = await fetchSource('PAYROLL.cob');
    const sourceB = await fetchSource('TRANSACT.cob');
    if (!sourceA || !sourceB) {
      Utils.showToast('Could not load files for comparison', 'danger');
      return;
    }

    Utils.showToast('Comparing spaghetti vs clean...', 'info');

    try {
      const data = await ApiClient.post('/api/analysis/compare', {
        source_a: sourceA,
        source_b: sourceB,
        label_a: 'PAYROLL.cob (1974 spaghetti)',
        label_b: 'TRANSACT.cob (clean)',
      });

      CompareViewer.render(data, sourceA, sourceB);

      // Show compare, hide grid
      document.getElementById('analysisGrid').style.display = 'none';
      document.getElementById('compareCard').style.display = '';
    } catch (e) {
      Utils.showToast(`Compare failed: ${e.message}`, 'danger');
    }
  }

  /**
   * Initialize the analysis view.
   */
  function init() {
    CallGraphView.init('callGraphContainer');
    CompareViewer.init('compareContainer');

    // Wire up buttons
    document.getElementById('btnAnalyze')?.addEventListener('click', analyzeFile);
    document.getElementById('btnCompare')?.addEventListener('click', runCompare);
    document.getElementById('btnCrossFile')?.addEventListener('click', runCrossFile);
    document.getElementById('traceEntrySelect')?.addEventListener('change', () => traceFromEntry());
    document.getElementById('btnCloseCompare')?.addEventListener('click', () => {
      document.getElementById('compareCard').style.display = 'none';
      document.getElementById('analysisGrid').style.display = '';
    });
    document.getElementById('btnCloseCrossFile')?.addEventListener('click', () => {
      document.getElementById('crossFileCard').style.display = 'none';
      document.getElementById('analysisGrid').style.display = '';
    });

    // Click-to-trace: listen for cg-node-click events on the call graph container
    document.getElementById('callGraphContainer')?.addEventListener('cg-node-click', (e) => {
      const paragraph = e.detail?.paragraph;
      if (paragraph) {
        traceFromEntry(paragraph);
        CallGraphView.setSelectedNode(paragraph);
      }
    });
  }

  /**
   * Run cross-file analysis on all payroll spaghetti files.
   */
  async function runCrossFile() {
    Utils.showToast('Running cross-file analysis...', 'info');
    const files = [...PAYROLL_FILES];
    const sources = {};

    for (const f of files) {
      const src = await fetchSource(f);
      if (src) sources[f] = src;
    }

    if (Object.keys(sources).length < 2) {
      Utils.showToast('Need at least 2 files for cross-file analysis', 'danger');
      return;
    }

    try {
      const data = await ApiClient.post('/api/analysis/cross-file', { sources });
      Utils.showToast(
        `Cross-file: ${data.total_paragraphs} paragraphs, ${data.cross_edges.length} inter-file edges, total complexity ${data.total_complexity}`,
        'success'
      );

      // Show cross-file card, hide analysis grid + compare
      document.getElementById('analysisGrid').style.display = 'none';
      document.getElementById('compareCard').style.display = 'none';
      document.getElementById('crossFileCard').style.display = '';

      // Render cross-file graph
      CallGraphView.renderCrossFile(data);

      // Render cross-file summary table
      renderCrossFileSummary(data);
    } catch (e) {
      Utils.showToast(`Cross-file analysis failed: ${e.message}`, 'danger');
    }
  }

  /**
   * Render a summary table for cross-file analysis results.
   */
  function renderCrossFileSummary(data) {
    const container = document.getElementById('crossFileSummary');
    if (!container) return;

    const files = data.files || {};
    let html = `<table class="cross-file-summary">
      <thead><tr><th>File</th><th>Paragraphs</th><th>Complexity</th><th>Rating</th></tr></thead>
      <tbody>`;

    Object.entries(files).forEach(([filename, info]) => {
      const score = info.complexity_score || 0;
      const rating = info.complexity_rating || (score >= 100 ? 'spaghetti' : score >= 50 ? 'moderate' : 'clean');
      const ratingClass = rating === 'spaghetti' ? 'spaghetti' : rating === 'moderate' ? 'moderate' : 'clean';
      html += `<tr>
        <td>${Utils.escapeHtml(filename)}</td>
        <td>${(info.paragraphs || []).length}</td>
        <td><span class="complexity-score complexity-score--${ratingClass}">${score}</span></td>
        <td>${rating}</td>
      </tr>`;
    });

    html += `</tbody></table>
      <div style="margin-top: var(--sp-2); font-size: var(--text-xs); color: var(--text-muted);">
        Total: ${data.total_paragraphs} paragraphs, ${data.cross_edges?.length || 0} inter-file edges, combined complexity ${data.total_complexity}
      </div>`;

    container.innerHTML = html;
  }

  return { init };

})();

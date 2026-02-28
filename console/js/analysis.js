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

  // Payroll files are served from a different path
  const PAYROLL_FILES = new Set(['PAYROLL.cob', 'TAXCALC.cob', 'DEDUCTN.cob', 'PAYBATCH.cob']);

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
      if (!resp.ok) throw new Error(`${resp.status}`);
      const text = await resp.text();
      sourceCache[filename] = text;
      return text;
    } catch (e) {
      // Try alternate path for payroll
      if (PAYROLL_FILES.has(filename)) {
        try {
          const resp2 = await fetch(`/cobol-source/${filename}`);
          if (resp2.ok) {
            const text = await resp2.text();
            sourceCache[filename] = text;
            return text;
          }
        } catch { /* fall through */ }
      }
      Utils.showToast(`Failed to load ${filename}: ${e.message}`, 'error');
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

    try {
      // Run all analysis endpoints in parallel
      const [graphData, complexityData, deadCodeData] = await Promise.all([
        ApiClient.post('/api/analysis/call-graph', { source_text: source }),
        ApiClient.post('/api/analysis/complexity', { source_text: source }),
        ApiClient.post('/api/analysis/dead-code', { source_text: source }),
      ]);

      // Render call graph
      CallGraphView.render(graphData, complexityData, deadCodeData);
      CallGraphView.renderLegend('callGraphLegend');

      // Update summary
      renderSummary(complexityData, deadCodeData);

      // Populate trace entry point selector
      populateEntryPoints(graphData.paragraphs || []);

      // Show analysis grid, hide compare
      document.getElementById('analysisGrid').style.display = '';
      document.getElementById('compareCard').style.display = 'none';

      Utils.showToast(`${filename}: ${complexityData.rating} (score ${complexityData.total_score})`, 'success');
    } catch (e) {
      Utils.showToast(`Analysis failed: ${e.message}`, 'error');
    }
  }

  /**
   * Render the summary stats bar.
   */
  function renderSummary(cx, dc) {
    const el = document.getElementById('analysisSummary');
    if (!el) return;

    const ratingClass = cx.rating === 'clean' ? 'clean'
      : cx.rating === 'moderate' ? 'moderate' : 'spaghetti';

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
    `;
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
   */
  async function traceFromEntry() {
    const entrySelect = document.getElementById('traceEntrySelect');
    const entry = entrySelect?.value;
    if (!entry) return;

    const fileSelect = document.getElementById('analysisFileSelect');
    const source = await fetchSource(fileSelect.value);
    if (!source) return;

    try {
      const data = await ApiClient.post('/api/analysis/trace', {
        source_text: source,
        entry_point: entry,
        max_steps: 100,
      });

      renderExecPath(data.execution_path || []);
    } catch (e) {
      Utils.showToast(`Trace failed: ${e.message}`, 'error');
    }
  }

  /**
   * Render the execution path as a visual chain of steps.
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
        arrow.textContent = via === 'GOTO' ? '→→' : via === 'ALTER→GOTO' ? '⇒' : '→';
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
      Utils.showToast('Could not load files for comparison', 'error');
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
      Utils.showToast(`Compare failed: ${e.message}`, 'error');
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
    document.getElementById('traceEntrySelect')?.addEventListener('change', traceFromEntry);
    document.getElementById('btnCloseCompare')?.addEventListener('click', () => {
      document.getElementById('compareCard').style.display = 'none';
      document.getElementById('analysisGrid').style.display = '';
    });
  }

  return { init };

})();

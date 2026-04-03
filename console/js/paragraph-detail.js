/**
 * paragraph-detail.js -- Deep-dive panel for individual COBOL paragraphs.
 *
 * When the user clicks a node in the call graph, this module fetches a
 * full explanation from POST /api/analysis/explain-paragraph and renders
 * a detail panel showing:
 *   - Complexity score + rating badge
 *   - Factor breakdown (each factor links to Knowledge Base)
 *   - Edges: calls-to and called-by lists
 *   - Data flow: fields read (blue) and written (red)
 *   - Dead code / ALTER_CONDITIONAL status
 *
 * The detail panel lives in a tab alongside the Execution Trace panel
 * inside #analysisDetailsCard.  A tab strip toggles between the two.
 *
 * COBOL CONCEPT: explain-paragraph combines ALL analyzers (call graph,
 * complexity, dead code, data flow) focused on a single paragraph --
 * the same multi-tool approach a mainframe analyst would use when
 * investigating a production incident in a 40-year-old program.
 */

const ParagraphDetail = (() => {

  /* ── Knowledge Base cache ──────────────────────────────────────── */

  // Entries keyed by lowercase name for fuzzy matching
  let _kb = {};
  let _kbLoaded = false;

  /**
   * Load the knowledge base JSON (once, on init).
   */
  async function loadKB() {
    if (_kbLoaded) return;
    try {
      const resp = await fetch('/console/data/knowledge-base.json');
      if (!resp.ok) return;
      const data = await resp.json();
      (data.entries || []).forEach(entry => {
        _kb[entry.name.toLowerCase()] = entry;
      });
      _kbLoaded = true;
    } catch (_) {
      // KB is optional -- detail panel works without it
    }
  }

  /**
   * Match a complexity factor string to a KB entry.
   * Factor format examples: "GO TO x3 (+15)", "ALTER x1 (+10)"
   * We strip the count/score suffix and look up the pattern name.
   */
  function matchKB(factorStr) {
    const name = factorStr.replace(/\s*x\d+\s*\(\+\d+\)$/, '').trim();
    const key = name.toLowerCase();

    // Exact match
    if (_kb[key]) return _kb[key];

    // Partial: check if factor name is contained in a KB entry name or vice-versa
    for (const k of Object.keys(_kb)) {
      if (key.includes(k) || k.includes(key)) return _kb[k];
    }
    return null;
  }

  /* ── API ───────────────────────────────────────────────────────── */

  /**
   * Fetch explain-paragraph data from the backend.
   */
  async function fetchExplanation(source, paragraphName) {
    return ApiClient.post('/api/analysis/explain-paragraph', {
      source_text: source,
      paragraph_name: paragraphName,
    });
  }

  /* ── Rendering ─────────────────────────────────────────────────── */

  /**
   * Render the full paragraph detail panel.
   * @param {Object} data - Response from POST /api/analysis/explain-paragraph
   */
  function renderDetail(data) {
    const container = document.getElementById('paragraphDetailContainer');
    if (!container) return;

    const score = data.complexity?.score || 0;
    const factors = data.complexity?.factors || [];
    const ratingClass = score >= 20 ? 'spaghetti' : score >= 10 ? 'moderate' : 'clean';

    let html = '';

    // ── Header: name + score badge + dead/alter tag ──
    html += `<div class="para-detail__header">
      <span class="para-detail__name">${Utils.escapeHtml(data.paragraph)}</span>
      <span class="complexity-score complexity-score--${ratingClass}">${score}</span>`;
    if (data.is_dead) {
      html += '<span class="para-detail__tag para-detail__tag--dead">DEAD</span>';
    } else if (data.is_alter_conditional) {
      html += '<span class="para-detail__tag para-detail__tag--alter">ALTER_CONDITIONAL</span>';
    }
    html += '</div>';

    // ── Complexity Factors ──
    if (factors.length > 0) {
      html += '<div class="para-detail__section">';
      html += '<div class="para-detail__section-title">Complexity Factors</div>';
      html += '<div class="para-detail__factors">';
      factors.forEach(f => {
        const kb = matchKB(f);
        const cls = kb ? 'para-detail__factor para-detail__factor--kb' : 'para-detail__factor';
        const tip = kb ? ` title="Click for KB: ${Utils.escapeHtml(kb.name)}"` : '';
        html += `<span class="${cls}"${tip} data-factor="${Utils.escapeHtml(f)}">${Utils.escapeHtml(f)}</span>`;
      });
      html += '</div></div>';
    }

    // ── Control Flow: calls-to / called-by ──
    html += '<div class="para-detail__section">';
    html += '<div class="para-detail__section-title">Control Flow</div>';
    html += '<div class="para-detail__edges">';

    if (data.calls_to && data.calls_to.length > 0) {
      html += '<div class="para-detail__edge-group">';
      html += '<span class="para-detail__edge-label">Calls &rarr;</span>';
      data.calls_to.forEach(e => {
        html += `<span class="para-detail__edge-target para-detail__edge-type--${e.type}" data-paragraph="${Utils.escapeHtml(e.target)}">${Utils.escapeHtml(e.target)} <small>(${e.type})</small></span>`;
      });
      html += '</div>';
    }

    if (data.called_by && data.called_by.length > 0) {
      html += '<div class="para-detail__edge-group">';
      html += '<span class="para-detail__edge-label">&larr; Called by</span>';
      data.called_by.forEach(e => {
        html += `<span class="para-detail__edge-target para-detail__edge-type--${e.type}" data-paragraph="${Utils.escapeHtml(e.source)}">${Utils.escapeHtml(e.source)} <small>(${e.type})</small></span>`;
      });
      html += '</div>';
    }

    if ((!data.calls_to || data.calls_to.length === 0) &&
        (!data.called_by || data.called_by.length === 0)) {
      html += '<span class="para-detail__empty">No connected edges (isolated paragraph)</span>';
    }
    html += '</div></div>';

    // ── Data Flow: fields read / written ──
    html += '<div class="para-detail__section">';
    html += '<div class="para-detail__section-title">Data Flow</div>';
    html += '<div class="para-detail__fields">';

    if (data.fields_read && data.fields_read.length > 0) {
      html += '<div class="para-detail__field-group">';
      html += '<span class="para-detail__field-label para-detail__field-label--read">Reads</span>';
      data.fields_read.forEach(f => {
        html += `<span class="para-detail__field para-detail__field--read">${Utils.escapeHtml(f)}</span>`;
      });
      html += '</div>';
    }

    if (data.fields_written && data.fields_written.length > 0) {
      html += '<div class="para-detail__field-group">';
      html += '<span class="para-detail__field-label para-detail__field-label--write">Writes</span>';
      data.fields_written.forEach(f => {
        html += `<span class="para-detail__field para-detail__field--write">${Utils.escapeHtml(f)}</span>`;
      });
      html += '</div>';
    }

    if ((!data.fields_read || data.fields_read.length === 0) &&
        (!data.fields_written || data.fields_written.length === 0)) {
      html += '<span class="para-detail__empty">No field accesses detected</span>';
    }
    html += '</div></div>';

    // ── "Fix this pattern" link for high-complexity paragraphs ──
    if (score >= 10) {
      html += `<div class="para-detail__fix">
        <button class="btn btn--xs btn--outline para-detail__fix-btn"
                data-paragraph="${Utils.escapeHtml(data.paragraph)}">
          Ask how to fix this pattern &rarr;
        </button>
      </div>`;
    }

    container.innerHTML = html;
    wireEvents(container, data);
  }

  /**
   * Attach click handlers after rendering.
   */
  function wireEvents(container, data) {
    // Factor click -> KB popover
    container.querySelectorAll('.para-detail__factor--kb').forEach(el => {
      el.addEventListener('click', () => showKBCard(el, container));
    });

    // Edge target click -> navigate to that node
    container.querySelectorAll('.para-detail__edge-target').forEach(el => {
      el.addEventListener('click', () => {
        const para = el.dataset.paragraph;
        if (para) {
          CallGraphView.setSelectedNode(para);
          show(para);
        }
      });
    });

    // Fix button -> Chat tab
    container.querySelectorAll('.para-detail__fix-btn').forEach(el => {
      el.addEventListener('click', () => {
        const para = el.dataset.paragraph;
        const file = document.getElementById('analysisFileSelect')?.value || '';
        if (typeof Chat !== 'undefined') {
          Chat.setContext('analysis', {
            type: 'paragraph', id: para, context: { file },
          });
          Chat.prefillAndFocus(`How would I refactor ${para} in ${file} to reduce its complexity?`);
        }
        if (typeof App !== 'undefined') App.switchView('chat');
      });
    });
  }

  /* ── Knowledge Base popover ────────────────────────────────────── */

  /**
   * Show a KB annotation card near the clicked factor element.
   */
  function showKBCard(factorEl, parentContainer) {
    // Remove any existing KB card first
    document.querySelectorAll('.kb-card').forEach(c => c.remove());

    const factorStr = factorEl.dataset.factor;
    const kb = matchKB(factorStr);
    if (!kb) return;

    const card = document.createElement('div');
    card.className = 'kb-card glass';
    card.innerHTML = `
      <div class="kb-card__header">
        <span class="kb-card__name">${Utils.escapeHtml(kb.name)}</span>
        <span class="kb-card__era">${Utils.escapeHtml(kb.era || '')}</span>
        <button class="kb-card__close">&times;</button>
      </div>
      <div class="kb-card__body">
        <p>${Utils.escapeHtml(kb.purpose)}</p>
        ${kb.mainframe_context ? `<div class="kb-card__row"><strong>Mainframe:</strong> ${Utils.escapeHtml(kb.mainframe_context)}</div>` : ''}
        ${kb.modern_equivalent ? `<div class="kb-card__row"><strong>Modern:</strong> ${Utils.escapeHtml(kb.modern_equivalent)}</div>` : ''}
        ${kb.risk ? `<div class="kb-card__row kb-card__row--risk"><strong>Risk:</strong> ${Utils.escapeHtml(kb.risk)}</div>` : ''}
      </div>`;

    card.querySelector('.kb-card__close').addEventListener('click', () => card.remove());

    // Close on outside click
    const handler = (e) => {
      if (!card.contains(e.target) && !factorEl.contains(e.target)) {
        card.remove();
        document.removeEventListener('click', handler);
      }
    };
    setTimeout(() => document.addEventListener('click', handler), 0);

    parentContainer.appendChild(card);
  }

  /* ── Tab switching ─────────────────────────────────────────────── */

  /**
   * Switch between the Trace and Detail tabs.
   */
  function switchTab(tabName) {
    const traceTab = document.getElementById('tabTrace');
    const detailTab = document.getElementById('tabDetail');
    const traceContent = document.getElementById('execPathContainer');
    const detailContent = document.getElementById('paragraphDetailContainer');
    const animControls = document.getElementById('traceAnimControls');

    if (!traceTab || !detailTab) return;

    if (tabName === 'detail') {
      traceTab.classList.remove('detail-tab--active');
      detailTab.classList.add('detail-tab--active');
      if (traceContent) traceContent.style.display = 'none';
      if (detailContent) detailContent.style.display = '';
      if (animControls) animControls.style.display = 'none';
    } else {
      traceTab.classList.add('detail-tab--active');
      detailTab.classList.remove('detail-tab--active');
      if (traceContent) traceContent.style.display = '';
      if (detailContent) detailContent.style.display = 'none';
      // Re-show anim controls only if traces are loaded
      if (animControls && document.querySelectorAll('.exec-path__group').length > 0) {
        animControls.style.display = '';
      }
    }
  }

  /* ── Public API ────────────────────────────────────────────────── */

  /**
   * Show paragraph detail for a given paragraph name.
   * Fetches source from Analysis, calls explain-paragraph, renders.
   */
  async function show(paragraphName) {
    if (!paragraphName) return;

    switchTab('detail');

    const container = document.getElementById('paragraphDetailContainer');
    if (container) {
      container.innerHTML = '<span class="para-detail__loading">Loading\u2026</span>';
    }

    const fileSelect = document.getElementById('analysisFileSelect');
    const filename = fileSelect?.value;
    if (!filename) return;

    const source = await Analysis.fetchSource(filename);
    if (!source) return;

    try {
      const data = await fetchExplanation(source, paragraphName);
      renderDetail(data);
    } catch (e) {
      if (container) {
        container.innerHTML = `<span class="para-detail__empty">Could not load: ${Utils.escapeHtml(e.message)}</span>`;
      }
    }
  }

  /**
   * Initialize: load KB, wire tab clicks.
   */
  function init() {
    loadKB();
    document.getElementById('tabTrace')?.addEventListener('click', () => switchTab('trace'));
    document.getElementById('tabDetail')?.addEventListener('click', () => switchTab('detail'));
  }

  return { init, show, switchTab };

})();

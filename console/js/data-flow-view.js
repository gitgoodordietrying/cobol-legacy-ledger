/**
 * data-flow-view.js -- Field read/write visualization for COBOL programs.
 *
 * Shows all Working-Storage fields with reader/writer counts, coupling
 * warnings, and per-paragraph access detail.  Calls POST /api/analysis/data-flow
 * with the currently selected file's source text.
 *
 * COBOL CONCEPT: In legacy COBOL, all variables live in Working-Storage
 * and are globally accessible to every paragraph.  Data flow analysis
 * reveals hidden coupling -- when multiple paragraphs write the same
 * field, the order of execution determines the final value.  This is
 * a major source of bugs in spaghetti code, because GO TO chains make
 * that order unpredictable.
 */

const DataFlowView = (() => {

  /**
   * Run data flow analysis on the currently selected file.
   */
  async function analyze() {
    const fileSelect = document.getElementById('analysisFileSelect');
    const filename = fileSelect?.value;
    if (!filename) return;

    Utils.showToast(`Analyzing data flow in ${filename}\u2026`, 'info');

    const source = await Analysis.fetchSource(filename);
    if (!source) return;

    try {
      const data = await ApiClient.post('/api/analysis/data-flow', {
        source_text: source,
      });

      render(data);

      // Show data flow card, hide others
      document.getElementById('analysisGrid').style.display = 'none';
      document.getElementById('compareCard').style.display = 'none';
      document.getElementById('crossFileCard').style.display = 'none';
      document.getElementById('dataFlowCard').style.display = '';

      const fieldCount = Object.keys(data.field_readers || {}).length;
      Utils.showToast(`Data flow: ${fieldCount} fields analyzed`, 'success');
    } catch (e) {
      Utils.showToast(`Data flow failed: ${e.message}`, 'danger');
    }
  }

  /**
   * Render the data flow field list.
   * @param {Object} data - Response from POST /api/analysis/data-flow
   *   { field_readers, field_writers, paragraph_reads, paragraph_writes }
   */
  function render(data) {
    const container = document.getElementById('dataFlowContainer');
    if (!container) return;

    const readers = data.field_readers || {};
    const writers = data.field_writers || {};

    // Merge all field names from both readers and writers
    const allFields = new Set([...Object.keys(readers), ...Object.keys(writers)]);
    if (allFields.size === 0) {
      container.innerHTML = '<span class="df-empty">No field accesses detected.</span>';
      return;
    }

    // Sort by total access count (most-accessed first)
    const sorted = [...allFields].sort((a, b) => {
      const countA = (readers[a]?.length || 0) + (writers[a]?.length || 0);
      const countB = (readers[b]?.length || 0) + (writers[b]?.length || 0);
      return countB - countA;
    });

    // Count coupling warnings (fields with >3 writers)
    const coupledCount = sorted.filter(f => (writers[f]?.length || 0) > 3).length;

    let html = `<div class="df-summary">
      <span class="df-summary__stat">${allFields.size} fields</span>
      <span class="df-summary__stat df-summary__stat--read">${Object.keys(readers).length} read</span>
      <span class="df-summary__stat df-summary__stat--write">${Object.keys(writers).length} written</span>
      ${coupledCount > 0 ? `<span class="df-summary__stat df-summary__stat--warn">${coupledCount} high-coupling</span>` : ''}
    </div>`;

    html += '<div class="df-field-list">';

    sorted.forEach(field => {
      const rList = readers[field] || [];
      const wList = writers[field] || [];
      const coupling = wList.length > 3;

      html += `<div class="df-field${coupling ? ' df-field--coupled' : ''}" data-field="${Utils.escapeHtml(field)}">`;

      // Collapsible header row
      html += '<div class="df-field__header">';
      html += `<span class="df-field__name">${Utils.escapeHtml(field)}</span>`;
      html += '<span class="df-field__counts">';
      html += `<span class="df-field__count df-field__count--read" title="${rList.length} paragraph(s) read this field">${rList.length}R</span>`;
      html += `<span class="df-field__count df-field__count--write" title="${wList.length} paragraph(s) write this field">${wList.length}W</span>`;
      if (coupling) {
        html += '<span class="df-field__coupling" title="High coupling: more than 3 writers increases bug risk">coupled</span>';
      }
      html += '</span></div>';

      // Expandable detail (hidden by default)
      html += '<div class="df-field__detail" style="display: none;">';
      if (rList.length > 0) {
        html += '<div class="df-field__access-group">';
        html += '<span class="df-field__access-label df-field__access-label--read">Read by:</span>';
        rList.forEach(p => {
          html += `<span class="df-field__para" data-paragraph="${Utils.escapeHtml(p)}">${Utils.escapeHtml(p)}</span>`;
        });
        html += '</div>';
      }
      if (wList.length > 0) {
        html += '<div class="df-field__access-group">';
        html += '<span class="df-field__access-label df-field__access-label--write">Written by:</span>';
        wList.forEach(p => {
          html += `<span class="df-field__para" data-paragraph="${Utils.escapeHtml(p)}">${Utils.escapeHtml(p)}</span>`;
        });
        html += '</div>';
      }
      html += '</div></div>';
    });

    html += '</div>';
    container.innerHTML = html;
    wireEvents(container);
  }

  /**
   * Attach interactive event handlers after rendering.
   */
  function wireEvents(container) {
    // Click field header -> expand/collapse detail
    container.querySelectorAll('.df-field__header').forEach(header => {
      header.style.cursor = 'pointer';
      header.addEventListener('click', () => {
        const detail = header.nextElementSibling;
        if (!detail) return;
        const isOpen = detail.style.display !== 'none';
        detail.style.display = isOpen ? 'none' : '';
        header.closest('.df-field')?.classList.toggle('df-field--expanded', !isOpen);
      });
    });

    // Click paragraph name -> select that node in call graph
    container.querySelectorAll('.df-field__para').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const para = el.dataset.paragraph;
        if (para) {
          CallGraphView.setSelectedNode(para);
          // Switch back to analysis grid to see the graph
          document.getElementById('dataFlowCard').style.display = 'none';
          document.getElementById('analysisGrid').style.display = '';
        }
      });
    });
  }

  /**
   * Initialize: wire Data Flow button and close button.
   */
  function init() {
    document.getElementById('btnDataFlow')?.addEventListener('click', analyze);
    document.getElementById('btnCloseDataFlow')?.addEventListener('click', () => {
      document.getElementById('dataFlowCard').style.display = 'none';
      document.getElementById('analysisGrid').style.display = '';
    });
  }

  return { init, analyze };

})();

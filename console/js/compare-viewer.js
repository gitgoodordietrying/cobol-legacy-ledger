/**
 * compare-viewer.js -- Split-pane comparison of spaghetti vs clean COBOL.
 *
 * Shows two COBOL programs side by side with complexity heatmap backgrounds.
 * Lines in high-complexity paragraphs get colored backgrounds; dead code
 * is dimmed. Summary stats (total score, rating, dead count) at top of each pane.
 *
 * Default comparison: PAYROLL.cob (spaghetti, 1974) vs TRANSACT.cob (clean, modern).
 */

const CompareViewer = (() => {

  let containerEl = null;

  /**
   * Initialize the compare viewer.
   * @param {string} containerId - ID of the container element
   */
  function init(containerId) {
    containerEl = document.getElementById(containerId);
  }

  /**
   * Render a side-by-side comparison.
   * @param {Object} compareData - Response from POST /api/analysis/compare
   * @param {string} sourceA - Raw COBOL source text for left pane
   * @param {string} sourceB - Raw COBOL source text for right pane
   */
  function render(compareData, sourceA, sourceB) {
    if (!containerEl) return;
    containerEl.innerHTML = '';

    const wrapper = document.createElement('div');
    wrapper.className = 'compare-viewer';

    wrapper.appendChild(renderPane(
      compareData.a, sourceA, 'compare-pane--left'
    ));
    wrapper.appendChild(renderPane(
      compareData.b, sourceB, 'compare-pane--right'
    ));

    containerEl.appendChild(wrapper);
  }

  /**
   * Render a single pane (left or right).
   */
  function renderPane(data, source, cssClass) {
    const pane = document.createElement('div');
    pane.className = `compare-pane ${cssClass}`;

    // Header with label and stats
    const header = document.createElement('div');
    header.className = 'compare-pane__header';

    const label = document.createElement('span');
    label.textContent = data.label;

    const stats = document.createElement('span');
    stats.className = 'compare-pane__stats';
    const cx = data.complexity;
    const dc = data.dead_code;
    const ratingClass = cx.rating === 'clean' ? 'clean'
      : cx.rating === 'moderate' ? 'moderate' : 'spaghetti';
    stats.innerHTML = `
      <span class="analysis-stat__value--${ratingClass}">${cx.total_score}</span> score
      &middot; ${cx.rating}
      &middot; ${dc.dead_count} dead
    `;

    header.appendChild(label);
    header.appendChild(stats);
    pane.appendChild(header);

    // Source with complexity heatmap
    const sourceDiv = document.createElement('div');
    sourceDiv.className = 'compare-pane__source';

    const lines = source.split('\n');
    const paraScores = cx.paragraphs || {};

    // Build paragraph line ranges from complexity data
    let currentPara = null;
    const lineParaMap = {};
    const PARA_RE = /^\s{7}([\w-]+)\.\s*$/;

    lines.forEach((line, i) => {
      const m = line.match(PARA_RE);
      if (m) currentPara = m[1].trim();
      if (currentPara) lineParaMap[i] = currentPara;
    });

    const deadSet = new Set(dc.dead || []);

    lines.forEach((line, i) => {
      const span = document.createElement('span');
      const para = lineParaMap[i];
      const score = para && paraScores[para] ? paraScores[para].score : 0;

      let cssLine = 'complexity-line';
      if (para && deadSet.has(para)) {
        cssLine += ' complexity-line--dead';
      } else if (score >= 20) {
        cssLine += ' complexity-line--high';
      } else if (score >= 10) {
        cssLine += ' complexity-line--medium';
      } else if (score > 0) {
        cssLine += ' complexity-line--low';
      } else {
        cssLine += ' complexity-line--clean';
      }

      span.className = cssLine;
      span.textContent = line || ' ';

      // Add score badge on paragraph header lines
      const m = line.match(PARA_RE);
      if (m && score > 0) {
        const badge = document.createElement('span');
        const badgeClass = score >= 20 ? 'spaghetti' : score >= 10 ? 'moderate' : 'clean';
        badge.className = `complexity-score complexity-score--${badgeClass}`;
        badge.textContent = score;
        span.textContent = line;
        span.appendChild(badge);
      }

      sourceDiv.appendChild(span);
    });

    pane.appendChild(sourceDiv);
    return pane;
  }

  return { init, render };

})();

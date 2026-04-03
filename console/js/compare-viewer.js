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

    const cx = data.complexity;
    const dc = data.dead_code;
    const paraScores = cx.paragraphs || {};
    const deadSet = new Set(dc.dead || []);
    const alterCondSet = new Set(dc.alter_conditional || []);

    // Header with label and stats
    const header = document.createElement('div');
    header.className = 'compare-pane__header';

    const label = document.createElement('span');
    label.textContent = data.label;

    const stats = document.createElement('span');
    stats.className = 'compare-pane__stats';
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

    // Anti-pattern summary bar -- tally factor counts across all paragraphs
    const antiPatterns = {};
    Object.values(paraScores).forEach(p => {
      (p.factors || []).forEach(f => {
        const match = f.match(/^(.+?)\s+x(\d+)/);
        if (match) {
          antiPatterns[match[1]] = (antiPatterns[match[1]] || 0) + parseInt(match[2]);
        }
      });
    });
    const apEntries = Object.entries(antiPatterns).sort((a, b) => b[1] - a[1]);
    if (apEntries.length > 0) {
      const bar = document.createElement('div');
      bar.className = 'compare-pane__anti-patterns';
      bar.innerHTML = apEntries
        .map(([name, count]) => `<span class="compare-ap__item">${Utils.escapeHtml(name)}: ${count}</span>`)
        .join('');
      pane.appendChild(bar);
    }

    // Source with complexity heatmap
    const sourceDiv = document.createElement('div');
    sourceDiv.className = 'compare-pane__source';

    const lines = source.split('\n');

    // Build paragraph line ranges from complexity data
    let currentPara = null;
    const lineParaMap = {};
    const PARA_RE = /^\s{7}([\w-]+)\.\s*$/;

    lines.forEach((line, i) => {
      const m = line.match(PARA_RE);
      if (m) currentPara = m[1].trim();
      if (currentPara) lineParaMap[i] = currentPara;
    });

    lines.forEach((line, i) => {
      const span = document.createElement('span');
      const para = lineParaMap[i];
      const score = para && paraScores[para] ? paraScores[para].score : 0;

      let cssLine = 'complexity-line';
      if (para && deadSet.has(para)) {
        cssLine += ' complexity-line--dead';
      } else if (para && alterCondSet.has(para)) {
        cssLine += ' complexity-line--alter-cond';
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

      // Paragraph header line: score badge + dead/alter label + factor popover
      const m = line.match(PARA_RE);
      if (m) {
        const paraName = m[1].trim();

        // Dead code / ALTER_CONDITIONAL label
        if (deadSet.has(paraName)) {
          const tag = document.createElement('span');
          tag.className = 'complexity-dead-label';
          tag.textContent = 'DEAD';
          span.appendChild(tag);
        } else if (alterCondSet.has(paraName)) {
          const tag = document.createElement('span');
          tag.className = 'complexity-dead-label complexity-dead-label--alter';
          tag.textContent = 'ALTER_CONDITIONAL';
          span.appendChild(tag);
        }

        // Score badge with click-to-expand factors
        if (score > 0) {
          const badge = document.createElement('span');
          const badgeClass = score >= 20 ? 'spaghetti' : score >= 10 ? 'moderate' : 'clean';
          badge.className = `complexity-score complexity-score--${badgeClass}`;
          badge.textContent = score;
          badge.style.cursor = 'pointer';
          badge.title = 'Click for factor breakdown';
          badge.addEventListener('click', (e) => {
            e.stopPropagation();
            showFactorPopover(badge, paraScores[paraName]);
          });
          span.appendChild(badge);
        }
      }

      sourceDiv.appendChild(span);
    });

    pane.appendChild(sourceDiv);
    return pane;
  }

  /**
   * Show a factor breakdown popover near a score badge.
   */
  function showFactorPopover(badge, paraData) {
    // Remove any existing popover
    document.querySelectorAll('.factor-popover').forEach(p => p.remove());
    if (!paraData || !paraData.factors || paraData.factors.length === 0) return;

    const pop = document.createElement('div');
    pop.className = 'factor-popover glass';
    pop.innerHTML = '<div class="factor-popover__title">Factors</div>'
      + paraData.factors.map(f => `<div class="factor-popover__item">${Utils.escapeHtml(f)}</div>`).join('');

    badge.parentElement.style.position = 'relative';
    badge.parentElement.appendChild(pop);

    // Close on outside click
    const handler = (e) => {
      if (!pop.contains(e.target) && e.target !== badge) {
        pop.remove();
        document.removeEventListener('click', handler);
      }
    };
    setTimeout(() => document.addEventListener('click', handler), 0);
  }

  return { init, render };

})();

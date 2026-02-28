/**
 * call-graph.js -- SVG directed graph visualization of COBOL paragraph dependencies.
 *
 * Renders paragraphs as nodes and control flow (PERFORM, GO TO, ALTER, PERFORM THRU,
 * fall-through) as colored/styled edges. Nodes are colored by complexity score.
 * Follows the same IIFE module pattern as network-graph.js.
 */

const CallGraphView = (() => {

  const SVG_NS = 'http://www.w3.org/2000/svg';

  // Node sizing
  const NODE_W = 130;
  const NODE_H = 36;
  const H_GAP = 40;
  const V_GAP = 60;
  const COLS = 4;
  const PAD = 30;

  // Edge type colors (matches analysis.css)
  const EDGE_COLORS = {
    PERFORM: '#22c55e',
    GOTO: '#ef4444',
    ALTER: '#f59e0b',
    PERFORM_THRU: '#3b82f6',
    FALL_THROUGH: '#64748b',
  };

  // Complexity rating colors
  const RATING_COLORS = {
    clean: '#22c55e',
    moderate: '#f59e0b',
    spaghetti: '#ef4444',
  };

  let container = null;

  /**
   * Create an SVG element with attributes.
   */
  function svgEl(tag, attrs = {}) {
    const el = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    return el;
  }

  /**
   * Initialize the call graph view.
   * @param {string} containerId - ID of the container element
   */
  function init(containerId) {
    container = document.getElementById(containerId);
  }

  /**
   * Render a call graph from analysis API response data.
   * @param {Object} graphData - Response from POST /api/analysis/call-graph
   * @param {Object} complexityData - Response from POST /api/analysis/complexity (optional)
   * @param {Object} deadCodeData - Response from POST /api/analysis/dead-code (optional)
   */
  function render(graphData, complexityData, deadCodeData) {
    if (!container) return;
    container.innerHTML = '';

    const paragraphs = graphData.paragraphs || [];
    const edges = graphData.edges || [];
    const deadSet = new Set(deadCodeData?.dead || []);
    const alterCondSet = new Set(deadCodeData?.alter_conditional || []);
    const complexityMap = complexityData?.paragraphs || {};

    if (paragraphs.length === 0) {
      container.innerHTML = '<span style="color: var(--text-muted); padding: 16px;">No paragraphs found</span>';
      return;
    }

    // Compute node positions (grid layout)
    const positions = {};
    paragraphs.forEach((name, i) => {
      const col = i % COLS;
      const row = Math.floor(i / COLS);
      positions[name] = {
        x: PAD + col * (NODE_W + H_GAP) + NODE_W / 2,
        y: PAD + row * (NODE_H + V_GAP) + NODE_H / 2,
      };
    });

    const totalW = PAD * 2 + Math.min(paragraphs.length, COLS) * (NODE_W + H_GAP);
    const totalH = PAD * 2 + (Math.ceil(paragraphs.length / COLS)) * (NODE_H + V_GAP);

    const svg = svgEl('svg', {
      viewBox: `0 0 ${totalW} ${totalH}`,
      preserveAspectRatio: 'xMidYMid meet',
      style: `width: 100%; height: ${Math.max(totalH, 300)}px;`,
    });

    // Arrowhead markers
    const defs = svgEl('defs');
    Object.entries(EDGE_COLORS).forEach(([type, color]) => {
      const marker = svgEl('marker', {
        id: `arrow-${type}`, viewBox: '0 0 10 10',
        refX: '10', refY: '5', markerWidth: '6', markerHeight: '6',
        orient: 'auto-start-reverse',
      });
      const path = svgEl('path', { d: 'M 0 0 L 10 5 L 0 10 z', fill: color });
      marker.appendChild(path);
      defs.appendChild(marker);
    });
    svg.appendChild(defs);

    // Draw edges
    edges.forEach(edge => {
      const src = positions[edge.source];
      const tgt = positions[edge.target];
      if (!src || !tgt) return;

      const color = EDGE_COLORS[edge.type] || '#64748b';
      const dasharray = edge.type === 'GOTO' ? '6 3'
        : edge.type === 'ALTER' ? '3 3'
        : edge.type === 'PERFORM_THRU' ? '8 4'
        : edge.type === 'FALL_THROUGH' ? '2 4'
        : 'none';

      // Simple curved path
      const dx = tgt.x - src.x;
      const dy = tgt.y - src.y;
      const mx = (src.x + tgt.x) / 2;
      const my = (src.y + tgt.y) / 2;
      const offset = Math.abs(dx) < 10 ? 30 : 0;

      const line = svgEl('path', {
        d: `M ${src.x} ${src.y + NODE_H / 2} Q ${mx + offset} ${my} ${tgt.x} ${tgt.y - NODE_H / 2}`,
        stroke: color,
        'stroke-width': edge.type === 'ALTER' ? '2' : '1.5',
        'stroke-dasharray': dasharray,
        fill: 'none',
        'marker-end': `url(#arrow-${edge.type})`,
        class: `cg-edge cg-edge--${edge.type}`,
      });

      // Tooltip
      const title = svgEl('title');
      title.textContent = `${edge.source} → ${edge.target} (${edge.type})`;
      line.appendChild(title);
      svg.appendChild(line);
    });

    // Draw nodes
    paragraphs.forEach(name => {
      const pos = positions[name];
      const g = svgEl('g', { class: 'cg-node', transform: `translate(${pos.x}, ${pos.y})` });

      // Determine node color
      let fillColor = 'rgba(20, 27, 55, 0.8)';
      let strokeColor = 'rgba(255, 255, 255, 0.15)';
      const score = complexityMap[name]?.score || 0;

      if (deadSet.has(name)) {
        fillColor = 'rgba(100, 116, 139, 0.3)';
        strokeColor = '#64748b';
      } else if (alterCondSet.has(name)) {
        fillColor = 'rgba(245, 158, 11, 0.2)';
        strokeColor = '#f59e0b';
      } else if (score >= 20) {
        fillColor = 'rgba(239, 68, 68, 0.2)';
        strokeColor = '#ef4444';
      } else if (score >= 10) {
        fillColor = 'rgba(245, 158, 11, 0.15)';
        strokeColor = '#f59e0b';
      } else if (score > 0) {
        fillColor = 'rgba(34, 197, 94, 0.1)';
        strokeColor = '#22c55e';
      }

      const rect = svgEl('rect', {
        x: -NODE_W / 2, y: -NODE_H / 2,
        width: NODE_W, height: NODE_H,
        fill: fillColor, stroke: strokeColor,
        class: 'cg-node__rect',
      });
      g.appendChild(rect);

      // Label (truncate long names)
      const displayName = name.length > 16 ? name.slice(0, 14) + '..' : name;
      const label = svgEl('text', {
        y: score > 0 ? '-3' : '0',
        class: 'cg-node__label',
      });
      label.textContent = displayName;
      g.appendChild(label);

      // Score subtitle
      if (score > 0) {
        const scoreTxt = svgEl('text', { y: '10', class: 'cg-node__score' });
        scoreTxt.textContent = `score: ${score}`;
        g.appendChild(scoreTxt);
      }

      // Dead code indicator
      if (deadSet.has(name)) {
        const deadTxt = svgEl('text', { y: '10', class: 'cg-node__score' });
        deadTxt.textContent = 'DEAD';
        deadTxt.setAttribute('fill', '#ef4444');
        g.appendChild(deadTxt);
      }

      // Tooltip
      const title = svgEl('title');
      title.textContent = `${name} — score: ${score}${deadSet.has(name) ? ' (DEAD)' : ''}`;
      g.appendChild(title);

      svg.appendChild(g);
    });

    container.appendChild(svg);
  }

  /**
   * Build the legend showing edge type colors.
   * @param {string} legendId - ID of the legend container
   */
  function renderLegend(legendId) {
    const legend = document.getElementById(legendId);
    if (!legend) return;

    legend.innerHTML = '';
    const types = [
      ['PERFORM', '#22c55e', 'solid'],
      ['GO TO', '#ef4444', 'dashed'],
      ['ALTER', '#f59e0b', 'dotted'],
      ['THRU', '#3b82f6', 'dashed'],
      ['Fall-through', '#64748b', 'dotted'],
    ];

    types.forEach(([label, color, style]) => {
      const item = document.createElement('span');
      item.className = 'cg-legend__item';
      item.innerHTML = `<span class="cg-legend__line" style="background:${color};border-top:2px ${style} ${color};background:none;"></span>${label}`;
      legend.appendChild(item);
    });
  }

  return { init, render, renderLegend };

})();

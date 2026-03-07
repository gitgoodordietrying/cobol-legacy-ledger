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
  let _selectedNode = null;

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

    // Draw edges with improved routing to avoid node overlap
    // Track edge indices between same source-target pairs for spreading
    const edgeIndexMap = {};
    edges.forEach((edge, edgeIdx) => {
      const src = positions[edge.source];
      const tgt = positions[edge.target];
      if (!src || !tgt) return;

      const color = EDGE_COLORS[edge.type] || '#64748b';
      const dasharray = edge.type === 'GOTO' ? '6 3'
        : edge.type === 'ALTER' ? '3 3'
        : edge.type === 'PERFORM_THRU' ? '8 4'
        : edge.type === 'FALL_THROUGH' ? '2 4'
        : 'none';

      // Track edge index for spreading overlapping edges
      const pairKey = `${edge.source}-${edge.target}`;
      const reversePairKey = `${edge.target}-${edge.source}`;
      if (!edgeIndexMap[pairKey]) edgeIndexMap[pairKey] = 0;
      const spreadIdx = edgeIndexMap[pairKey]++;
      const spreadOffset = spreadIdx * 15;

      // Improved routing
      const dx = tgt.x - src.x;
      const dy = tgt.y - src.y;
      const absDx = Math.abs(dx);
      const absDy = Math.abs(dy);
      const rowJumps = Math.round(absDy / (NODE_H + V_GAP));

      let d;
      const sy = src.y + NODE_H / 2;
      const ty = tgt.y - NODE_H / 2;

      if (absDx < 10 && absDy < NODE_H + V_GAP + 10) {
        // Same column, adjacent row: gentle side curve
        const side = (edgeIdx % 2 === 0 ? 1 : -1);
        const cx = src.x + (35 + spreadOffset) * side;
        d = `M ${src.x} ${sy} Q ${cx} ${(sy + ty) / 2} ${tgt.x} ${ty}`;
      } else if (absDx < 10) {
        // Same column, multi-row jump: larger side offset to avoid intermediate nodes
        const side = (edgeIdx % 2 === 0 ? 1 : -1);
        const cx = src.x + (50 + rowJumps * 20 + spreadOffset) * side;
        d = `M ${src.x} ${sy} Q ${cx} ${(sy + ty) / 2} ${tgt.x} ${ty}`;
      } else if (rowJumps > 1) {
        // Multi-row jump with horizontal distance: cubic bezier curving around nodes
        const mx = (src.x + tgt.x) / 2;
        const sideSign = dx > 0 ? 1 : -1;
        const curveOffset = (25 + rowJumps * 15 + spreadOffset) * sideSign;
        const c1x = src.x + curveOffset;
        const c1y = sy + (ty - sy) * 0.25;
        const c2x = tgt.x - curveOffset * 0.5;
        const c2y = sy + (ty - sy) * 0.75;
        d = `M ${src.x} ${sy} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${tgt.x} ${ty}`;
      } else {
        // Adjacent or nearby: simple quadratic curve
        const mx = (src.x + tgt.x) / 2;
        const my = (sy + ty) / 2;
        const offset = spreadOffset * (edgeIdx % 2 === 0 ? 1 : -1);
        d = `M ${src.x} ${sy} Q ${mx + offset} ${my} ${tgt.x} ${ty}`;
      }

      const line = svgEl('path', {
        d,
        stroke: color,
        'stroke-width': edge.type === 'ALTER' ? '1.8' : '1.2',
        'stroke-dasharray': dasharray,
        fill: 'none',
        'marker-end': `url(#arrow-${edge.type})`,
        class: `cg-edge cg-edge--${edge.type}`,
      });

      // Tooltip
      const title = svgEl('title');
      title.textContent = `${edge.source} \u2192 ${edge.target} (${edge.type})`;
      line.appendChild(title);
      svg.appendChild(line);
    });

    // Draw nodes
    paragraphs.forEach(name => {
      const pos = positions[name];
      const g = svgEl('g', { class: 'cg-node', 'data-paragraph': name, transform: `translate(${pos.x}, ${pos.y})` });

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
      title.textContent = `${name} \u2014 score: ${score}${deadSet.has(name) ? ' (DEAD)' : ''}`;
      g.appendChild(title);

      // Click handler: dispatch custom event for trace interaction
      g.addEventListener('click', () => {
        setSelectedNode(name);
        g.dispatchEvent(new CustomEvent('cg-node-click', {
          detail: { paragraph: name },
          bubbles: true,
        }));
      });

      // Highlight if previously selected
      if (_selectedNode === name) {
        g.classList.add('cg-node--selected');
      }

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

  /**
   * Highlight a node as selected (brighter border).
   * @param {string} name - paragraph name to select
   */
  function setSelectedNode(name) {
    _selectedNode = name;
    if (!container) return;
    container.querySelectorAll('.cg-node').forEach(g => {
      g.classList.toggle('cg-node--selected', g.getAttribute('data-paragraph') === name);
    });
  }

  /**
   * Render a cross-file dependency graph showing files as nodes with edges.
   * @param {Object} data - Response from POST /api/analysis/cross-file
   */
  function renderCrossFile(data) {
    const cfContainer = document.getElementById('crossFileGraphContainer');
    if (!cfContainer) return;
    cfContainer.innerHTML = '';

    const files = Object.keys(data.files || {});
    if (files.length === 0) return;

    const CF_NODE_W = 140;
    const CF_NODE_H = 44;
    const CF_H_GAP = 50;
    const CF_V_GAP = 70;
    const CF_COLS = 4;
    const CF_PAD = 40;

    const positions = {};
    files.forEach((f, i) => {
      const col = i % CF_COLS;
      const row = Math.floor(i / CF_COLS);
      positions[f] = {
        x: CF_PAD + col * (CF_NODE_W + CF_H_GAP) + CF_NODE_W / 2,
        y: CF_PAD + row * (CF_NODE_H + CF_V_GAP) + CF_NODE_H / 2,
      };
    });

    const totalW = CF_PAD * 2 + Math.min(files.length, CF_COLS) * (CF_NODE_W + CF_H_GAP);
    const totalH = CF_PAD * 2 + Math.ceil(files.length / CF_COLS) * (CF_NODE_H + CF_V_GAP);

    const svg = svgEl('svg', {
      viewBox: `0 0 ${totalW} ${totalH}`,
      preserveAspectRatio: 'xMidYMid meet',
      style: `width: 100%; height: ${Math.max(totalH, 250)}px;`,
    });

    // Edge colors for cross-file types
    const CF_EDGE_COLORS = {
      CALL_EXTERNAL: '#22c55e',
      COPY_DEPENDENCY: '#3b82f6',
      SHARED_COPYBOOK: '#f59e0b',
    };

    // Arrowhead markers
    const defs = svgEl('defs');
    Object.entries(CF_EDGE_COLORS).forEach(([type, color]) => {
      const marker = svgEl('marker', {
        id: `cf-arrow-${type}`, viewBox: '0 0 10 10',
        refX: '10', refY: '5', markerWidth: '6', markerHeight: '6',
        orient: 'auto-start-reverse',
      });
      marker.appendChild(svgEl('path', { d: 'M 0 0 L 10 5 L 0 10 z', fill: color }));
      defs.appendChild(marker);
    });
    svg.appendChild(defs);

    // Draw cross-edges
    (data.cross_edges || []).forEach(edge => {
      const src = positions[edge.source_file];
      const tgt = positions[edge.target_file];
      if (!src || !tgt) return;

      const edgeType = edge.edge_type || edge.type || 'UNKNOWN';
      const color = CF_EDGE_COLORS[edgeType] || '#64748b';
      const mx = (src.x + tgt.x) / 2;
      const my = (src.y + tgt.y) / 2;
      const dx = tgt.x - src.x;
      const offset = Math.abs(dx) < 10 ? 35 : 0;

      const line = svgEl('path', {
        d: `M ${src.x} ${src.y + CF_NODE_H / 2} Q ${mx + offset} ${my} ${tgt.x} ${tgt.y - CF_NODE_H / 2}`,
        stroke: color, 'stroke-width': '1.5', fill: 'none',
        'marker-end': `url(#cf-arrow-${edgeType})`,
        class: `cg-edge cg-edge--${edgeType}`,
      });
      const title = svgEl('title');
      title.textContent = `${edge.source_file} \u2192 ${edge.target_file} (${edgeType}: ${edge.source || ''})`;
      line.appendChild(title);
      svg.appendChild(line);
    });

    // Draw file nodes
    files.forEach(f => {
      const pos = positions[f];
      const fileData = data.files[f] || {};
      const score = fileData.complexity_score || 0;
      const g = svgEl('g', { class: 'cg-node', transform: `translate(${pos.x}, ${pos.y})` });

      let fillColor = 'rgba(20, 27, 55, 0.8)';
      let strokeColor = 'rgba(255, 255, 255, 0.15)';
      if (score >= 100) {
        fillColor = 'rgba(239, 68, 68, 0.2)';
        strokeColor = '#ef4444';
      } else if (score >= 50) {
        fillColor = 'rgba(245, 158, 11, 0.15)';
        strokeColor = '#f59e0b';
      } else if (score > 0) {
        fillColor = 'rgba(34, 197, 94, 0.1)';
        strokeColor = '#22c55e';
      }

      g.appendChild(svgEl('rect', {
        x: -CF_NODE_W / 2, y: -CF_NODE_H / 2,
        width: CF_NODE_W, height: CF_NODE_H,
        fill: fillColor, stroke: strokeColor, rx: 6, ry: 6, 'stroke-width': 1.5,
      }));

      const label = svgEl('text', { y: '-3', class: 'cg-node__label' });
      label.textContent = f.replace('.cob', '');
      g.appendChild(label);

      const scoreTxt = svgEl('text', { y: '12', class: 'cg-node__score' });
      scoreTxt.textContent = `${(fileData.paragraphs || []).length}p / score ${score}`;
      g.appendChild(scoreTxt);

      svg.appendChild(g);
    });

    cfContainer.appendChild(svg);
  }

  return { init, render, renderLegend, setSelectedNode, renderCrossFile };

})();

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
  const H_GAP = 55;
  const V_GAP = 90;
  const PAD = 30;

  // Orthogonal routing constants
  const LANE_W = 6;        // width of each routing lane
  const CORNER_R = 4;      // rounded corner radius

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
   * Build an SVG path string with rounded corners at each waypoint.
   * pts is an array of {x, y} objects. Used by both render() and renderCrossFile().
   */
  function buildOrthogonalPath(pts) {
    if (pts.length < 2) return '';
    const r = CORNER_R;
    let d = `M ${pts[0].x} ${pts[0].y}`;

    for (let i = 1; i < pts.length - 1; i++) {
      const prev = pts[i - 1];
      const cur = pts[i];
      const next = pts[i + 1];

      const dxIn = Math.sign(cur.x - prev.x);
      const dyIn = Math.sign(cur.y - prev.y);
      const dxOut = Math.sign(next.x - cur.x);
      const dyOut = Math.sign(next.y - cur.y);

      const lenIn = Math.abs(cur.x - prev.x) + Math.abs(cur.y - prev.y);
      const lenOut = Math.abs(next.x - cur.x) + Math.abs(next.y - cur.y);
      const cr = Math.min(r, lenIn / 2, lenOut / 2);

      if (cr < 1) {
        d += ` L ${cur.x} ${cur.y}`;
        continue;
      }

      const ax = cur.x - dxIn * cr;
      const ay = cur.y - dyIn * cr;
      const bx = cur.x + dxOut * cr;
      const by = cur.y + dyOut * cr;

      const cross = dxIn * dyOut - dyIn * dxOut;
      const sweep = cross > 0 ? 1 : 0;

      d += ` L ${ax} ${ay} A ${cr} ${cr} 0 0 ${sweep} ${bx} ${by}`;
    }

    const last = pts[pts.length - 1];
    d += ` L ${last.x} ${last.y}`;
    return d;
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

    // Adaptive column count based on paragraph count
    const cols = paragraphs.length <= 8 ? 3 : paragraphs.length <= 16 ? 4 : 5;

    // Compute node positions (grid layout)
    const positions = {};
    paragraphs.forEach((name, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      positions[name] = {
        x: PAD + col * (NODE_W + H_GAP) + NODE_W / 2,
        y: PAD + row * (NODE_H + V_GAP) + NODE_H / 2,
      };
    });

    const totalW = PAD * 2 + Math.min(paragraphs.length, cols) * (NODE_W + H_GAP);
    const totalH = PAD * 2 + (Math.ceil(paragraphs.length / cols)) * (NODE_H + V_GAP);

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
        refX: '6', refY: '5', markerWidth: '6', markerHeight: '6',
        orient: 'auto-start-reverse',
      });
      const path = svgEl('path', { d: 'M 0 0 L 10 5 L 0 10 z', fill: color });
      marker.appendChild(path);
      defs.appendChild(marker);
    });
    svg.appendChild(defs);

    // ── Orthogonal (Manhattan) edge routing ──────────────────────
    // Edges travel in horizontal/vertical segments only, using the
    // gaps between rows as routing channels (like circuit traces).

    // Compute row/col for each paragraph
    const nodeGrid = {};
    paragraphs.forEach((name, i) => {
      nodeGrid[name] = { col: i % cols, row: Math.floor(i / cols) };
    });
    const maxRow = Math.ceil(paragraphs.length / cols) - 1;

    // Group edges by channel (the gap between rows they route through)
    // and assign each edge a unique lane so parallel edges don't overlap.
    const channelLanes = {};  // channelKey → next lane index
    function assignLane(key) {
      if (channelLanes[key] == null) channelLanes[key] = 0;
      return channelLanes[key]++;
    }

    edges.forEach((edge) => {
      const src = positions[edge.source];
      const tgt = positions[edge.target];
      if (!src || !tgt) return;

      const color = EDGE_COLORS[edge.type] || '#64748b';
      const dasharray = edge.type === 'GOTO' ? '6 3'
        : edge.type === 'ALTER' ? '3 3'
        : edge.type === 'PERFORM_THRU' ? '8 4'
        : edge.type === 'FALL_THROUGH' ? '2 4'
        : 'none';

      const srcGrid = nodeGrid[edge.source];
      const tgtGrid = nodeGrid[edge.target];
      const arrowGap = 8;
      const sy = src.y + NODE_H / 2;       // exit bottom of source
      const ty = tgt.y - NODE_H / 2 - arrowGap;  // enter top of target

      let pts;

      if (edge.source === edge.target) {
        // ── Self-loop: small loop off the right side ──
        const loopR = 14;
        const rx = src.x + NODE_W / 2 + 6;
        const d = `M ${src.x + NODE_W / 2} ${src.y - 6}`
          + ` C ${rx + loopR} ${src.y - 6}, ${rx + loopR} ${src.y + 6}, ${src.x + NODE_W / 2} ${src.y + 6}`;

        const line = svgEl('path', {
          d,
          stroke: color,
          'stroke-width': edges.length > 20 ? '0.8' : '1.2',
          'stroke-dasharray': dasharray,
          fill: 'none',
          'marker-end': `url(#arrow-${edge.type})`,
          class: `cg-edge cg-edge--${edge.type}`,
        });
        const title = svgEl('title');
        title.textContent = `${edge.source} \u2192 ${edge.target} (${edge.type})`;
        line.appendChild(title);
        svg.appendChild(line);
        return;

      } else if (srcGrid.row < tgtGrid.row) {
        // ── Forward edge (source above target) ──
        // Route: exit bottom → drop into channel below source row →
        //        travel horizontally → drop to target top
        const channelKey = `fwd-${srcGrid.row}`;
        const lane = assignLane(channelKey);
        // Channel Y sits in the gap between rows
        const channelBase = src.y + NODE_H / 2 + 10;
        const channelY = channelBase + lane * LANE_W;

        if (srcGrid.col === tgtGrid.col) {
          // Same column — just go straight down (with a tiny jog if needed for lane offset)
          if (lane === 0) {
            pts = [
              { x: src.x, y: sy },
              { x: tgt.x, y: ty },
            ];
          } else {
            const jog = lane * LANE_W * (lane % 2 === 0 ? 1 : -1);
            pts = [
              { x: src.x, y: sy },
              { x: src.x, y: channelY },
              { x: src.x + jog, y: channelY },
              { x: src.x + jog, y: ty - 10 },
              { x: tgt.x, y: ty },
            ];
          }
        } else {
          // Different column — Z-shaped route through channel
          pts = [
            { x: src.x, y: sy },
            { x: src.x, y: channelY },
            { x: tgt.x, y: channelY },
            { x: tgt.x, y: ty },
          ];
        }

      } else if (srcGrid.row > tgtGrid.row) {
        // ── Backward edge (target above source) ──
        // Route around the periphery of the graph
        const channelKey = `back-${srcGrid.row}-${tgtGrid.row}`;
        const lane = assignLane(channelKey);
        const isLeft = src.x <= totalW / 2;
        const sideX = isLeft
          ? PAD / 2 - 10 - lane * LANE_W
          : totalW - PAD / 2 + 10 + lane * LANE_W;

        const srcChannelY = src.y + NODE_H / 2 + 10 + lane * LANE_W;
        const tgtChannelY = tgt.y - NODE_H / 2 - arrowGap - 10 - lane * LANE_W;

        pts = [
          { x: src.x, y: sy },
          { x: src.x, y: srcChannelY },
          { x: sideX, y: srcChannelY },
          { x: sideX, y: tgtChannelY },
          { x: tgt.x, y: tgtChannelY },
          { x: tgt.x, y: ty },
        ];

      } else {
        // ── Same row ──
        // Route via channel below the row
        const channelKey = `same-${srcGrid.row}`;
        const lane = assignLane(channelKey);
        const channelY = src.y + NODE_H / 2 + 10 + lane * LANE_W;

        pts = [
          { x: src.x, y: sy },
          { x: src.x, y: channelY },
          { x: tgt.x, y: channelY },
          { x: tgt.x, y: ty },
        ];
      }

      const d = buildOrthogonalPath(pts);
      const strokeW = edges.length > 20 ? '0.8' : '1.2';

      const line = svgEl('path', {
        d,
        stroke: color,
        'stroke-width': edge.type === 'ALTER' ? '1.8' : strokeW,
        'stroke-dasharray': dasharray,
        fill: 'none',
        'marker-end': `url(#arrow-${edge.type})`,
        class: `cg-edge cg-edge--${edge.type}`,
      });

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

  // Track which edge types are currently hidden
  const _hiddenTypes = new Set();

  /**
   * Build the legend as toggle buttons that show/hide edge types.
   * @param {string} legendId - ID of the legend container
   */
  function renderLegend(legendId) {
    const legend = document.getElementById(legendId);
    if (!legend) return;

    legend.innerHTML = '';
    const types = [
      ['PERFORM', 'PERFORM', '#22c55e', 'solid'],
      ['GO TO', 'GOTO', '#ef4444', 'dashed'],
      ['ALTER', 'ALTER', '#f59e0b', 'dotted'],
      ['THRU', 'PERFORM_THRU', '#3b82f6', 'dashed'],
      ['Fall-through', 'FALL_THROUGH', '#64748b', 'dotted'],
    ];

    types.forEach(([label, edgeType, color, style]) => {
      const item = document.createElement('span');
      item.className = 'cg-legend__item';
      if (_hiddenTypes.has(edgeType)) item.classList.add('cg-legend__item--off');
      item.innerHTML = `<span class="cg-legend__line" style="border-top:2px ${style} ${color};background:none;"></span>${label}`;
      item.title = `Click to toggle ${label} edges`;

      item.addEventListener('click', () => {
        if (_hiddenTypes.has(edgeType)) {
          _hiddenTypes.delete(edgeType);
          item.classList.remove('cg-legend__item--off');
        } else {
          _hiddenTypes.add(edgeType);
          item.classList.add('cg-legend__item--off');
        }
        applyEdgeVisibility();
      });

      legend.appendChild(item);
    });
  }

  /**
   * Show/hide SVG edges based on _hiddenTypes set.
   */
  function applyEdgeVisibility() {
    if (!container) return;
    container.querySelectorAll('.cg-edge').forEach(el => {
      const hidden = [..._hiddenTypes].some(t => el.classList.contains(`cg-edge--${t}`));
      el.style.display = hidden ? 'none' : '';
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
    const CF_V_GAP = 90;
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

    // Compute grid positions for orthogonal routing
    const cfNodeGrid = {};
    files.forEach((f, i) => {
      cfNodeGrid[f] = { col: i % CF_COLS, row: Math.floor(i / CF_COLS) };
    });

    // Lane allocation for cross-file channels
    const cfChannelLanes = {};
    function cfAssignLane(key) {
      if (cfChannelLanes[key] == null) cfChannelLanes[key] = 0;
      return cfChannelLanes[key]++;
    }

    // Draw cross-edges with orthogonal routing
    (data.cross_edges || []).forEach(edge => {
      const src = positions[edge.source_file];
      const tgt = positions[edge.target_file];
      if (!src || !tgt) return;

      const edgeType = edge.edge_type || edge.type || 'UNKNOWN';
      const color = CF_EDGE_COLORS[edgeType] || '#64748b';
      const srcGrid = cfNodeGrid[edge.source_file];
      const tgtGrid = cfNodeGrid[edge.target_file];
      const arrowGap = 8;
      const sy = src.y + CF_NODE_H / 2;
      const ty = tgt.y - CF_NODE_H / 2 - arrowGap;

      let pts;

      if (edge.source_file === edge.target_file) {
        // Self-reference: small loop off the right side
        const loopR = 14;
        const rx = src.x + CF_NODE_W / 2 + 6;
        const d = `M ${src.x + CF_NODE_W / 2} ${src.y - 6}`
          + ` C ${rx + loopR} ${src.y - 6}, ${rx + loopR} ${src.y + 6}, ${src.x + CF_NODE_W / 2} ${src.y + 6}`;
        const line = svgEl('path', {
          d, stroke: color, 'stroke-width': '1.5', fill: 'none',
          'marker-end': `url(#cf-arrow-${edgeType})`,
          class: `cg-edge cg-edge--${edgeType}`,
        });
        const title = svgEl('title');
        title.textContent = `${edge.source_file} \u2192 ${edge.target_file} (${edgeType}: ${edge.source || ''})`;
        line.appendChild(title);
        svg.appendChild(line);
        return;

      } else if (srcGrid.row < tgtGrid.row) {
        // Forward edge
        const channelKey = `cf-fwd-${srcGrid.row}`;
        const lane = cfAssignLane(channelKey);
        const channelY = src.y + CF_NODE_H / 2 + 10 + lane * LANE_W;

        if (srcGrid.col === tgtGrid.col) {
          if (lane === 0) {
            pts = [{ x: src.x, y: sy }, { x: tgt.x, y: ty }];
          } else {
            const jog = lane * LANE_W * (lane % 2 === 0 ? 1 : -1);
            pts = [
              { x: src.x, y: sy }, { x: src.x, y: channelY },
              { x: src.x + jog, y: channelY }, { x: src.x + jog, y: ty - 10 },
              { x: tgt.x, y: ty },
            ];
          }
        } else {
          pts = [
            { x: src.x, y: sy }, { x: src.x, y: channelY },
            { x: tgt.x, y: channelY }, { x: tgt.x, y: ty },
          ];
        }

      } else if (srcGrid.row > tgtGrid.row) {
        // Backward edge — route around periphery
        const channelKey = `cf-back-${srcGrid.row}-${tgtGrid.row}`;
        const lane = cfAssignLane(channelKey);
        const isLeft = src.x <= totalW / 2;
        const sideX = isLeft
          ? CF_PAD / 2 - 10 - lane * LANE_W
          : totalW - CF_PAD / 2 + 10 + lane * LANE_W;
        const srcChannelY = src.y + CF_NODE_H / 2 + 10 + lane * LANE_W;
        const tgtChannelY = tgt.y - CF_NODE_H / 2 - arrowGap - 10 - lane * LANE_W;

        pts = [
          { x: src.x, y: sy }, { x: src.x, y: srcChannelY },
          { x: sideX, y: srcChannelY }, { x: sideX, y: tgtChannelY },
          { x: tgt.x, y: tgtChannelY }, { x: tgt.x, y: ty },
        ];

      } else {
        // Same row
        const channelKey = `cf-same-${srcGrid.row}`;
        const lane = cfAssignLane(channelKey);
        const channelY = src.y + CF_NODE_H / 2 + 10 + lane * LANE_W;

        pts = [
          { x: src.x, y: sy }, { x: src.x, y: channelY },
          { x: tgt.x, y: channelY }, { x: tgt.x, y: ty },
        ];
      }

      const d = buildOrthogonalPath(pts);
      const line = svgEl('path', {
        d, stroke: color, 'stroke-width': '1.5', fill: 'none',
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

/**
 * network-graph.js -- SVG hub-and-spoke visualization of the 6-node network.
 *
 * CLEARING sits at the center, 5 banks are arranged at 72-degree intervals
 * on a radius. Static spoke lines connect each bank to the hub. Nodes show
 * chain health (green ring = valid, red = broken). Click a node to open the
 * detail popup. Transaction events animate as edge flashes or node pulses.
 */

const NetworkGraph = (() => {

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const WIDTH = 600;
  const HEIGHT = 500;
  const CX = WIDTH / 2;
  const CY = HEIGHT / 2 + 10;
  const RADIUS = 170;

  const NODES = ['BANK_A', 'BANK_B', 'BANK_C', 'BANK_D', 'BANK_E'];
  const LABELS = {
    BANK_A: 'BANK A', BANK_B: 'BANK B', BANK_C: 'BANK C',
    BANK_D: 'BANK D', BANK_E: 'BANK E', CLEARING: 'CLEARING',
  };
  const SUBLABELS = {
    BANK_A: 'Retail', BANK_B: 'Corporate', BANK_C: 'Wealth',
    BANK_D: 'Institutional', BANK_E: 'Community', CLEARING: 'Hub',
  };

  let svg = null;
  let positions = {};
  let healthRings = {};

  /**
   * Calculate node positions: hub at center, banks at 72-degree intervals.
   */
  function calcPositions() {
    positions.CLEARING = { x: CX, y: CY };
    NODES.forEach((node, i) => {
      const angle = (i * 72 - 90) * (Math.PI / 180);  // Start from top
      positions[node] = {
        x: CX + RADIUS * Math.cos(angle),
        y: CY + RADIUS * Math.sin(angle),
      };
    });
  }

  /**
   * Create an SVG element with attributes.
   */
  function svgEl(tag, attrs = {}) {
    const el = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    return el;
  }

  /**
   * Initialize the SVG graph inside the container element.
   */
  function init() {
    const container = document.getElementById('graphContainer');
    if (!container) return;

    calcPositions();

    svg = svgEl('svg', { viewBox: `0 0 ${WIDTH} ${HEIGHT}`, preserveAspectRatio: 'xMidYMid meet' });

    // Defs for glow effects
    const defs = svgEl('defs');
    NODES.concat(['CLEARING']).forEach(node => {
      const filter = svgEl('filter', { id: `glow-${node}`, x: '-50%', y: '-50%', width: '200%', height: '200%' });
      const blur = svgEl('feGaussianBlur', { stdDeviation: '4', result: 'coloredBlur' });
      const merge = svgEl('feMerge');
      merge.appendChild(svgEl('feMergeNode', { in: 'coloredBlur' }));
      merge.appendChild(svgEl('feMergeNode', { in: 'SourceGraphic' }));
      filter.appendChild(blur);
      filter.appendChild(merge);
      defs.appendChild(filter);
    });

    // Health glow filters (green = valid, red = broken)
    const glowValid = svgEl('filter', { id: 'glow-health-valid', x: '-50%', y: '-50%', width: '200%', height: '200%' });
    const blurValid = svgEl('feGaussianBlur', { stdDeviation: '7', result: 'glow' });
    const floodValid = svgEl('feFlood', { 'flood-color': '#22c55e', 'flood-opacity': '0.6', result: 'color' });
    const compValid = svgEl('feComposite', { in: 'color', in2: 'glow', operator: 'in', result: 'colorGlow' });
    const mergeValid = svgEl('feMerge');
    mergeValid.appendChild(svgEl('feMergeNode', { in: 'colorGlow' }));
    mergeValid.appendChild(svgEl('feMergeNode', { in: 'SourceGraphic' }));
    glowValid.append(blurValid, floodValid, compValid, mergeValid);
    defs.appendChild(glowValid);

    const glowBroken = svgEl('filter', { id: 'glow-health-broken', x: '-50%', y: '-50%', width: '200%', height: '200%' });
    const blurBroken = svgEl('feGaussianBlur', { stdDeviation: '7', result: 'glow' });
    const floodBroken = svgEl('feFlood', { 'flood-color': '#ef4444', 'flood-opacity': '0.6', result: 'color' });
    const compBroken = svgEl('feComposite', { in: 'color', in2: 'glow', operator: 'in', result: 'colorGlow' });
    const mergeBroken = svgEl('feMerge');
    mergeBroken.appendChild(svgEl('feMergeNode', { in: 'colorGlow' }));
    mergeBroken.appendChild(svgEl('feMergeNode', { in: 'SourceGraphic' }));
    glowBroken.append(blurBroken, floodBroken, compBroken, mergeBroken);
    defs.appendChild(glowBroken);

    svg.appendChild(defs);

    // Spoke lines (banks to hub)
    const spokesGroup = svgEl('g', { class: 'spokes' });
    NODES.forEach(node => {
      const line = svgEl('line', {
        x1: positions.CLEARING.x, y1: positions.CLEARING.y,
        x2: positions[node].x, y2: positions[node].y,
        class: 'spoke-line', 'data-from': 'CLEARING', 'data-to': node,
      });
      spokesGroup.appendChild(line);
    });
    svg.appendChild(spokesGroup);

    // Animation layer (edge flashes go here)
    const animLayer = svgEl('g', { id: 'animLayer' });
    svg.appendChild(animLayer);

    // Node groups
    const nodesGroup = svgEl('g', { class: 'nodes' });

    const allNodes = ['CLEARING'].concat(NODES);
    allNodes.forEach(node => {
      const pos = positions[node];
      const color = Utils.bankColorHex(node);
      const g = svgEl('g', { class: 'node-group', 'data-node': node });

      const nodeR = node === 'CLEARING' ? 46 : 38;
      const glowR = node === 'CLEARING' ? 42 : 34;

      // Outer ring (unified identity + health indicator)
      const ring = svgEl('circle', {
        cx: pos.x, cy: pos.y, r: nodeR,
        fill: 'none', stroke: color, 'stroke-width': 3.5,
        class: 'node-ring', opacity: 0.8,
      });
      healthRings[node] = { ring, defaultColor: color };

      // Inner glow
      const glow = svgEl('circle', {
        cx: pos.x, cy: pos.y, r: glowR,
        fill: color, opacity: 0.15,
        filter: `url(#glow-${node})`,
      });

      // Label
      const label = svgEl('text', {
        x: pos.x, y: pos.y - 3, class: 'node-label',
      });
      label.textContent = LABELS[node];

      // Sublabel
      const sublabel = svgEl('text', {
        x: pos.x, y: pos.y + 13, class: 'node-sublabel',
      });
      sublabel.textContent = SUBLABELS[node];

      g.appendChild(glow);
      g.appendChild(ring);
      g.appendChild(label);
      g.appendChild(sublabel);

      // Click handler
      g.addEventListener('click', () => {
        if (typeof Dashboard !== 'undefined' && Dashboard.showNodeDetail) {
          Dashboard.showNodeDetail(node);
        }
        if (typeof EventBus !== 'undefined') {
          EventBus.emit('selection.changed', {
            type: 'node', id: node, context: { tab: 'dashboard' }
          });
        }
      });

      nodesGroup.appendChild(g);
    });
    svg.appendChild(nodesGroup);

    container.innerHTML = '';
    container.appendChild(svg);
  }

  /**
   * Animate a transaction: external flashes edge src→HUB→dest, internal pulses source.
   * Capped at 10 concurrent animations to prevent SVG element buildup during bursts.
   * @param {object} event - SSE event data
   */
  let _activeAnims = 0;
  const MAX_ANIMS = 10;

  function animateTransaction(event) {
    if (!svg) return;
    if (_activeAnims >= MAX_ANIMS) return;  // Skip during burst
    const animLayer = svg.getElementById('animLayer');
    if (!animLayer) return;

    if (event.type === 'external' && event.dest_bank) {
      _activeAnims++;
      // Flash source → CLEARING
      flashEdge(animLayer, event.bank, 'CLEARING', Utils.bankColorHex(event.bank));
      // Flash CLEARING → dest (delayed)
      setTimeout(() => {
        flashEdge(animLayer, 'CLEARING', event.dest_bank, Utils.bankColorHex(event.dest_bank));
      }, 300);
      setTimeout(() => { _activeAnims--; }, 650);
    } else if (event.bank) {
      _activeAnims++;
      // Internal: pulse the source node
      pulseNode(animLayer, event.bank);
      setTimeout(() => { _activeAnims--; }, 550);
    }
  }

  function flashEdge(layer, from, to, color) {
    const p1 = positions[from];
    const p2 = positions[to];
    if (!p1 || !p2) return;

    const line = svgEl('line', {
      x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y,
      stroke: color, class: 'edge-flash',
    });
    layer.appendChild(line);
    setTimeout(() => line.remove(), 650);
  }

  function pulseNode(layer, node) {
    const pos = positions[node];
    if (!pos) return;

    const circle = svgEl('circle', {
      cx: pos.x, cy: pos.y, r: 28,
      fill: Utils.bankColorHex(node), opacity: 0.4,
      class: 'node-pulse',
    });
    layer.appendChild(circle);
    setTimeout(() => circle.remove(), 550);
  }

  /**
   * Refresh chain health rings by polling GET /api/nodes.
   */
  async function refreshNodeData() {
    try {
      const nodes = await ApiClient.get('/api/nodes');
      nodes.forEach(n => {
        setNodeHealth(n.node, n.chain_valid);
      });
    } catch {
      // Silently fail — rings stay transparent
    }
  }

  /**
   * Set a single node's health ring color.
   * @param {string} node - Node name (e.g. 'BANK_A')
   * @param {boolean} isValid - true = green, false = red
   */
  function setNodeHealth(node, isValid) {
    const entry = healthRings[node];
    if (!entry) return;
    const { ring } = entry;
    ring.setAttribute('stroke', isValid ? '#22c55e' : '#ef4444');
    ring.classList.remove('node-ring--valid', 'node-ring--broken');
    ring.classList.add(isValid ? 'node-ring--valid' : 'node-ring--broken');
  }

  /**
   * Reset all health rings to their default bank color (neutral state).
   */
  function resetHealthRings() {
    Object.values(healthRings).forEach(({ ring, defaultColor }) => {
      ring.setAttribute('stroke', defaultColor);
      ring.classList.remove('node-ring--valid', 'node-ring--broken');
    });
  }

  /**
   * Pulse all 6 health rings simultaneously (used during Integrity Check).
   * Applies the CSS pulse animation, removed after a duration.
   * @param {number} durationMs - how long to pulse (default 2000ms)
   */
  function pulseAllRings(durationMs = 2000) {
    Object.values(healthRings).forEach(({ ring }) => {
      ring.classList.add('node-ring--checking');
    });
    setTimeout(() => {
      Object.values(healthRings).forEach(({ ring }) => {
        ring.classList.remove('node-ring--checking');
      });
    }, durationMs);
  }

  return { init, animateTransaction, refreshNodeData, setNodeHealth, resetHealthRings, pulseAllRings };
})();

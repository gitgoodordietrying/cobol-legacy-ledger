/**
 * network-graph.js -- SVG hub-and-spoke visualization of the 6-node network.
 *
 * CLEARING sits at the center, 5 banks are arranged at 72-degree intervals
 * on a radius. Static spoke lines connect each bank to the hub. Nodes show
 * chain health (green dot = valid, red = broken). Click a node to open the
 * detail popup. Transaction events animate as edge flashes or node pulses.
 */

const NetworkGraph = (() => {

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const WIDTH = 800;
  const HEIGHT = 560;
  const CX = WIDTH / 2;
  const CY = HEIGHT / 2;
  const RADIUS = 190;

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
  let healthDots = {};

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

      // Outer ring
      const ring = svgEl('circle', {
        cx: pos.x, cy: pos.y, r: node === 'CLEARING' ? 34 : 28,
        fill: 'none', stroke: color, 'stroke-width': 2,
        class: 'node-ring', opacity: 0.8,
      });

      // Inner glow
      const glow = svgEl('circle', {
        cx: pos.x, cy: pos.y, r: node === 'CLEARING' ? 30 : 24,
        fill: color, opacity: 0.12,
        filter: `url(#glow-${node})`,
      });

      // Label
      const label = svgEl('text', {
        x: pos.x, y: pos.y - 2, class: 'node-label',
      });
      label.textContent = LABELS[node];

      // Sublabel
      const sublabel = svgEl('text', {
        x: pos.x, y: pos.y + 11, class: 'node-sublabel',
      });
      sublabel.textContent = SUBLABELS[node];

      // Chain health dot
      const dotY = pos.y + (node === 'CLEARING' ? 34 : 28) + 10;
      const dot = svgEl('circle', {
        cx: pos.x, cy: dotY, r: 4,
        fill: '#64748b', class: 'chain-health-dot',
      });
      healthDots[node] = dot;

      g.appendChild(glow);
      g.appendChild(ring);
      g.appendChild(label);
      g.appendChild(sublabel);
      g.appendChild(dot);

      // Click handler
      g.addEventListener('click', () => {
        if (typeof Dashboard !== 'undefined' && Dashboard.showNodeDetail) {
          Dashboard.showNodeDetail(node);
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
   * @param {object} event - SSE event data
   */
  function animateTransaction(event) {
    if (!svg) return;
    const animLayer = svg.getElementById('animLayer');
    if (!animLayer) return;

    if (event.type === 'external' && event.dest_bank) {
      // Flash source → CLEARING
      flashEdge(animLayer, event.bank, 'CLEARING', Utils.bankColorHex(event.bank));
      // Flash CLEARING → dest (delayed)
      setTimeout(() => {
        flashEdge(animLayer, 'CLEARING', event.dest_bank, Utils.bankColorHex(event.dest_bank));
      }, 300);
    } else if (event.bank) {
      // Internal: pulse the source node
      pulseNode(animLayer, event.bank);
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
   * Refresh chain health dots by polling GET /api/nodes.
   */
  async function refreshNodeData() {
    try {
      const nodes = await ApiClient.get('/api/nodes');
      nodes.forEach(n => {
        const dot = healthDots[n.node];
        if (dot) {
          dot.setAttribute('fill', n.chain_valid ? '#22c55e' : '#ef4444');
        }
      });
    } catch {
      // Silently fail — dots stay gray
    }
  }

  return { init, animateTransaction, refreshNodeData };
})();

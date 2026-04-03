/**
 * fun-facts.js -- Toggleable educational overlay with COBOL history and
 * practitioner anecdotes, plus a COBOL timeline modal.
 *
 * When the toggle is ON, small (i) icons appear next to relevant UI
 * elements across all tabs. Clicking an icon shows a popover with
 * the fact. Facts are tab-aware — only icons for the current tab
 * (and 'all' tab facts) are placed.
 *
 * The timeline is a modal with 22+ milestones across three tracks:
 * COBOL language evolution, IBM hardware generations, and the
 * project's fictional developer history.
 *
 * All data is embedded — no API calls. The system works with or
 * without this module loaded (graceful degradation per WS6 spec).
 */

const FunFacts = (() => {

  let _active = false;
  const LS_KEY = 'cll_fun_facts';

  /* ── Fact Data (35+ facts) ─────────────────────────────────── */

  const FACTS = [
    // ── Hardware ──
    { id: 'hw1', tab: 'dashboard', anchor: '#networkGraph',
      title: 'IBM z16 Throughput',
      body: 'The IBM z16 processes 25 billion encrypted transactions per day at 5.2 GHz. Its on-chip AI accelerator scores 100% of credit card transactions in real-time (1ms latency, 300 billion inferences/day).' },
    { id: 'hw2', tab: 'all', anchor: '#healthDot',
      title: 'Mainframe Efficiency',
      body: 'Five z16 systems replace 192 x86 servers (10,364 cores) with 75% less energy. The z17 (2025) pushes to Telum II at 5.5 GHz with 64 TB DDR5.' },
    // ── Economics ──
    { id: 'ec1', tab: 'dashboard', anchor: '#simControls',
      title: 'MIPS Economics',
      body: 'Large banks deploy 300,000-400,000+ MIPS at ~$1,200/MIPS. 68% of mainframe costs are software licensing, not hardware.' },
    // ── Scale ──
    { id: 'sc1', tab: 'dashboard', anchor: '#btnStart',
      title: 'COBOL at Global Scale',
      body: 'COBOL processes 85-90% of the world\'s credit card transactions. CICS benchmarks: 174,000 transactions/second per single LPAR.' },
    { id: 'sc2', tab: 'analysis', anchor: '#btnAnalyze',
      title: 'Legacy Scale',
      body: 'A major EU bank has 6 million lines of COBOL. Rewrite estimates range from 5 to 20+ years. Most shops choose augmentation over replacement.' },
    // ── Migration Failures ──
    { id: 'mf1', tab: 'dashboard', anchor: '#btnVerify',
      title: 'TSB Bank Migration (2018)',
      body: 'TSB migrated 5.2 million customers off a mainframe. 1.9 million were locked out. Total cost: \u00A3330M in losses + \u00A348.65M in regulatory fines.' },
    { id: 'mf2', tab: 'dashboard', anchor: '#eventFeed',
      title: 'Queensland Health Payroll',
      body: 'Queensland Health\'s payroll replacement cost $1.2B AUD to remediate. The COBOL system it replaced had worked for decades.' },
    // ── Silent Killers ──
    { id: 'sk1', tab: 'analysis', anchor: '#analysisSummary',
      title: 'Silent Truncation',
      body: 'MOVE 1000005 TO PIC 9(6) silently stores 000005 \u2014 the leading 1 disappears. No error, no warning. This is why mainframe developers trust nothing.' },
    { id: 'sk2', tab: 'analysis', anchor: '#btnCompare',
      title: 'IEEE 754 vs Packed Decimal',
      body: '0.1 + 0.2 = 0.30000000000000004 in IEEE 754. COMP-3 packed decimal is exact by construction \u2014 this is why banks use COBOL for money.' },
    // ── Human Cost ──
    { id: 'hc1', tab: 'all', anchor: '#roleSelect',
      title: 'Ramp-Up Time',
      body: '2-3 year ramp-up for new COBOL hires. Over 70% of business rules exist only in code, not documentation.' },
    { id: 'hc2', tab: 'analysis', anchor: '#callGraphCard',
      title: 'The Failed Rewrite',
      body: 'Two attempts to replace one legacy system failed because teams couldn\'t replicate undocumented business logic. The first two years after redevelopment were spent putting "lost" business rules back in.' },
    // ── Language Quirks ──
    { id: 'lq1', tab: 'analysis', anchor: '#analysisFileSelect',
      title: 'Overpunch Sign Encoding',
      body: '-123 in PIC S9(3) DISPLAY format displays as "12L". The sign is encoded in the last nibble of the last byte \u2014 an IBM System/360 convention from 1964.' },
    { id: 'lq2', tab: 'analysis', anchor: '#traceEntrySelect',
      title: 'EBCDIC Collating Sequence',
      body: 'EBCDIC sorts \'a\' < \'A\' < \'1\'. ASCII reverses this entirely. Migrating sort routines between platforms breaks silently.' },
    // ── Banking Precision ──
    { id: 'bp1', tab: 'dashboard', anchor: '#statVolume',
      title: 'Banking Field Sizes',
      body: 'Banks use PIC S9(13)V99 COMP-3 (8 bytes, \u00b1$999 trillion exact). Interest rates: PIC 9(3)V9(6). Account numbers are PIC X(16) not PIC 9 \u2014 to preserve leading zeros.' },
    { id: 'bp2', tab: 'mainframe', anchor: '#btnCompile',
      title: 'Banker\'s Rounding',
      body: 'COBOL ROUNDED defaults to round-half-up, not round-half-to-even. Banks must implement round-half-to-even explicitly in COBOL \u2014 it\'s not the default.' },
    // ── Architecture ──
    { id: 'ar1', tab: 'dashboard', anchor: '#graphContainer',
      title: 'Parallel Sysplex',
      body: 'Parallel Sysplex clusters 32 z/OS systems via Coupling Facility (sub-8\u03bcs latency). DB2 Data Sharing: actual concurrent read/write across systems, not replication.' },
    { id: 'ar2', tab: 'dashboard', anchor: '#cobolViewer',
      title: 'Seven Nines',
      body: 'DS8900F storage achieves 99.99999% availability. GDPS Metro Mirror: RPO=0 (zero data loss), RTO in seconds.' },
    // ── Y2K ──
    { id: 'y2k1', tab: 'analysis', anchor: '#btnCrossFile',
      title: 'Y2K Is Not Over',
      body: 'Windowing code with pivot year 40 means 2050 is interpreted as 1950. 30-year mortgages from 2020 are already crossing this boundary. The COBOL equivalent of the Unix 2038 problem.' },
    // ── I/O ──
    { id: 'io1', tab: 'dashboard', anchor: '#btnTamper',
      title: 'Mainframe I/O',
      body: 'FICON channels at 16/32 Gbps with dedicated channel subsystem offloading I/O from CPUs. zHyperLink: 18-30\u03bcs latency (10x lower than FICON).' },
    // ── Availability ──
    { id: 'av1', tab: 'dashboard', anchor: '#btnReset',
      title: 'Crypto Hardware',
      body: 'Crypto Express8S HSMs: FIPS 140-2 Level 4 (highest commercially available) with quantum-safe cryptography. Every z16 encrypts 100% of data at rest and in flight.' },
    // ── Mainframe tab facts ──
    { id: 'mt1', tab: 'mainframe', anchor: '#mainframeTemplateSelect',
      title: 'Column Rules',
      body: 'COBOL\'s fixed format dates to punched cards: cols 1-6 (sequence number), col 7 (indicator: * for comment, - for continuation), cols 8-11 (A margin), cols 12-72 (B margin), cols 73-80 (identification).' },
    { id: 'mt2', tab: 'mainframe', anchor: '#dialectSelect',
      title: 'Dialect Wars',
      body: 'IBM Enterprise COBOL, Micro Focus Visual COBOL, and GnuCOBOL all claim COBOL 2014 compliance but differ on EXEC CICS, COMP-1/2 formats, SCREEN SECTION, and XML GENERATE.' },
    { id: 'mt3', tab: 'mainframe', anchor: '#mainframeTerminal',
      title: 'JCL Job Control',
      body: 'JCL (Job Control Language) is older than COBOL. Every mainframe batch job starts with // in column 1. A missing comma in JCL can crash a production batch run.' },
    // ── Analysis tab extras ──
    { id: 'an1', tab: 'analysis', anchor: '#tabDetail',
      title: 'McCracken on ALTER (1976)',
      body: '"There is no way to determine the state of a program containing ALTER statements without simulating the execution of the program." \u2014 Daniel McCracken, 1976. ALTER was deprecated in COBOL-85, removed in COBOL-2002.' },
    { id: 'an2', tab: 'analysis', anchor: '#btnDataFlow',
      title: 'Shared State Problem',
      body: 'In COBOL, all Working-Storage variables are globally accessible. When 23 paragraphs write the same field and execution order depends on GO TO chains, the final value is effectively random.' },
    // ── General ──
    { id: 'gn1', tab: 'all', anchor: '.nav__brand',
      title: 'Grace Hopper',
      body: 'Grace Hopper\'s team delivered the first COBOL compiler in 1960. She advocated that programs should be written in English-like language, not mathematical notation. COBOL was the result.' },
    { id: 'gn2', tab: 'all', anchor: '#tab-dashboard',
      title: 'COBOL Is Not Dead',
      body: 'There are estimated 220-240 billion lines of COBOL in production worldwide. More COBOL was written in 2020 than in any previous year \u2014 driven by pandemic unemployment systems.' },
    { id: 'gn3', tab: 'dashboard', anchor: '#narrativeBanner',
      title: 'Sunday Night Culture',
      body: 'Mainframe batch runs traditionally execute Sunday night. Deployment teams work weekends. "If it breaks on Monday morning, you\'re the one they call \u2014 not the vendor."' },
    { id: 'gn4', tab: 'dashboard', anchor: '#btnPause',
      title: 'CICS Response Time',
      body: 'CICS online transactions must complete in under 1 second. At 174,000 TPS, a 100ms delay means 17,400 transactions queue up. Mainframe developers think in milliseconds.' },
  ];

  /* ── Timeline Data (22+ milestones) ────────────────────────── */

  const TIMELINE = [
    { year: 1959, track: 'language', title: 'COBOL-60 Specification', desc: 'CODASYL committee defines COBOL. Grace Hopper\'s FLOW-MATIC is the primary influence.' },
    { year: 1960, track: 'language', title: 'First COBOL Compiler', desc: 'RCA and Remington Rand deliver the first compilers. The same program runs on two different machines for the first time.' },
    { year: 1964, track: 'hardware', title: 'IBM System/360', desc: 'Single architecture family from small to large. EBCDIC, packed decimal hardware instructions. The machine COBOL was born to run on.' },
    { year: 1968, track: 'language', title: 'ANSI Standard (COBOL-68)', desc: 'First ANSI standard. GO TO and ALTER are the primary control flow. No structured programming.' },
    { year: 1974, track: 'language', title: 'COBOL-74', desc: 'Minor revision. PERFORM THRU becomes common. Still no END-IF or EVALUATE.' },
    { year: 1974, track: 'project', title: 'JRK writes PAYROLL.cob', desc: 'The original spaghetti. GO TO + ALTER state machine. No comments, no structure. Still in production 52 years later.' },
    { year: 1976, track: 'language', title: 'McCracken ALTER Warning', desc: '"There is no way to determine the state of a program containing ALTER." The academic community sounds the alarm.' },
    { year: 1983, track: 'project', title: 'PMR writes TAXCALC.cob', desc: '6-level nested IF without END-IF. PERFORM THRU for tax brackets. Misleading comments.' },
    { year: 1985, track: 'language', title: 'COBOL-85 (Structured)', desc: 'END-IF, END-PERFORM, EVALUATE. ALTER deprecated. The structured programming revolution \u2014 but legacy code doesn\'t get rewritten.' },
    { year: 1991, track: 'project', title: 'SLW writes DEDUCTN.cob', desc: 'Structured/spaghetti hybrid. Mixed COMP types. The "we don\'t have budget to rewrite" era.' },
    { year: 2000, track: 'language', title: 'Y2K', desc: 'Billions spent on 2-digit year fixes. Most shops use windowing (pivot years) instead of expanding fields. The fix becomes its own time bomb.' },
    { year: 2002, track: 'language', title: 'COBOL-2002 (OO COBOL)', desc: 'ALTER deleted from the standard. Object-oriented features added. Almost nobody uses them.' },
    { year: 2002, track: 'project', title: 'Y2K team writes PAYBATCH.cob', desc: 'Excessive DISPLAY tracing, dead Y2K windowing code, batch formatting artifacts.' },
    { year: 2014, track: 'language', title: 'COBOL 2014 (Current ISO)', desc: 'Current standard. Dynamic tables, enhanced arithmetic. Adoption is slow \u2014 most shops still compile for COBOL-85 compatibility.' },
    { year: 2017, track: 'hardware', title: 'IBM z14', desc: 'Pervasive encryption: 100% data encrypted without app changes. 3.5x crypto performance.' },
    { year: 2019, track: 'hardware', title: 'IBM z15', desc: 'Data Privacy Passports. Instant Recovery. 190 cores, 40 TB. On-chip deflate compression at 17x throughput.' },
    { year: 2022, track: 'hardware', title: 'IBM z16 (Telum)', desc: '7nm 5.2 GHz. Industry-first on-chip AI accelerator: 300B inferences/day at 1ms. 200 cores, 40 TB. Quantum-safe cryptography.' },
    { year: 2025, track: 'hardware', title: 'IBM z17 (Telum II)', desc: '5.5 GHz. 32 cores per chip. 64 TB DDR5. The mainframe continues to evolve faster than the "replace it" crowd expected.' },
  ];

  /* ── Toggle ────────────────────────────────────────────────── */

  function handleToggle() {
    _active = !_active;
    localStorage.setItem(LS_KEY, _active ? '1' : '0');

    const toggle = document.getElementById('funFactsToggle');
    if (toggle) toggle.checked = _active;

    if (_active) {
      placeFacts();
      Utils.showToast('Fun Facts: ON', 'info');
    } else {
      removeFacts();
      Utils.showToast('Fun Facts: OFF', 'info');
    }
  }

  /* ── Fact Placement ────────────────────────────────────────── */

  function getCurrentTab() {
    const active = document.querySelector('.nav__tab--active');
    return active?.dataset?.view || 'dashboard';
  }

  function placeFacts() {
    removeFacts();
    if (!_active) return;

    const currentTab = getCurrentTab();

    FACTS.forEach(fact => {
      if (fact.tab !== 'all' && fact.tab !== currentTab) return;

      const anchor = document.querySelector(fact.anchor);
      if (!anchor) return;

      // Don't double-place
      if (anchor.querySelector(`[data-fact-id="${fact.id}"]`)) return;

      const icon = document.createElement('span');
      icon.className = 'help-tip help-tip--fun-fact';
      icon.setAttribute('data-fact-id', fact.id);
      icon.textContent = 'i';
      icon.title = fact.title;

      icon.addEventListener('click', (e) => {
        e.stopPropagation();
        showFactPopover(icon, fact);
      });

      // Append to the anchor element
      anchor.appendChild(icon);
    });
  }

  function removeFacts() {
    document.querySelectorAll('.help-tip--fun-fact').forEach(el => el.remove());
    document.querySelectorAll('.fun-fact-popover').forEach(el => el.remove());
  }

  function showFactPopover(icon, fact) {
    // Remove existing popovers
    document.querySelectorAll('.fun-fact-popover').forEach(el => el.remove());

    const pop = document.createElement('div');
    pop.className = 'fun-fact-popover glass';
    pop.innerHTML = `
      <div class="fun-fact-popover__title">${Utils.escapeHtml(fact.title)}</div>
      <div class="fun-fact-popover__body">${Utils.escapeHtml(fact.body)}</div>`;

    // Position near the icon
    icon.style.position = icon.style.position || 'relative';
    icon.parentElement.style.position = icon.parentElement.style.position || 'relative';
    icon.parentElement.appendChild(pop);

    // Close on outside click
    const handler = (e) => {
      if (!pop.contains(e.target) && e.target !== icon) {
        pop.remove();
        document.removeEventListener('click', handler);
      }
    };
    setTimeout(() => document.addEventListener('click', handler), 0);
  }

  /* ── Timeline Modal ────────────────────────────────────────── */

  function openTimeline() {
    const existing = document.getElementById('timelineModal');
    if (existing) { existing.style.display = ''; return; }

    const overlay = document.createElement('div');
    overlay.className = 'popup-overlay';
    overlay.id = 'timelineModal';
    overlay.setAttribute('role', 'dialog');

    let html = `<div class="popup popup--wide glass">
      <div class="glass__header">
        <span>COBOL &amp; Mainframe Timeline</span>
        <button class="popup__close" id="timelineClose">&times;</button>
      </div>
      <div class="glass__body timeline-body">
        <div class="timeline">`;

    TIMELINE.forEach(m => {
      const trackCls = `timeline__milestone--${m.track}`;
      html += `<div class="timeline__milestone ${trackCls}">
        <span class="timeline__year">${m.year}</span>
        <span class="timeline__track-badge">${m.track}</span>
        <div class="timeline__title">${Utils.escapeHtml(m.title)}</div>
        <div class="timeline__desc">${Utils.escapeHtml(m.desc)}</div>
      </div>`;
    });

    html += '</div></div></div>';
    overlay.innerHTML = html;

    document.body.appendChild(overlay);

    document.getElementById('timelineClose')?.addEventListener('click', closeTimeline);
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeTimeline();
    });
  }

  function closeTimeline() {
    const modal = document.getElementById('timelineModal');
    if (modal) modal.remove();
  }

  /* ── Init ──────────────────────────────────────────────────── */

  function init() {
    // Restore state from localStorage
    _active = localStorage.getItem(LS_KEY) === '1';

    const toggle = document.getElementById('funFactsToggle');
    if (toggle) {
      toggle.checked = _active;
      toggle.addEventListener('change', handleToggle);
    }

    // Timeline button
    document.getElementById('btnTimeline')?.addEventListener('click', openTimeline);

    // Re-place facts when tab changes
    if (typeof EventBus !== 'undefined') {
      EventBus.on('tab.changed', () => {
        if (_active) placeFacts();
      });
    }

    // Initial placement
    if (_active) {
      // Delay slightly so DOM is settled
      setTimeout(placeFacts, 100);
    }
  }

  return { init, openTimeline };

})();

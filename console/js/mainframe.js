/**
 * mainframe.js -- COBOL Mainframe Dashboard: editor, compiler, JCL output.
 *
 * Virtual dry-erase board where students write, compile, and learn COBOL.
 * The editor uses a transparent textarea over a syntax-highlighted overlay,
 * sharing CobolViewer.highlightLine() for consistent highlighting.
 *
 * Compile flow: textarea -> POST /api/mainframe/compile -> JCL-style output.
 * Mode A uses real GnuCOBOL (cobc). Mode B falls back to validation-only.
 *
 * COBOL CONCEPT: On a real mainframe, a compile-link-go job looks like:
 *   //STEP01 EXEC PGM=IGYCRCTL  (compile)
 *   //STEP02 EXEC PGM=IEWBLINK  (link)
 *   //STEP03 EXEC PGM=STUDENT   (run)
 * Our JCL output simulates this authentic job structure.
 */

const Mainframe = (() => {

  let _format = 'free';  // 'fixed' or 'free'
  let _highlightTimer = null;
  const DEBOUNCE_MS = 200;

  /* ── Quick Reference Data ──────────────────────────────────── */

  const FILE_STATUS = [
    ['00', 'Success'],
    ['10', 'End of file (AT END)'],
    ['22', 'Duplicate key on WRITE'],
    ['23', 'Record not found on READ'],
    ['35', 'File not found on OPEN'],
    ['39', 'File attribute conflict'],
    ['41', 'File already open'],
    ['42', 'File not open'],
    ['46', 'Sequential READ without position'],
    ['47', 'READ on file not opened INPUT/I-O'],
    ['48', 'WRITE on file not opened OUTPUT/I-O'],
  ];

  const ABEND_CODES = [
    ['S0C7', 'Data exception \u2014 invalid packed decimal (COMP-3). The #1 production COBOL abend.'],
    ['S0C4', 'Protection exception \u2014 addressing violation (bad pointer/subscript).'],
    ['S322', 'Time limit exceeded \u2014 infinite loop or runaway PERFORM.'],
    ['S806', 'Module not found \u2014 missing load library member.'],
  ];

  const DIALECT_NOTES = [
    ['EXEC CICS', 'IBM only \u2014 not supported in GnuCOBOL'],
    ['COMP-1/2', 'Float format differs: IBM hex vs IEEE 754'],
    ['SCREEN', 'GnuCOBOL supports; IBM does not'],
    ['COPY...REPLACING', 'Supported everywhere but parsing varies'],
  ];

  /* ── Editor ────────────────────────────────────────────────── */

  function setupEditor() {
    const textarea = document.getElementById('mainframeEditor');
    const overlay = document.getElementById('mainframeOverlay');
    const gutter = document.getElementById('mainframeGutter');
    const content = document.getElementById('mainframeContent');
    if (!textarea || !overlay) return;

    // Sync scroll between textarea and overlay
    textarea.addEventListener('scroll', () => {
      overlay.scrollTop = textarea.scrollTop;
      overlay.scrollLeft = textarea.scrollLeft;
      if (gutter) gutter.scrollTop = textarea.scrollTop;
    });

    // Highlight on input (debounced)
    textarea.addEventListener('input', () => {
      clearTimeout(_highlightTimer);
      _highlightTimer = setTimeout(() => {
        updateOverlay();
        updateLineNumbers();
      }, DEBOUNCE_MS);
    });

    // Also sync on content area scroll
    if (content) {
      content.addEventListener('scroll', () => {
        if (gutter) gutter.scrollTop = content.scrollTop;
      });
    }

    // Initial render
    updateOverlay();
    updateLineNumbers();
    updateColumnIndicators();
  }

  function updateOverlay() {
    const textarea = document.getElementById('mainframeEditor');
    const overlay = document.getElementById('mainframeOverlay');
    if (!textarea || !overlay) return;

    const lines = textarea.value.split('\n');
    const hl = typeof CobolViewer !== 'undefined' && CobolViewer.highlightLine
      ? CobolViewer.highlightLine
      : (line) => Utils.escapeHtml(line);

    overlay.innerHTML = lines.map(line => hl(line)).join('\n');
  }

  function updateLineNumbers() {
    const textarea = document.getElementById('mainframeEditor');
    const gutter = document.getElementById('mainframeGutter');
    if (!textarea || !gutter) return;

    const count = textarea.value.split('\n').length;
    const nums = [];
    for (let i = 1; i <= count; i++) nums.push(i);
    gutter.textContent = nums.join('\n');
  }

  function updateColumnIndicators() {
    const container = document.getElementById('mainframeColIndicators');
    if (!container) return;

    // Measure character width using a hidden span
    const measure = document.createElement('span');
    measure.style.cssText = 'position:absolute;visibility:hidden;font-family:var(--font-mono);font-size:var(--text-xs);white-space:pre;';
    measure.textContent = 'M';
    document.body.appendChild(measure);
    const charW = measure.getBoundingClientRect().width;
    document.body.removeChild(measure);

    const pad = 12; // matches padding var(--sp-3)

    if (_format === 'fixed') {
      container.innerHTML = [
        { col: 7, cls: '7', label: '7' },
        { col: 12, cls: '12', label: '12' },
        { col: 72, cls: '72', label: '72' },
      ].map(c => `
        <div class="mf-editor__col-line mf-editor__col-line--${c.cls}" style="left: ${pad + c.col * charW}px;"></div>
        <span class="mf-editor__col-label" style="left: ${pad + c.col * charW}px;">${c.label}</span>
      `).join('');
    } else {
      container.innerHTML = '';
    }
  }

  function toggleFormat() {
    _format = _format === 'fixed' ? 'free' : 'fixed';
    const badge = document.getElementById('formatBadge');
    if (badge) {
      badge.textContent = _format.toUpperCase();
      badge.className = 'mf-format-badge' + (_format === 'free' ? ' mf-format-badge--free' : '');
    }
    updateColumnIndicators();
  }

  /* ── Templates ─────────────────────────────────────────────── */

  // Default params each codegen template requires
  const TEMPLATE_PARAMS = {
    crud: {
      record_copybook: 'STUDREC',
      record_name: 'STUDENT-RECORD',
      file_name: 'STUDENTS',
      id_field: 'STUD-ID',
    },
    report: {
      input_files: [{ logical_name: 'INPUT-FILE', physical_name: 'STUDENTS.DAT', copybook: 'STUDREC' }],
      report_types: ['SUMMARY', 'DETAIL'],
    },
    batch: {
      input_file: 'STUDENTS.DAT',
      input_copybook: 'STUDREC',
      record_name: 'STUDENT-RECORD',
    },
    copybook: {
      fields: [
        { name: 'STUD-ID', pic: '9(8)' },
        { name: 'STUD-NAME', pic: 'X(30)' },
        { name: 'STUD-GPA', pic: '9V99' },
      ],
    },
  };

  async function loadTemplate() {
    const select = document.getElementById('mainframeTemplateSelect');
    const textarea = document.getElementById('mainframeEditor');
    if (!select || !textarea) return;

    const template = select.value;
    if (!template) return;

    // Confirm if editor has content
    if (textarea.value.trim() && !confirm('This will replace your current code. Continue?')) {
      select.value = '';
      return;
    }

    Utils.showToast(`Loading ${template} template\u2026`, 'info');

    try {
      const data = await ApiClient.post('/api/codegen/generate', {
        template: template,
        name: 'STUDENT',
        params: TEMPLATE_PARAMS[template] || {},
      });

      textarea.value = data.source || '';
      updateOverlay();
      updateLineNumbers();
      Utils.showToast(`Template loaded: ${data.line_count} lines`, 'success');
    } catch (e) {
      Utils.showToast(`Template failed: ${e.message}`, 'danger');
    }

    select.value = '';
  }

  /* ── Compile ───────────────────────────────────────────────── */

  async function compileSource() {
    const textarea = document.getElementById('mainframeEditor');
    if (!textarea || !textarea.value.trim()) {
      Utils.showToast('Nothing to compile', 'info');
      return;
    }

    const btn = document.getElementById('btnCompile');
    if (btn) { btn.disabled = true; btn.textContent = 'Compiling\u2026'; }

    try {
      const result = await ApiClient.post('/api/mainframe/compile', {
        source_text: textarea.value,
        format: _format,
        program_name: 'STUDENT',
        dialect: document.getElementById('dialectSelect')?.value || 'default',
      });

      renderJclOutput(result);

      const msg = result.success ? 'Compilation successful' : 'Compilation failed';
      Utils.showToast(`${msg} (${result.mode} mode)`, result.success ? 'success' : 'danger');
    } catch (e) {
      Utils.showToast(`Compile error: ${e.message}`, 'danger');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Compile'; }
    }
  }

  /* ── JCL Output Rendering ──────────────────────────────────── */

  function renderJclOutput(result) {
    const terminal = document.getElementById('mainframeTerminal');
    if (!terminal) return;

    // Remove placeholder
    const placeholder = terminal.querySelector('.mf-output__placeholder');
    if (placeholder) placeholder.remove();

    const entry = document.createElement('div');
    entry.className = 'mf-output__entry';

    const time = new Date().toLocaleTimeString();
    let html = '';

    // Mode banner for validation-only
    if (result.mode === 'validate') {
      html += '<span class="mf-output__mode-banner">VALIDATION ONLY \u2014 cobc not available</span>\n';
    }

    // JCL job card
    html += '<div class="mf-output__job-card">';
    html += `//STUDENT  JOB (ACCT),'STUDENT',CLASS=A,MSGCLASS=X,TIME=(,${10})\n`;
    html += `//*  ${time}\n`;
    html += `//STEP01   EXEC PGM=IGYCRCTL,PARM='LIB'\n`;
    html += `//SYSPRINT DD SYSOUT=*\n`;
    html += `//SYSIN    DD *\n`;
    html += `//STEP02   EXEC PGM=IEWBLINK,COND=(8,LT,STEP01)\n`;
    html += `//STEP03   EXEC PGM=STUDENT,COND=(8,LT,STEP02)\n`;
    html += `//*\n`;
    html += '</div>';

    // Compile output
    if (result.mode === 'compile') {
      // stdout
      if (result.stdout) {
        result.stdout.split('\n').forEach(line => {
          html += `<span class="mf-output__line">${Utils.escapeHtml(line)}</span>\n`;
        });
      }

      // stderr (errors / warnings)
      if (result.stderr) {
        result.stderr.split('\n').forEach(line => {
          if (!line.trim()) return;
          const isError = /error/i.test(line);
          const isWarn = /warning/i.test(line);
          const cls = isError ? 'mf-output__line--error'
            : isWarn ? 'mf-output__line--warning'
            : 'mf-output__line--info';

          // Extract line number for clickable errors
          const lineMatch = line.match(/:(\d+):/);
          if (lineMatch) {
            html += `<span class="mf-output__line ${cls} mf-output__line--clickable" data-line="${lineMatch[1]}">${Utils.escapeHtml(line)}</span>\n`;
          } else {
            html += `<span class="mf-output__line ${cls}">${Utils.escapeHtml(line)}</span>\n`;
          }
        });
      }
    } else {
      // Mode B: validation results
      if (result.validation && result.validation.length > 0) {
        result.validation.forEach(issue => {
          const cls = issue.level === 'ERROR' ? 'mf-output__line--error' : 'mf-output__line--warning';
          html += `<span class="mf-output__line ${cls}">[${issue.level}] ${Utils.escapeHtml(issue.message)}</span>\n`;
        });
      } else if (result.success) {
        html += '<span class="mf-output__line mf-output__line--success">No validation issues found.</span>\n';
      }
    }

    // MAXCC summary
    const maxcc = result.return_code === 0 ? '0000' : result.return_code === 1 ? '0012' : '0008';
    const maxccCls = result.return_code === 0 ? 'ok' : 'err';
    html += `<div class="mf-output__maxcc mf-output__maxcc--${maxccCls}">`;
    html += `IEF142I STUDENT STEP01 - STEP WAS EXECUTED - COND CODE ${maxcc}`;
    if (result.success) {
      html += '\nIEF142I STUDENT STEP02 - STEP WAS EXECUTED - COND CODE 0000';
    }
    html += '</div>';

    entry.innerHTML = html;

    // Wire clickable error lines -> scroll editor
    entry.querySelectorAll('.mf-output__line--clickable').forEach(el => {
      el.addEventListener('click', () => {
        const lineNum = parseInt(el.dataset.line);
        scrollEditorToLine(lineNum);
      });
    });

    terminal.prepend(entry);
  }

  function scrollEditorToLine(lineNum) {
    const textarea = document.getElementById('mainframeEditor');
    if (!textarea) return;

    const lines = textarea.value.split('\n');
    let charPos = 0;
    for (let i = 0; i < Math.min(lineNum - 1, lines.length); i++) {
      charPos += lines[i].length + 1;
    }

    textarea.focus();
    textarea.setSelectionRange(charPos, charPos + (lines[lineNum - 1]?.length || 0));

    // Scroll to approximate position
    const lineHeight = 18; // approx for var(--text-xs) at 1.5 line-height
    textarea.scrollTop = (lineNum - 5) * lineHeight;
  }

  /* ── Quick Reference Sidebar ───────────────────────────────── */

  function setupSidebar() {
    const sections = document.querySelectorAll('.mf-sidebar__section');
    sections.forEach(section => {
      const header = section.querySelector('.mf-sidebar__header');
      if (header) {
        header.addEventListener('click', () => {
          section.classList.toggle('mf-sidebar__section--open');
        });
      }
    });

    // Render reference tables
    renderRefTable('refFileStatus', FILE_STATUS);
    renderRefTable('refAbendCodes', ABEND_CODES);
    renderRefTable('refDialect', DIALECT_NOTES);
  }

  function renderRefTable(containerId, data) {
    const el = document.getElementById(containerId);
    if (!el) return;

    el.innerHTML = '<table class="mf-ref-table">'
      + data.map(([code, desc]) =>
        `<tr><td>${Utils.escapeHtml(code)}</td><td>${Utils.escapeHtml(desc)}</td></tr>`
      ).join('')
      + '</table>';
  }

  /* ── EventBus Integration ──────────────────────────────────── */

  function setupEventBus() {
    if (typeof EventBus === 'undefined') return;

    // Challenge system stub: load source from Analysis "fix this" link
    EventBus.on('challenge.load', (payload) => {
      const textarea = document.getElementById('mainframeEditor');
      if (!textarea) return;

      if (payload.source_text) {
        textarea.value = payload.source_text;
        updateOverlay();
        updateLineNumbers();
      }

      Utils.showToast(`Challenge loaded: ${payload.paragraph_name || 'COBOL'}`, 'info');

      // Switch to mainframe tab
      if (typeof App !== 'undefined') App.switchView('mainframe');
    });
  }

  /* ── Init ──────────────────────────────────────────────────── */

  function init() {
    setupEditor();
    setupSidebar();
    setupEventBus();

    // Wire buttons
    document.getElementById('btnCompile')?.addEventListener('click', compileSource);
    document.getElementById('btnFormatToggle')?.addEventListener('click', toggleFormat);
    document.getElementById('mainframeTemplateSelect')?.addEventListener('change', loadTemplate);

    // Open first sidebar section by default
    const firstSection = document.querySelector('.mf-sidebar__section');
    if (firstSection) firstSection.classList.add('mf-sidebar__section--open');
  }

  return { init };

})();

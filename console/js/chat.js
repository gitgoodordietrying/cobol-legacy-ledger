/**
 * chat.js -- Chatbot UI with provider switching and session management.
 *
 * Sends messages to POST /api/chat, renders assistant responses with basic
 * markdown, shows tool call cards (collapsible), manages sessions, and
 * handles provider switching between Ollama and Anthropic.
 */

const Chat = (() => {

  let currentSessionId = null;
  let _sending = false;  // Guard against concurrent message submissions
  const sessions = [];  // { id, preview }

  // ── Context state (updated via EventBus) ─────────────────────
  let _currentContext = { tab: 'dashboard', selection: null };

  // ── Tab-scoped prompt chips ──────────────────────────────────
  const TAB_CHIPS = {
    dashboard: [
      'List all accounts in BANK_A',
      'What is a nostro account?',
      'Verify all chains',
      'Run a settlement between BANK_A and BANK_B',
      'Show me CLEARING accounts',
      'Explain inter-bank settlement',
    ],
    analysis: [
      'Analyze PAYROLL.cob',
      'Compare PAYROLL.cob vs TRANSACT.cob',
      'What is PERFORM THRU?',
      'Find dead code in DISPUTE.cob',
      'Explain the ALTER anti-pattern',
      'Trace execution from P-010 in PAYROLL.cob',
    ],
    mainframe: [
      'What are the four COBOL divisions?',
      'Explain COMP-3 packed decimal',
      'How does fixed-format column layout work?',
      'What is a copybook?',
      'Explain PICTURE clause',
      'What is the difference between COMP and COMP-3?',
    ],
    chat: [
      'List all accounts in BANK_A',
      'Explain what PAYROLL.cob does',
      'What is a nostro account?',
      'Compare PAYROLL.cob vs TRANSACT.cob',
      'Verify all chains',
      'What is PERFORM THRU?',
    ],
  };

  /** Get current chips based on active tab context. */
  function getCurrentChips() {
    return TAB_CHIPS[_currentContext.tab] || TAB_CHIPS.chat;
  }

  let _ollamaModels = [];  // Populated dynamically from /api/chat/models
  const ANTHROPIC_MODELS_FULL = ['claude-haiku-4-5-20251001', 'claude-sonnet-4-20250514', 'claude-opus-4-20250514'];
  const ANTHROPIC_MODELS_LIMITED = ['claude-haiku-4-5-20251001'];  // Env key = haiku only
  let _userApiKey = false;  // True if user provided their own key
  let _ollamaAvailable = false;  // True if Ollama is reachable

  /**
   * Initialize chat bindings.
   */
  function init() {
    // Send button
    document.getElementById('btnSend')?.addEventListener('click', sendMessage);

    // Enter to send, Shift+Enter for newline
    const textarea = document.getElementById('chatInput');
    textarea?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Auto-resize textarea
    textarea?.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    });

    // Provider buttons
    document.getElementById('btnOllama')?.addEventListener('click', () => switchProvider('ollama'));
    document.getElementById('btnAnthropic')?.addEventListener('click', () => switchProvider('anthropic'));

    // Model dropdown — switch provider when model changes
    document.getElementById('modelSelect')?.addEventListener('change', () => {
      const provider = document.getElementById('providerName')?.textContent?.split('/')[0] || 'ollama';
      switchProvider(provider);
    });

    // API key input — when user pastes a key and presses Enter, auto-switch to Anthropic
    const apiKeyInput = document.getElementById('apiKeyInput');
    apiKeyInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && apiKeyInput.value.trim()) {
        e.preventDefault();
        switchProvider('anthropic');
      }
    });
    // Also enable the Anthropic button when user types a key
    apiKeyInput?.addEventListener('input', () => {
      const btnAnthropic = document.getElementById('btnAnthropic');
      if (btnAnthropic && apiKeyInput.value.trim()) {
        btnAnthropic.disabled = false;
        btnAnthropic.title = 'Switch to Anthropic Claude (your API key)';
      }
    });

    // New chat
    document.getElementById('btnNewChat')?.addEventListener('click', newChat);

    // Prompt chips
    wireChips();

    // Load provider status
    refreshProviderStatus();

    // Sync role display
    document.getElementById('roleSelect')?.addEventListener('change', () => {
      const role = document.getElementById('roleSelect').value;
      const chatRole = document.getElementById('chatRole');
      if (chatRole) chatRole.textContent = role;
    });

    // ── EventBus subscriptions ───────────────────────────────
    if (typeof EventBus !== 'undefined') {
      EventBus.on('tab.changed', (payload) => {
        _currentContext.tab = payload.tab;
        refreshChipsForTab();
        updateContextBadge();
      });
      EventBus.on('selection.changed', (payload) => {
        _currentContext.selection = payload;
        updateContextBadge();
      });
    }
  }

  /**
   * Send the current message.
   */
  async function sendMessage() {
    if (_sending) return;

    const textarea = document.getElementById('chatInput');
    const message = textarea?.value?.trim();
    if (!message) return;

    _sending = true;
    const sendBtn = document.getElementById('btnSend');
    if (sendBtn) sendBtn.disabled = true;

    // Clear input
    textarea.value = '';
    textarea.style.height = 'auto';

    // Show user message
    appendMessage('user', message);

    // Show typing indicator
    showTyping(true);

    try {
      const tutorToggle = document.getElementById('tutorModeToggle');
      const mode = tutorToggle?.checked ? 'tutor' : 'direct';
      const body = { message, mode };
      if (currentSessionId) body.session_id = currentSessionId;
      // Include context for tab-scoped system prompts
      body.context = {
        tab: _currentContext.tab || 'dashboard',
        selected_file: _currentContext.selection?.type === 'file' ? _currentContext.selection.id : null,
        selected_paragraph: _currentContext.selection?.type === 'paragraph' ? _currentContext.selection.id : null,
        selected_node: _currentContext.selection?.type === 'node' ? _currentContext.selection.id : null,
      };

      const resp = await ApiClient.post('/api/chat', body);

      // Track session
      currentSessionId = resp.session_id;
      trackSession(currentSessionId, message);

      // Show tool calls
      if (resp.tool_calls && resp.tool_calls.length > 0) {
        resp.tool_calls.forEach(tc => appendToolCall(tc));
      }

      // Show assistant response
      appendMessage('assistant', resp.response, resp.provider + '/' + resp.model);

    } catch (err) {
      appendMessage('assistant', `Error: ${err.message}`);
      Utils.showToast(err.message, 'danger');
    } finally {
      showTyping(false);
      _sending = false;
      if (sendBtn) sendBtn.disabled = false;
    }
  }

  /**
   * Append a message bubble to the chat.
   */
  function appendMessage(role, text, meta = '') {
    const container = document.getElementById('chatMessages');
    if (!container) return;

    // Remove empty state
    const empty = container.querySelector('.chat-empty');
    if (empty) empty.remove();

    const div = document.createElement('div');
    div.className = `message message--${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'message__bubble';
    bubble.innerHTML = role === 'assistant' ? Utils.renderMarkdown(text) : Utils.escapeHtml(text);
    div.appendChild(bubble);

    if (meta) {
      const metaEl = document.createElement('div');
      metaEl.className = 'message__meta';
      metaEl.textContent = meta;
      div.appendChild(metaEl);
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }

  /**
   * Append a tool call card.
   */
  function appendToolCall(tc) {
    const container = document.getElementById('chatMessages');
    if (!container) return;

    const card = document.createElement('div');
    card.className = 'tool-call';

    const statusBadge = tc.permitted
      ? '<span class="badge badge--success">OK</span>'
      : '<span class="badge badge--danger">DENIED</span>';

    card.innerHTML = `
      <div class="tool-call__header">
        <span class="tool-call__arrow">\u25B6</span>
        <span class="tool-call__name">${Utils.escapeHtml(tc.tool_name)}</span>
        ${statusBadge}
      </div>
      <div class="tool-call__body">
        <div style="margin-bottom: var(--sp-2); color: var(--text-muted);">Params:</div>
        <pre class="tool-call__json">${Utils.escapeHtml(JSON.stringify(tc.params, null, 2))}</pre>
        <div style="margin: var(--sp-2) 0; color: var(--text-muted);">Result:</div>
        <pre class="tool-call__json">${Utils.escapeHtml(JSON.stringify(tc.result, null, 2))}</pre>
      </div>
    `;

    // Toggle expand/collapse
    const header = card.querySelector('.tool-call__header');
    const body = card.querySelector('.tool-call__body');
    const arrow = card.querySelector('.tool-call__arrow');
    header.addEventListener('click', () => {
      body.classList.toggle('tool-call__body--open');
      arrow.classList.toggle('tool-call__arrow--open');
    });

    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
  }

  /**
   * Show/hide typing indicator.
   */
  function showTyping(show) {
    const container = document.getElementById('chatMessages');
    if (!container) return;

    let typing = container.querySelector('.typing');
    if (show && !typing) {
      typing = document.createElement('div');
      typing.className = 'typing';
      typing.innerHTML = '<div class="typing__dot"></div><div class="typing__dot"></div><div class="typing__dot"></div>';
      container.appendChild(typing);
      container.scrollTop = container.scrollHeight;
    } else if (!show && typing) {
      typing.remove();
    }
  }

  /**
   * Track a session in the sidebar.
   */
  function trackSession(sessionId, firstMessage) {
    const existing = sessions.find(s => s.id === sessionId);
    if (!existing) {
      sessions.unshift({ id: sessionId, preview: Utils.truncate(firstMessage, 30) });
      renderSessions();
    }
  }

  /**
   * Render the session list in the sidebar.
   */
  function renderSessions() {
    const list = document.getElementById('sessionList');
    if (!list) return;

    list.innerHTML = '';
    sessions.forEach(s => {
      const item = document.createElement('div');
      item.className = `session-item ${s.id === currentSessionId ? 'session-item--active' : ''}`;
      item.textContent = s.preview || s.id.slice(0, 8);
      item.addEventListener('click', () => loadSession(s.id));
      list.appendChild(item);
    });
  }

  /**
   * Load a previous session's history.
   */
  async function loadSession(sessionId) {
    currentSessionId = sessionId;
    renderSessions();

    const container = document.getElementById('chatMessages');
    if (!container) return;
    container.innerHTML = '<span style="color: var(--text-muted); padding: var(--sp-4);">Loading history...</span>';

    try {
      const history = await ApiClient.get(`/api/chat/history/${sessionId}`);
      container.innerHTML = '';

      // API returns a plain array (not {messages: [...]})
      if (Array.isArray(history) && history.length) {
        history.forEach(msg => {
          let content = msg.content;
          // Handle structured content blocks (Anthropic format)
          if (Array.isArray(content)) {
            content = content.filter(b => b.type === 'text').map(b => b.text).join('');
          }
          appendMessage(msg.role, content);
        });
      }
    } catch {
      container.innerHTML = '';
      appendMessage('assistant', 'Could not load session history.');
    }
  }

  /**
   * Start a new chat session.
   */
  function newChat() {
    currentSessionId = null;
    const container = document.getElementById('chatMessages');
    if (container) {
      const chips = getCurrentChips();
      const chipsHtml = chips.map(p =>
        `<button class="chat-chip" data-prompt="${Utils.escapeHtml(p)}">${Utils.escapeHtml(p)}</button>`
      ).join('');
      container.innerHTML = `
        <div class="chat-empty">
          <div class="chat-empty__icon">&#9001;/&#9002;</div>
          <span>Send a message to begin</span>
          <div class="chat-chips">${chipsHtml}</div>
        </div>
      `;
      // Re-wire chips
      wireChips();
    }
    renderSessions();
  }

  /**
   * Switch LLM provider.
   */
  async function switchProvider(provider) {
    try {
      const body = { provider };
      const modelSelect = document.getElementById('modelSelect');
      const apiKeyInput = document.getElementById('apiKeyInput');

      if (modelSelect?.value) body.model = modelSelect.value;
      if (apiKeyInput?.value && provider === 'anthropic') {
        body.api_key = apiKeyInput.value;
        _userApiKey = true;  // User provided their own key — unlock all models
      }

      await ApiClient.post('/api/provider/switch', body);
      Utils.showToast(`Switched to ${provider}`, 'success');
      refreshProviderStatus();
    } catch (err) {
      Utils.showToast(err.message, 'danger');
    }
  }

  /**
   * Update model dropdown options based on current provider.
   * Anthropic with env key = haiku only. User's own key = all models.
   */
  function updateModelOptions(provider) {
    const select = document.getElementById('modelSelect');
    if (!select) return;
    let models;
    if (provider === 'anthropic') {
      models = _userApiKey ? ANTHROPIC_MODELS_FULL : ANTHROPIC_MODELS_LIMITED;
    } else {
      models = _ollamaModels;
    }
    select.innerHTML = '';
    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m;
      // Friendly display names
      opt.textContent = m.replace('claude-haiku-4-5-20251001', 'Haiku 4.5')
                         .replace('claude-sonnet-4-20250514', 'Sonnet 4')
                         .replace('claude-opus-4-20250514', 'Opus 4');
      select.appendChild(opt);
    });
  }

  /**
   * Update provider button states based on availability.
   */
  function updateProviderButtons(status) {
    const btnOllama = document.getElementById('btnOllama');
    const btnAnthropic = document.getElementById('btnAnthropic');

    if (btnOllama) {
      btnOllama.disabled = !status.ollama_available;
      btnOllama.title = status.ollama_available
        ? 'Switch to local Ollama'
        : 'Ollama not detected — install and start Ollama locally';
    }

    if (btnAnthropic) {
      btnAnthropic.disabled = !status.anthropic_key_set;
      btnAnthropic.title = status.anthropic_key_set
        ? 'Switch to Anthropic Claude'
        : 'No API key — paste your key below to enable';
    }
  }

  /**
   * Wire prompt chip buttons to send messages.
   */
  function wireChips() {
    document.querySelectorAll('.chat-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const prompt = chip.dataset.prompt;
        if (!prompt) return;
        const textarea = document.getElementById('chatInput');
        if (textarea) {
          textarea.value = prompt;
        }
        sendMessage();
      });
    });
  }

  /**
   * Refresh provider status display.
   */
  async function refreshProviderStatus() {
    try {
      const status = await ApiClient.get('/api/provider/status');
      const nameEl = document.getElementById('providerName');
      const dotEl = document.getElementById('providerDot');
      const apiKeyInput = document.getElementById('apiKeyInput');

      // Track state from backend
      _userApiKey = status.user_api_key || false;
      _ollamaAvailable = status.ollama_available || false;

      // Display current provider + friendly model name
      const friendlyModel = status.model
        .replace('claude-haiku-4-5-20251001', 'Haiku 4.5')
        .replace('claude-sonnet-4-20250514', 'Sonnet 4')
        .replace('claude-opus-4-20250514', 'Opus 4');
      if (nameEl) nameEl.textContent = `${status.provider}/${friendlyModel}`;
      if (dotEl) {
        dotEl.classList.remove('health-dot--ok', 'health-dot--error');
        dotEl.classList.add(status.available ? 'health-dot--ok' : 'health-dot--error');
      }

      // API key input: always editable so users can paste their own key
      if (apiKeyInput) {
        apiKeyInput.disabled = false;
        if (status.user_api_key) {
          apiKeyInput.placeholder = 'Custom API key active (all models)';
        } else if (status.anthropic_key_set) {
          apiKeyInput.placeholder = 'Default key active (Haiku only) — paste your own for all models';
        } else {
          apiKeyInput.placeholder = 'sk-ant-... (paste to enable Anthropic)';
        }
      }

      // Update button states
      updateProviderButtons(status);

      // Auto-switch to Anthropic if key is pre-configured and Ollama is unavailable
      if (status.anthropic_key_set && !status.available && status.provider === 'ollama' && !status.ollama_available) {
        switchProvider('anthropic');
        return;
      }

      // Fetch dynamic Ollama model list
      if (status.ollama_available) {
        try {
          const models = await ApiClient.get('/api/chat/models');
          if (Array.isArray(models) && models.length) _ollamaModels = models;
        } catch { /* models endpoint unavailable */ }
      }

      // Update model dropdown to match current provider
      updateModelOptions(status.provider);
      const modelSelect = document.getElementById('modelSelect');
      if (modelSelect && status.model) {
        modelSelect.value = status.model;
      }
    } catch {
      // Provider endpoint not available (LLM deps missing)
      const nameEl = document.getElementById('providerName');
      if (nameEl) nameEl.textContent = 'unavailable';
    }
  }

  // ── Context helpers ──────────────────────────────────────────

  /**
   * Refresh prompt chips to match the active tab.
   */
  function refreshChipsForTab() {
    const container = document.getElementById('chatMessages');
    if (!container) return;
    const emptyState = container.querySelector('.chat-empty');
    if (!emptyState) return;
    const chipsContainer = emptyState.querySelector('.chat-chips');
    if (!chipsContainer) return;
    const chips = getCurrentChips();
    chipsContainer.innerHTML = chips.map(p =>
      `<button class="chat-chip" data-prompt="${Utils.escapeHtml(p)}">${Utils.escapeHtml(p)}</button>`
    ).join('');
    wireChips();
  }

  /**
   * Update the context badge showing what the user is looking at.
   */
  function updateContextBadge() {
    const badge = document.getElementById('chatContextBadge');
    if (!badge) return;
    const parts = [];
    if (_currentContext.tab && _currentContext.tab !== 'chat') {
      parts.push(_currentContext.tab);
    }
    if (_currentContext.selection?.id) {
      parts.push(_currentContext.selection.id);
    }
    badge.textContent = parts.length ? parts.join(' \u203A ') : '';
  }

  /**
   * Set chat context from external modules (e.g., "Ask about this" links).
   */
  function setContext(tab, selection) {
    _currentContext.tab = tab;
    _currentContext.selection = selection;
    refreshChipsForTab();
    updateContextBadge();
  }

  /**
   * Pre-fill the chat textarea and focus it. Used by "Ask about this" links.
   */
  function prefillAndFocus(message) {
    const textarea = document.getElementById('chatInput');
    if (textarea) {
      textarea.value = message;
      textarea.focus();
    }
  }

  return { init, setContext, prefillAndFocus };
})();

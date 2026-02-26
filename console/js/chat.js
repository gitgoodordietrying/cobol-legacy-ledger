/**
 * chat.js -- Chatbot UI with provider switching and session management.
 *
 * Sends messages to POST /api/chat, renders assistant responses with basic
 * markdown, shows tool call cards (collapsible), manages sessions, and
 * handles provider switching between Ollama and Anthropic.
 */

const Chat = (() => {

  let currentSessionId = null;
  const sessions = [];  // { id, preview }

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

    // New chat
    document.getElementById('btnNewChat')?.addEventListener('click', newChat);

    // Load provider status
    refreshProviderStatus();

    // Sync role display
    document.getElementById('roleSelect')?.addEventListener('change', () => {
      const role = document.getElementById('roleSelect').value;
      const chatRole = document.getElementById('chatRole');
      if (chatRole) chatRole.textContent = role;
    });
  }

  /**
   * Send the current message.
   */
  async function sendMessage() {
    const textarea = document.getElementById('chatInput');
    const message = textarea?.value?.trim();
    if (!message) return;

    // Clear input
    textarea.value = '';
    textarea.style.height = 'auto';

    // Show user message
    appendMessage('user', message);

    // Show typing indicator
    showTyping(true);

    try {
      const body = { message };
      if (currentSessionId) body.session_id = currentSessionId;

      const resp = await ApiClient.post('/api/chat', body);

      showTyping(false);

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
      showTyping(false);
      appendMessage('assistant', `Error: ${err.message}`);
      Utils.showToast(err.message, 'danger');
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

      if (history.messages) {
        history.messages.forEach(msg => {
          appendMessage(msg.role, msg.content);
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
      container.innerHTML = `
        <div class="chat-empty">
          <div class="chat-empty__icon">&#9001;/&#9002;</div>
          <span>Send a message to begin</span>
          <span style="font-size: var(--text-xs); color: var(--text-muted);">
            Try: "List all accounts in BANK_A" or "What is a nostro account?"
          </span>
        </div>
      `;
    }
    renderSessions();
  }

  /**
   * Switch LLM provider.
   */
  async function switchProvider(provider) {
    try {
      await ApiClient.post('/api/provider/switch', { provider });
      Utils.showToast(`Switched to ${provider}`, 'success');
      refreshProviderStatus();
    } catch (err) {
      Utils.showToast(err.message, 'danger');
    }
  }

  /**
   * Refresh provider status display.
   */
  async function refreshProviderStatus() {
    try {
      const status = await ApiClient.get('/api/provider/status');
      const nameEl = document.getElementById('providerName');
      const dotEl = document.getElementById('providerDot');
      if (nameEl) nameEl.textContent = `${status.provider}/${status.model}`;
      if (dotEl) {
        dotEl.classList.remove('health-dot--ok', 'health-dot--error');
        dotEl.classList.add(status.available ? 'health-dot--ok' : 'health-dot--error');
      }
    } catch {
      // Provider endpoint not available (LLM deps missing)
      const nameEl = document.getElementById('providerName');
      if (nameEl) nameEl.textContent = 'unavailable';
    }
  }

  return { init };
})();

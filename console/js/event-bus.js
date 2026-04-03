/**
 * event-bus.js -- Lightweight pub/sub EventBus for cross-module communication.
 *
 * Foundation for WS3 context-aware chat, WS4 analysis overhaul, and WS5
 * COBOL mainframe dashboard. All UI modules communicate through events
 * instead of direct function calls.
 *
 * Events:
 *   tab.changed         { tab: 'dashboard' | 'analysis' | 'chat' | 'mainframe' }
 *   selection.changed   { type: 'file' | 'paragraph' | 'node' | null, id: string, context: object }
 *   chat.context.update { tab: string, selection: object, prompts: string[] }
 */
const EventBus = (() => {
  const _listeners = {};

  function on(event, fn) {
    (_listeners[event] ||= []).push(fn);
  }

  function off(event, fn) {
    const list = _listeners[event];
    if (list) _listeners[event] = list.filter(f => f !== fn);
  }

  function emit(event, payload) {
    (_listeners[event] || []).forEach(fn => fn(payload));
  }

  function once(event, fn) {
    const wrapper = (payload) => { off(event, wrapper); fn(payload); };
    on(event, wrapper);
  }

  return { on, off, emit, once };
})();

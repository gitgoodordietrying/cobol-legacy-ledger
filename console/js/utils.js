/**
 * utils.js -- Shared helper functions for the COBOL Legacy Ledger console.
 *
 * Pure utility functions with no DOM dependencies or side effects.
 * Used across all JS modules for formatting, escaping, and toasts.
 */

const Utils = (() => {

  /**
   * Format a number as USD currency string.
   * @param {number} amount
   * @returns {string} e.g., "$1,234.56"
   */
  function formatCurrency(amount) {
    if (amount == null || isNaN(amount)) return '$0.00';
    if (Math.abs(amount) >= 1_000_000) {
      return '$' + (amount / 1_000_000).toFixed(2) + 'M';
    }
    if (Math.abs(amount) >= 10_000) {
      return '$' + (amount / 1_000).toFixed(1) + 'K';
    }
    return '$' + amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  /**
   * Escape HTML special characters to prevent XSS.
   * @param {string} str
   * @returns {string}
   */
  function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /**
   * Basic markdown to HTML (bold, inline code, newlines).
   * @param {string} text
   * @returns {string}
   */
  function renderMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);
    // Bold: **text**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Inline code: `code`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Newlines
    html = html.replace(/\n/g, '<br>');
    return html;
  }

  /**
   * Show a toast notification.
   * @param {string} message
   * @param {'success'|'danger'|'warning'|'info'} type
   * @param {number} duration - ms before auto-dismiss
   */
  function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('toast--exit');
      setTimeout(() => toast.remove(), 200);
    }, duration);
  }

  /**
   * Get the CSS color variable for a bank/node name.
   * @param {string} node - e.g., "BANK_A", "CLEARING"
   * @returns {string} CSS variable reference
   */
  function bankColor(node) {
    const map = {
      BANK_A: 'var(--bank-a)', BANK_B: 'var(--bank-b)',
      BANK_C: 'var(--bank-c)', BANK_D: 'var(--bank-d)',
      BANK_E: 'var(--bank-e)', CLEARING: 'var(--clearing)',
    };
    return map[node] || 'var(--text-muted)';
  }

  /**
   * Get the raw hex color for a bank (for SVG).
   * @param {string} node
   * @returns {string}
   */
  function bankColorHex(node) {
    const map = {
      BANK_A: '#3b82f6', BANK_B: '#22c55e',
      BANK_C: '#f59e0b', BANK_D: '#8b5cf6',
      BANK_E: '#ec4899', CLEARING: '#a78bfa',
    };
    return map[node] || '#64748b';
  }

  /**
   * Truncate a string with ellipsis.
   */
  function truncate(str, len = 40) {
    if (!str || str.length <= len) return str || '';
    return str.slice(0, len - 1) + '\u2026';
  }

  return { formatCurrency, escapeHtml, renderMarkdown, showToast, bankColor, bankColorHex, truncate };
})();

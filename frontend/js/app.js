/**
 * app.js — form submission, message rendering, image modal
 */

(function () {
  const form     = document.getElementById('chat-form');
  const input    = document.getElementById('user-input');
  const sendBtn  = document.getElementById('send-btn');
  const messages = document.getElementById('messages');
  const modal    = document.getElementById('modal-overlay');
  const modalImg = document.getElementById('modal-img');
  const closeBtn = document.getElementById('modal-close');

  let sessionId = null;

  // ── Scroll to bottom ────────────────────────────────────────────────────
  function scrollBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  // ── Create a message container ──────────────────────────────────────────
  function createMessage(role) {
    const wrapper = document.createElement('div');
    wrapper.className = `message ${role}`;
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    wrapper.appendChild(bubble);
    messages.appendChild(wrapper);
    scrollBottom();
    return bubble;
  }

  // ── Append a user message ───────────────────────────────────────────────
  function appendUserMessage(text) {
    const bubble = createMessage('user');
    const p = document.createElement('p');
    p.textContent = text;
    bubble.appendChild(p);
    scrollBottom();
  }

  // ── Typing indicator ────────────────────────────────────────────────────
  function showTyping() {
    const bubble = createMessage('assistant');
    bubble.id = 'typing-bubble';
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    for (let i = 0; i < 3; i++) {
      indicator.appendChild(document.createElement('span'));
    }
    bubble.appendChild(indicator);
    scrollBottom();
    return bubble;
  }
  function removeTyping() {
    const el = document.getElementById('typing-bubble');
    if (el) el.closest('.message').remove();
  }

  // ── Simple markdown-lite renderer ───────────────────────────────────────
  // Handles **bold**, `code`, and newlines → <br>
  function renderMarkdown(text) {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  // ── Build a tool-notice element ─────────────────────────────────────────
  function toolNotice(html) {
    const el = document.createElement('div');
    el.className = 'tool-notice';
    el.innerHTML = html;
    return el;
  }

  // ── Format tool input for display ───────────────────────────────────────
  function formatInput(input) {
    if (!input || Object.keys(input).length === 0) return '(no params)';
    return Object.entries(input)
      .map(([k, v]) => `<strong>${k}</strong>: ${JSON.stringify(v)}`)
      .join(', ');
  }

  // ── Render result cards from a tool result ───────────────────────────────
  function renderResultCards(name, result, bubble) {
    if (!result) return;

    if (name === 'search_covers' && result.covers && result.covers.length) {
      FDCStream.renderCovers(result.covers, bubble);
    } else if (name === 'search_issues' && result.issues && result.issues.length) {
      FDCStream.renderIssues(result.issues, bubble);
    } else if (name === 'cover_details' && result.cover) {
      FDCStream.renderCovers([result.cover], bubble);
    } else if (name === 'get_issue_with_covers') {
      if (result.issue) FDCStream.renderIssues([result.issue], bubble);
      if (result.covers && result.covers.length) FDCStream.renderCovers(result.covers, bubble);
    }
  }

  // ── Main submit handler ─────────────────────────────────────────────────
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    sendBtn.disabled = true;
    appendUserMessage(message);

    let assistantBubble = null;
    let textBuffer = '';
    const typingBubble = showTyping();

    try {
      await FDCStream.startChat(message, sessionId, {

        onSession(sid) {
          sessionId = sid;
        },

        onText(text) {
          removeTyping();
          if (!assistantBubble) {
            assistantBubble = createMessage('assistant');
          }
          textBuffer += text;
          // Render accumulated text as one paragraph
          let textEl = assistantBubble.querySelector('.assistant-text');
          if (!textEl) {
            textEl = document.createElement('p');
            textEl.className = 'assistant-text';
            assistantBubble.insertBefore(textEl, assistantBubble.firstChild);
          }
          textEl.innerHTML = renderMarkdown(textBuffer);
          scrollBottom();
        },

        onToolCall(name, input) {
          removeTyping();
          if (!assistantBubble) {
            assistantBubble = createMessage('assistant');
          }
          const notice = toolNotice(
            `🔍 Searching: <strong>${name}</strong> — ${formatInput(input)}`
          );
          assistantBubble.appendChild(notice);
          scrollBottom();
        },

        onToolResult(name, result) {
          if (!assistantBubble) {
            assistantBubble = createMessage('assistant');
          }

          // Show count notice for search results
          if (result && result.count !== undefined) {
            const notice = toolNotice(
              `✅ Found <strong>${result.count}</strong> result${result.count !== 1 ? 's' : ''}`
            );
            assistantBubble.appendChild(notice);
          } else if (result && result.error) {
            const notice = toolNotice(`⚠️ ${result.error}`);
            assistantBubble.appendChild(notice);
          }

          renderResultCards(name, result, assistantBubble);
          scrollBottom();
        },

        onEnd() {
          removeTyping();
          sendBtn.disabled = false;
          input.focus();
          scrollBottom();
        },

        onError(msg) {
          removeTyping();
          if (!assistantBubble) {
            assistantBubble = createMessage('assistant');
          }
          const errEl = document.createElement('p');
          errEl.style.color = '#f87171';
          errEl.textContent = `Error: ${msg}`;
          assistantBubble.appendChild(errEl);
          sendBtn.disabled = false;
          scrollBottom();
        },
      });
    } catch (err) {
      removeTyping();
      const bubble = createMessage('assistant');
      const p = document.createElement('p');
      p.style.color = '#f87171';
      p.textContent = `Connection error: ${err.message}`;
      bubble.appendChild(p);
      sendBtn.disabled = false;
      scrollBottom();
    }
  });

  // ── Enter key submits (Shift+Enter = newline not applicable in input) ───
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event('submit', { cancelable: true }));
    }
  });

  // ── Modal lightbox controls ─────────────────────────────────────────────
  closeBtn.addEventListener('click', () => {
    modal.hidden = true;
    modalImg.src = '';
  });

  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.hidden = true;
      modalImg.src = '';
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.hidden) {
      modal.hidden = true;
      modalImg.src = '';
    }
  });

})();

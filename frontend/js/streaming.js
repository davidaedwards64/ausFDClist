/**
 * streaming.js — SSE consumer and result card renderer
 *
 * Exports (onto window):
 *   FDCStream.startChat(message, sessionId, callbacks)
 *   FDCStream.renderCovers(covers, container)
 *   FDCStream.renderIssues(issues, container)
 *   FDCStream.sourceBadgeClass(source)
 */

window.FDCStream = (() => {
  const PHP_BASE = 'https://davidaedwards.com/ausfdclist';

  // ── Image URL helpers ────────────────────────────────────────────────────
  // Cover images are stored in year-based subdirectories: images/{year}/{filename}
  function coverImgUrl(filename, coverId) {
    if (!filename) return null;
    const year = coverId ? coverId.substring(0, 4) : '';
    return year
      ? `${PHP_BASE}/images/${year}/${filename}`
      : `${PHP_BASE}/images/${filename}`;
  }
  function stampImgUrl(filename) {
    if (!filename) return null;
    const year = filename.substring(0, 4);
    return `${PHP_BASE}/images/${year}/${filename}`;
  }

  // ── Source code → badge CSS class ───────────────────────────────────────
  // Source column stores a single letter (A, T, W, etc.)
  function sourceBadgeClass(source) {
    if (!source) return 'badge-src-O';
    return `badge-src-${source.toUpperCase()}`;
  }

  // Source code → human-readable name
  const SOURCE_NAMES = {
    A: 'Australia Post', C: 'Collector (AP)', G: 'PMG Shield', Z: 'PMG Hermes',
    S: 'Special Issue',  T: 'Challis',        E: 'Excelsior',  U: 'Guthrie',
    H: 'Haslems',        J: 'John Gower',     M: 'Mappin & Curran', L: 'Miller Bros',
    Y: 'S Mitchell',     P: 'Parade/ACCA',    Q: 'Qld Stamp Mart',  R: 'Royal',
    B: 'Bodin/SCP',      W: 'Wesley',         I: 'Wide World',  X: 'Pharmaceutical',
    O: 'Other',
  };
  function sourceName(code) {
    return SOURCE_NAMES[code] || code || 'Unknown';
  }

  // ── Cover card HTML ──────────────────────────────────────────────────────
  function buildCoverCard(cover) {
    const card = document.createElement('div');
    card.className = 'cover-card';

    // Images
    const pics = [cover.Pic1, cover.Pic2, cover.Pic3, cover.Pic4].filter(Boolean);
    if (pics.length) {
      const imgContainer = document.createElement('div');
      imgContainer.className = 'card-images';
      pics.forEach(pic => {
        const img = document.createElement('img');
        img.src = coverImgUrl(pic, cover.CoverId);
        img.alt = cover.Title || 'FDC image';
        img.loading = 'lazy';
        img.addEventListener('click', () => openModal(img.src));
        imgContainer.appendChild(img);
      });
      card.appendChild(imgContainer);
    }

    // Body
    const body = document.createElement('div');
    body.className = 'card-body';

    const title = document.createElement('div');
    title.className = 'card-title';
    title.textContent = cover.Title || '(untitled)';
    body.appendChild(title);

    const idEl = document.createElement('div');
    idEl.className = 'card-id';
    idEl.textContent = cover.CoverId;
    body.appendChild(idEl);

    const meta = document.createElement('div');
    meta.className = 'card-meta';

    if (cover.Date) {
      const year = cover.Date.substring(0, 4);
      const yearEl = document.createElement('span');
      yearEl.className = 'card-year';
      yearEl.textContent = year;
      yearEl.style.color = 'var(--muted)';
      meta.appendChild(yearEl);
    }

    if (cover.Source) {
      const badge = document.createElement('span');
      badge.className = `badge ${sourceBadgeClass(cover.Source)}`;
      badge.title = cover.Source;               // show code on hover
      badge.textContent = sourceName(cover.Source);
      meta.appendChild(badge);
    }

    if (cover.Type && cover.Type.toLowerCase() !== 'fdc') {
      const typeBadge = document.createElement('span');
      typeBadge.style.cssText = 'font-size:.72rem;color:var(--muted);';
      typeBadge.textContent = cover.Type;
      meta.appendChild(typeBadge);
    }

    body.appendChild(meta);

    // Parent issue info
    if (cover.IssueTitle) {
      const issueInfo = document.createElement('div');
      issueInfo.style.cssText = 'font-size:.75rem;color:var(--muted);margin-top:5px;';
      issueInfo.textContent = `Issue: ${cover.IssueTitle}`;
      body.appendChild(issueInfo);
    }

    // Stamp pic from parent issue
    if (cover.StampPic) {
      const stampImg = document.createElement('img');
      stampImg.src = stampImgUrl(cover.StampPic);
      stampImg.alt = 'Stamps';
      stampImg.className = 'card-stamp-pic';
      stampImg.loading = 'lazy';
      stampImg.addEventListener('click', () => openModal(stampImg.src));
      body.appendChild(stampImg);
    }

    card.appendChild(body);
    return card;
  }

  // ── Issue card HTML ──────────────────────────────────────────────────────
  function buildIssueCard(issue) {
    const card = document.createElement('div');
    card.className = 'issue-card';

    const title = document.createElement('div');
    title.className = 'card-title';
    title.textContent = issue.Title || '(untitled)';
    card.appendChild(title);

    const idEl = document.createElement('div');
    idEl.className = 'card-id';
    idEl.textContent = issue.IssueId;
    card.appendChild(idEl);

    if (issue.Series) {
      const series = document.createElement('div');
      series.className = 'card-series';
      series.textContent = `Series: ${issue.Series}`;
      card.appendChild(series);
    }

    if (issue.Date) {
      const dateEl = document.createElement('div');
      dateEl.style.cssText = 'font-size:.75rem;color:var(--muted);margin:3px 0;';
      dateEl.textContent = issue.Date;
      card.appendChild(dateEl);
    }

    if (issue.Stamps) {
      const stamps = document.createElement('div');
      stamps.className = 'card-stamps';
      stamps.textContent = `Stamps: ${issue.Stamps}`;
      card.appendChild(stamps);
    }

    if (issue.StampPic) {
      const img = document.createElement('img');
      img.src = stampImgUrl(issue.StampPic);
      img.alt = 'Stamps';
      img.className = 'card-stamp-pic';
      img.loading = 'lazy';
      img.addEventListener('click', () => openModal(img.src));
      card.appendChild(img);
    }

    return card;
  }

  // ── Public render helpers ────────────────────────────────────────────────
  function renderCovers(covers, container) {
    if (!covers || covers.length === 0) return;
    const grid = document.createElement('div');
    grid.className = 'results-grid';
    covers.forEach(c => grid.appendChild(buildCoverCard(c)));
    container.appendChild(grid);
  }

  function renderIssues(issues, container) {
    if (!issues || issues.length === 0) return;
    const grid = document.createElement('div');
    grid.className = 'results-grid';
    issues.forEach(i => grid.appendChild(buildIssueCard(i)));
    container.appendChild(grid);
  }

  // ── Modal lightbox ───────────────────────────────────────────────────────
  function openModal(src) {
    const overlay = document.getElementById('modal-overlay');
    const img = document.getElementById('modal-img');
    img.src = src;
    overlay.hidden = false;
  }

  // ── SSE chat stream ──────────────────────────────────────────────────────
  /**
   * startChat(message, sessionId, callbacks)
   *
   * callbacks: {
   *   onSession(sessionId)          — called once with server session ID
   *   onText(text)                  — called with text chunk from assistant
   *   onToolCall(name, input)       — called when agent invokes a tool
   *   onToolResult(name, result)    — called when tool returns data
   *   onEnd()                       — called when stream ends
   *   onError(message)              — called on error
   * }
   */
  async function startChat(message, sessionId, callbacks) {
    const cb = callbacks || {};

    const idToken = window.Auth ? window.Auth.getIdToken() : null;
    const headers = { 'Content-Type': 'application/json' };
    if (idToken) headers['Authorization'] = `Bearer ${idToken}`;

    const response = await fetch('/api/chat', {
      method: 'POST',
      headers,
      body: JSON.stringify({ message, session_id: sessionId || null }),
    });

    if (!response.ok) {
      const err = await response.text();
      (cb.onError || console.error)(`HTTP ${response.status}: ${err}`);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete last line

      for (const line of lines) {
        if (!line.trim()) continue;

        // Strip SSE "data: " prefix
        const raw = line.startsWith('data: ') ? line.slice(6) : line;
        let event;
        try {
          event = JSON.parse(raw);
        } catch {
          continue;
        }

        switch (event.type) {
          case 'session':
            cb.onSession && cb.onSession(event.session_id);
            break;
          case 'text':
            cb.onText && cb.onText(event.text);
            break;
          case 'tool_call':
            cb.onToolCall && cb.onToolCall(event.name, event.input);
            break;
          case 'tool_result':
            cb.onToolResult && cb.onToolResult(event.name, event.result);
            break;
          case 'end':
            cb.onEnd && cb.onEnd();
            break;
          case 'error':
            cb.onError && cb.onError(event.message);
            break;
        }
      }
    }
  }

  return { startChat, renderCovers, renderIssues, sourceBadgeClass };
})();

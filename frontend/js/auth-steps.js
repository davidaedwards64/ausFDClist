/**
 * auth-steps.js — Auth steps panel showing Okta token exchange flow
 *
 * Exports: window.AuthSteps
 *   AuthSteps.showPanel()
 *   AuthSteps.updateStep1(user)
 *   AuthSteps.updateStep2(exchange)
 */
window.AuthSteps = (() => {
  let _panel = null;
  let _step1El = null;
  let _step2El = null;

  function showPanel() {
    if (_panel) return;

    const container = document.getElementById('auth-steps-container');
    if (!container) return;

    _panel = document.createElement('div');
    _panel.className = 'auth-steps-panel';
    _panel.innerHTML = `
      <div class="auth-steps-title">Okta Authentication Flow</div>
      <div class="auth-steps-flow">
        <div class="auth-step" id="auth-step-1">
          <div class="auth-step-icon auth-step-icon--pending">1</div>
          <div class="auth-step-body">
            <div class="auth-step-label">User Authentication</div>
            <div class="auth-step-detail auth-step-detail--pending">Waiting for sign-in…</div>
          </div>
        </div>
        <div class="auth-step-connector"></div>
        <div class="auth-step" id="auth-step-2">
          <div class="auth-step-icon auth-step-icon--pending">2</div>
          <div class="auth-step-body">
            <div class="auth-step-label">STS Token Exchange</div>
            <div class="auth-step-detail auth-step-detail--pending">Waiting for request…</div>
          </div>
        </div>
      </div>
    `;

    container.appendChild(_panel);
    _step1El = _panel.querySelector('#auth-step-1');
    _step2El = _panel.querySelector('#auth-step-2');
  }

  function _setStepStatus(stepEl, status, detailHtml) {
    const icon = stepEl.querySelector('.auth-step-icon');
    const detail = stepEl.querySelector('.auth-step-detail');

    icon.className = `auth-step-icon auth-step-icon--${status}`;
    detail.className = `auth-step-detail auth-step-detail--${status}`;
    detail.innerHTML = detailHtml;
  }

  function updateStep1(user) {
    if (!_step1El) showPanel();
    if (!_step1El) return;

    const email = (user && (user.email || user.name)) || 'authenticated user';
    _setStepStatus(
      _step1El,
      'success',
      `<span class="auth-badge auth-badge--info">id_token</span> obtained for <strong>${_esc(email)}</strong>`
    );
  }

  function updateStep2(exchange) {
    if (!_step2El) showPanel();
    if (!_step2El) return;

    if (!exchange || !exchange.success) {
      const status = exchange && exchange.status;
      if (status === 'not_configured') {
        _setStepStatus(
          _step2El,
          'warning',
          `<span class="auth-badge auth-badge--warning">NOT CONFIGURED</span> ` +
          `Set <code>OKTA_AGENT_CLIENT_ID</code> and <code>OKTA_AGENT_PRIVATE_JWK</code> to enable.`
        );
      } else {
        const msg = (exchange && exchange.error) || 'Unknown error';
        _setStepStatus(
          _step2El,
          'error',
          `<span class="auth-badge auth-badge--error">FAILED</span> ${_esc(msg)}`
        );
      }
      return;
    }

    const secret = exchange.vaulted_secret || {};
    const cachedBadge = exchange.cached
      ? `<span class="auth-badge auth-badge--gray">cached</span> `
      : '';
    const tokenType = exchange.issued_token_type
      ? `<span class="auth-badge auth-badge--info">${_esc(exchange.issued_token_type)}</span> `
      : '';
    const expiresIn = exchange.expires_in
      ? `expires in ${exchange.expires_in}s`
      : '';

    const maskedPw = secret.password
      ? _esc(secret.password.slice(0, 3)) + '••••••••'
      : '';
    const credRows = secret.username
      ? `<div class="auth-cred-row"><span class="auth-cred-key">username</span><code>${_esc(secret.username)}</code></div>` +
        `<div class="auth-cred-row"><span class="auth-cred-key">password</span><code>${maskedPw}</code></div>`
      : '';

    _setStepStatus(
      _step2El,
      'success',
      `<span class="auth-badge auth-badge--success">SUCCESS</span> ${cachedBadge}${tokenType}${_esc(expiresIn)}` +
      (credRows ? `<div class="auth-creds">${credRows}</div>` : '')
    );
  }

  function _esc(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  return { showPanel, updateStep1, updateStep2 };
})();

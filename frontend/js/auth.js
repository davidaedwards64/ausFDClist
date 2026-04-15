/**
 * auth.js — PKCE OIDC authentication module
 * Exposes window.Auth globally.
 */
window.Auth = (() => {
  const TOKEN_KEY    = 'okta_id_token';
  const USER_KEY     = 'okta_user';
  const VERIFIER_KEY = 'pkce_code_verifier';
  const STATE_KEY    = 'pkce_state';
  const CONFIG_KEY   = 'okta_config';

  // ── PKCE helpers ──────────────────────────────────────────────────────────
  function generateRandomString(length) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
    const arr = new Uint8Array(length);
    crypto.getRandomValues(arr);
    return Array.from(arr).map(b => chars[b % chars.length]).join('');
  }

  async function sha256(plain) {
    const encoder = new TextEncoder();
    const data = encoder.encode(plain);
    return crypto.subtle.digest('SHA-256', data);
  }

  function base64URLEncode(buffer) {
    return btoa(String.fromCharCode(...new Uint8Array(buffer)))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '');
  }

  // ── JWT decode (no signature verification — trust HTTPS delivery) ─────────
  function decodeJwt(token) {
    try {
      const payload = token.split('.')[1];
      return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
    } catch {
      return null;
    }
  }

  // ── Public API ────────────────────────────────────────────────────────────
  function getIdToken() {
    return sessionStorage.getItem(TOKEN_KEY);
  }

  function isAuthenticated() {
    const token = getIdToken();
    if (!token) return false;
    const payload = decodeJwt(token);
    if (!payload) return false;
    return payload.exp > Math.floor(Date.now() / 1000);
  }

  function getCurrentUser() {
    try {
      return JSON.parse(sessionStorage.getItem(USER_KEY));
    } catch {
      return null;
    }
  }

  function ensureAuthenticated() {
    if (!isAuthenticated()) {
      window.location.replace('/auth/signin');
    }
  }

  function logout() {
    sessionStorage.clear();
    window.location.replace('/auth/signin');
  }

  async function initiateLogin() {
    const configRes = await fetch('/api/config');
    if (!configRes.ok) throw new Error('Failed to fetch auth config');
    const config = await configRes.json();

    sessionStorage.setItem(CONFIG_KEY, JSON.stringify(config));

    const verifier = generateRandomString(64);
    const state    = generateRandomString(32);
    sessionStorage.setItem(VERIFIER_KEY, verifier);
    sessionStorage.setItem(STATE_KEY, state);

    const challenge = base64URLEncode(await sha256(verifier));

    const params = new URLSearchParams({
      client_id:             config.okta_client_id,
      response_type:         'code',
      scope:                 'openid email profile',
      redirect_uri:          config.okta_redirect_uri,
      state,
      code_challenge:        challenge,
      code_challenge_method: 'S256',
    });

    window.location.replace(`${config.okta_issuer}/v1/authorize?${params}`);
  }

  async function handleCallback() {
    const params = new URLSearchParams(window.location.search);
    const code  = params.get('code');
    const state = params.get('state');
    const error = params.get('error');

    if (error) {
      throw new Error(params.get('error_description') || error);
    }
    if (!code || !state) {
      throw new Error('Missing code or state in callback URL');
    }

    const savedState   = sessionStorage.getItem(STATE_KEY);
    const codeVerifier = sessionStorage.getItem(VERIFIER_KEY);

    if (state !== savedState) {
      throw new Error('State mismatch — possible CSRF attack');
    }

    const configJson = sessionStorage.getItem(CONFIG_KEY);
    if (!configJson) throw new Error('Auth config not found — please sign in again');
    const config = JSON.parse(configJson);

    const tokenRes = await fetch(`${config.okta_issuer}/v1/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type:    'authorization_code',
        client_id:     config.okta_client_id,
        redirect_uri:  config.okta_redirect_uri,
        code,
        code_verifier: codeVerifier,
      }),
    });

    if (!tokenRes.ok) {
      const err = await tokenRes.json().catch(() => ({}));
      throw new Error(err.error_description || `Token exchange failed (${tokenRes.status})`);
    }

    const tokens  = await tokenRes.json();
    const idToken = tokens.id_token;
    if (!idToken) throw new Error('No id_token in token response');

    const payload = decodeJwt(idToken);
    const user = {
      email: payload.email || '',
      name:  payload.name  || payload.preferred_username || payload.email || '',
      sub:   payload.sub   || '',
    };

    sessionStorage.removeItem(VERIFIER_KEY);
    sessionStorage.removeItem(STATE_KEY);
    sessionStorage.setItem(TOKEN_KEY, idToken);
    sessionStorage.setItem(USER_KEY, JSON.stringify(user));

    return user;
  }

  return {
    initiateLogin,
    handleCallback,
    getIdToken,
    isAuthenticated,
    getCurrentUser,
    logout,
    ensureAuthenticated,
  };
})();

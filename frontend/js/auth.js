/**
 * auth.js — BFF authentication module
 * The backend handles the full OIDC flow; this module queries /api/me.
 * Exposes window.Auth globally.
 */
window.Auth = (() => {
  let _user = null; // in-memory cache set by ensureAuthenticated()

  /**
   * Fetch /api/me. Redirects to sign-in if not authenticated.
   * Must be awaited before calling getCurrentUser().
   */
  async function ensureAuthenticated() {
    try {
      const res = await fetch('/api/me');
      if (!res.ok) {
        window.location.replace('/auth/signin');
        return;
      }
      _user = await res.json();
    } catch {
      window.location.replace('/auth/signin');
    }
  }

  function getCurrentUser() {
    return _user;
  }

  function logout() {
    window.location.replace('/auth/logout');
  }

  return { ensureAuthenticated, getCurrentUser, logout };
})();

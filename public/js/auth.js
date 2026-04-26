/**
 * auth.js — Keycloak authentication module
 *
 * Fetches Keycloak config from the backend, dynamically loads the Keycloak
 * JS adapter, and handles login/logout/token refresh for the SPA.
 *
 * Usage:
 *   import { initAuth, getToken, getUser, logout } from '/js/auth.js';
 *   await initAuth();   // call once at app boot — redirects to login if needed
 *   getToken();         // returns current access token string
 *   getUser();          // returns { name, email, sub }
 *   logout();           // ends session and redirects to Keycloak logout
 */

let _kc = null;

function _loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = resolve;
    s.onerror = () => reject(new Error(`Failed to load Keycloak adapter from ${src}`));
    document.head.appendChild(s);
  });
}

function _checkStorage() {
  try {
    const k = '__kc_storage_test__';
    sessionStorage.setItem(k, '1');
    sessionStorage.removeItem(k);
  } catch {
    // Edge "Tracking Prevention" can block sessionStorage for cross-origin scripts.
    // Surface a helpful hint rather than a cryptic crash.
    console.warn(
      '[auth] Storage blocked by browser Tracking Prevention.\n' +
      'In Edge: Settings → Privacy → Tracking prevention → Exceptions → add localhost\n' +
      'Or switch Tracking prevention to "Basic".'
    );
  }
}

export async function initAuth() {
  _checkStorage();

  const resp = await fetch('/api/auth/config');
  if (!resp.ok) throw new Error('Could not fetch auth config from backend');
  const config = await resp.json();

  await _loadScript(`${config.url}/js/keycloak.js`);

  _kc = new window.Keycloak({
    url: config.url,
    realm: config.realm,
    clientId: config.clientId,
  });

  await _kc.init({
    onLoad: 'check-sso',
    checkLoginIframe: false,
    pkceMethod: 'S256',
    enableLogging: false,
  });

  // Proactively refresh the token 60s before it expires, every 30s
  if (_kc.authenticated) {
    setInterval(() => {
      _kc.updateToken(60).catch(() => _kc.login());
    }, 30_000);
  }

  return _kc;
}

export function isAuthenticated() {
  return _kc?.authenticated ?? false;
}

export function getToken() {
  return _kc?.token ?? null;
}

export function getUser() {
  if (!_kc?.tokenParsed) return null;
  const p = _kc.tokenParsed;
  return {
    sub:   p.sub,
    name:  p.name || p.preferred_username || 'User',
    email: p.email || '',
  };
}

export function logout() {
  _kc?.logout({ redirectUri: window.location.origin });
}

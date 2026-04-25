/**
 * landing.js — handles login / register redirects via Keycloak.
 * Fetches the Keycloak config from the backend, then builds the
 * appropriate authorization or registration URL.
 */

const APP_REDIRECT = `${window.location.origin}/`;

async function getKeycloakConfig() {
  const resp = await fetch('/api/auth/config');
  if (!resp.ok) throw new Error('Could not reach auth config endpoint');
  return resp.json();
}

function buildLoginUrl(cfg) {
  const base = `${cfg.url}/realms/${cfg.realm}/protocol/openid-connect/auth`;
  const params = new URLSearchParams({
    client_id: cfg.clientId,
    redirect_uri: APP_REDIRECT,
    response_type: 'code',
    scope: 'openid',
  });
  return `${base}?${params}`;
}

function buildRegisterUrl(cfg) {
  const base = `${cfg.url}/realms/${cfg.realm}/protocol/openid-connect/registrations`;
  const params = new URLSearchParams({
    client_id: cfg.clientId,
    redirect_uri: APP_REDIRECT,
    response_type: 'code',
    scope: 'openid',
  });
  return `${base}?${params}`;
}

async function redirectToKeycloak(action) {
  try {
    const cfg = await getKeycloakConfig();
    const url = action === 'register' ? buildRegisterUrl(cfg) : buildLoginUrl(cfg);
    window.location.href = url;
  } catch {
    // Keycloak not reachable — fall through to SPA (initAuth will handle it)
    window.location.href = '/index.html';
  }
}

function bindButtons() {
  const loginIds = ['login-btn', 'login-mobile'];
  const registerIds = ['register-btn', 'register-mobile', 'cta-primary', 'cta-bottom'];

  loginIds.forEach(id => {
    document.getElementById(id)?.addEventListener('click', () => redirectToKeycloak('login'));
  });
  registerIds.forEach(id => {
    document.getElementById(id)?.addEventListener('click', () => redirectToKeycloak('register'));
  });
}

document.addEventListener('DOMContentLoaded', bindButtons);

/**
 * landing.js — handles login / register redirects via Keycloak.
 * Uses the Keycloak JS adapter with pkceMethod:'S256' but no onLoad,
 * so no SSO iframe or network requests happen at init time.
 */

const APP_REDIRECT = `${window.location.origin}/index.html`;

async function getKeycloakConfig() {
  const resp = await fetch('/api/auth/config');
  if (!resp.ok) throw new Error(`Auth config ${resp.status}`);
  const ct = resp.headers.get('content-type') ?? '';
  if (!ct.includes('json')) throw new Error('Auth config returned non-JSON');
  return resp.json();
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) { resolve(); return; }
    const s = document.createElement('script');
    s.src = src;
    s.onload = resolve;
    s.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(s);
  });
}

async function redirectToKeycloak(action) {
  try {
    const cfg = await getKeycloakConfig();
    await loadScript(`${cfg.url}/js/keycloak.js`);

    const kc = new window.Keycloak({ url: cfg.url, realm: cfg.realm, clientId: cfg.clientId });

    // No onLoad — skips the SSO iframe check entirely, makes no network requests.
    // pkceMethod ensures login/register URLs include code_challenge + verifier in sessionStorage.
    await kc.init({ pkceMethod: 'S256' });

    const opts = { redirectUri: APP_REDIRECT };
    if (action === 'register') {
      await kc.register(opts);
    } else {
      await kc.login(opts);
    }
  } catch (err) {
    console.warn('[landing] Keycloak redirect failed, falling back:', err);
    window.location.href = '/index.html';
  }
}

function bindButtons() {
  const loginIds = ['login-btn', 'login-mobile'];
  const registerIds = ['register-btn', 'register-mobile', 'register-mobile-nav', 'cta-primary', 'cta-bottom', 'register-pricing'];

  loginIds.forEach(id => {
    document.getElementById(id)?.addEventListener('click', () => redirectToKeycloak('login'));
  });
  registerIds.forEach(id => {
    document.getElementById(id)?.addEventListener('click', () => redirectToKeycloak('register'));
  });

  document.getElementById('waitlist-submit')?.addEventListener('click', () => {
    const email = document.getElementById('waitlist-email')?.value?.trim();
    if (!email) return;
    document.getElementById('waitlist-form').classList.add('hidden');
    document.getElementById('waitlist-thanks').classList.remove('hidden');
  });
}

document.addEventListener('DOMContentLoaded', bindButtons);

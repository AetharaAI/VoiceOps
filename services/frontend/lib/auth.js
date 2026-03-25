const TOKEN_KEY = 'voiceops_token';

function decodeJwtPayload(token) {
  try {
    const [, payload] = token.split('.');
    if (!payload) return null;
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    return JSON.parse(atob(padded));
  } catch (_err) {
    return null;
  }
}

export function getStoredToken() {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setStoredToken(token) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(TOKEN_KEY);
}

export function tokenExpiresAt(token) {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') return null;
  return payload.exp * 1000;
}

export function isTokenExpired(token) {
  if (!token) return true;
  const expiresAt = tokenExpiresAt(token);
  if (!expiresAt) return true;
  return Date.now() >= expiresAt;
}

export function hasValidToken() {
  const token = getStoredToken();
  return Boolean(token) && !isTokenExpired(token);
}

export function redirectToLogin() {
  if (typeof window === 'undefined') return;
  if (window.location.pathname === '/login') return;
  window.location.href = '/login';
}

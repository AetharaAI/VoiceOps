'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { clearStoredToken, getStoredToken, hasValidToken, redirectToLogin, tokenExpiresAt } from '../lib/auth';

const PUBLIC_PATHS = new Set(['/', '/login']);

export default function AuthGate() {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (PUBLIC_PATHS.has(pathname)) {
      return;
    }

    const token = getStoredToken();
    if (!token || !hasValidToken()) {
      clearStoredToken();
      router.replace('/login');
      return;
    }

    const expiresAt = tokenExpiresAt(token);
    if (!expiresAt) {
      clearStoredToken();
      router.replace('/login');
      return;
    }

    const timeoutMs = Math.max(0, expiresAt - Date.now());
    const timer = window.setTimeout(() => {
      clearStoredToken();
      redirectToLogin();
    }, timeoutMs);

    const handleFocus = () => {
      if (!hasValidToken()) {
        clearStoredToken();
        redirectToLogin();
      }
    };

    const handleStorage = (event) => {
      if (event.key === 'voiceops_token' && !event.newValue) {
        redirectToLogin();
      }
    };

    window.addEventListener('focus', handleFocus);
    window.addEventListener('storage', handleStorage);

    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('storage', handleStorage);
    };
  }, [pathname, router]);

  return null;
}

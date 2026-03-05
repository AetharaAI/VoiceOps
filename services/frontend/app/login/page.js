'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000/api/v1';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('owner@example.com');
  const [password, setPassword] = useState('ChangeMe123!');
  const [message, setMessage] = useState('');

  const [tenantName, setTenantName] = useState('Hello World Tenant');
  const [tenantSlug, setTenantSlug] = useState('hello-world');
  const [fullName, setFullName] = useState('Tenant Owner');
  const [platformKey, setPlatformKey] = useState('change-platform-key');

  async function login(e) {
    e.preventDefault();
    setMessage('Logging in...');
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      localStorage.setItem('voiceops_token', data.access_token);
      setMessage('Login successful.');
      router.push('/dashboard');
    } catch (error) {
      setMessage(`Login failed: ${error.message}`);
    }
  }

  async function bootstrap(e) {
    e.preventDefault();
    setMessage('Bootstrapping tenant...');
    try {
      const response = await fetch(`${API_BASE}/auth/bootstrap`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Platform-Admin-Key': platformKey
        },
        body: JSON.stringify({
          tenant_name: tenantName,
          tenant_slug: tenantSlug,
          email,
          full_name: fullName,
          password
        })
      });
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      localStorage.setItem('voiceops_token', data.access_token);
      setMessage('Bootstrap complete.');
      router.push('/dashboard');
    } catch (error) {
      setMessage(`Bootstrap failed: ${error.message}`);
    }
  }

  return (
    <main className="container grid-2">
      <section className="card">
        <h1>Login</h1>
        <form onSubmit={login}>
          <label>Email</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <button type="submit">Sign In</button>
        </form>
      </section>

      <section className="card">
        <h2>First Tenant Bootstrap</h2>
        <form onSubmit={bootstrap}>
          <label>Platform Admin Key</label>
          <input value={platformKey} onChange={(e) => setPlatformKey(e.target.value)} />
          <label>Tenant Name</label>
          <input value={tenantName} onChange={(e) => setTenantName(e.target.value)} />
          <label>Tenant Slug</label>
          <input value={tenantSlug} onChange={(e) => setTenantSlug(e.target.value)} />
          <label>Owner Name</label>
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
          <button className="secondary" type="submit">Bootstrap Tenant</button>
        </form>
      </section>

      <section className="card" style={{ gridColumn: '1 / -1' }}>
        <strong>Status:</strong> {message || 'Idle'}
      </section>
    </main>
  );
}

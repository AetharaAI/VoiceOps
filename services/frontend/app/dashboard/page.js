'use client';

import { useEffect, useState } from 'react';
import Nav from '../../components/nav';
import { api } from '../../lib/api';

export default function DashboardPage() {
  const [tenant, setTenant] = useState(null);
  const [phoneNumbers, setPhoneNumbers] = useState([]);
  const [businessHours, setBusinessHours] = useState([]);
  const [routingRules, setRoutingRules] = useState([]);
  const [form, setForm] = useState({ phone_number: '', provider: 'twilio', agent_id: '' });
  const [message, setMessage] = useState('');

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const [tenantData, pn, bh, rr] = await Promise.all([
        api('/tenants/me'),
        api('/phone-numbers'),
        api('/business-hours'),
        api('/routing-rules')
      ]);
      setTenant(tenantData);
      setPhoneNumbers(pn);
      setBusinessHours(bh);
      setRoutingRules(rr);
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function addPhoneNumber(e) {
    e.preventDefault();
    try {
      await api('/phone-numbers', {
        method: 'POST',
        body: JSON.stringify({
          phone_number: form.phone_number,
          provider: form.provider,
          agent_id: form.agent_id || null
        })
      });
      setForm({ phone_number: '', provider: 'twilio', agent_id: '' });
      await load();
      setMessage('Phone number saved.');
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <main className="container">
      <Nav />
      <h1>Tenant Dashboard</h1>
      <p>Phone numbers, business hours, and routing rules per tenant.</p>

      <div className="grid-2">
        <section className="card">
          <h2>Tenant</h2>
          {tenant ? (
            <pre>{JSON.stringify(tenant, null, 2)}</pre>
          ) : (
            <p>Load tenant details by logging in.</p>
          )}
        </section>

        <section className="card">
          <h2>Add Phone Number</h2>
          <form onSubmit={addPhoneNumber}>
            <label>Phone Number (E.164)</label>
            <input
              value={form.phone_number}
              onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
              placeholder="+15551234567"
            />
            <label>Provider</label>
            <input
              value={form.provider}
              onChange={(e) => setForm({ ...form, provider: e.target.value })}
            />
            <label>Default Agent ID</label>
            <input
              value={form.agent_id}
              onChange={(e) => setForm({ ...form, agent_id: e.target.value })}
            />
            <button type="submit">Save Number</button>
          </form>
        </section>
      </div>

      <section className="card">
        <h2>Configured Numbers</h2>
        <pre>{JSON.stringify(phoneNumbers, null, 2)}</pre>
      </section>

      <div className="grid-2">
        <section className="card">
          <h2>Business Hours</h2>
          <pre>{JSON.stringify(businessHours, null, 2)}</pre>
        </section>
        <section className="card">
          <h2>Routing Rules</h2>
          <pre>{JSON.stringify(routingRules, null, 2)}</pre>
        </section>
      </div>

      <section className="card">{message || 'Ready.'}</section>
    </main>
  );
}

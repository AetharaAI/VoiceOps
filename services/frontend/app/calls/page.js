'use client';

import { useEffect, useState } from 'react';
import Nav from '../../components/nav';
import { api } from '../../lib/api';

export default function CallsPage() {
  const [calls, setCalls] = useState([]);
  const [agents, setAgents] = useState([]);
  const [tenantId, setTenantId] = useState('');
  const [selectedCall, setSelectedCall] = useState(null);
  const [message, setMessage] = useState('');

  const [dialForm, setDialForm] = useState({ to_number: '+15551230099', agent_id: '', campaign_id: '' });

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const [tenant, callList, agentList] = await Promise.all([api('/tenants/me'), api('/calls'), api('/agents')]);
      setTenantId(tenant.id);
      setCalls(callList);
      setAgents(agentList);
      if (!dialForm.agent_id && agentList.length > 0) {
        setDialForm((prev) => ({ ...prev, agent_id: agentList[0].id }));
      }
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function triggerOutbound(e) {
    e.preventDefault();
    try {
      await api('/calls/outbound', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: tenantId,
          to_number: dialForm.to_number,
          agent_id: dialForm.agent_id,
          campaign_id: dialForm.campaign_id || null,
          context_payload: { source: 'manual_ui' }
        })
      });
      setMessage('Outbound call queued.');
      await load();
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function openCall(callId) {
    try {
      const data = await api(`/calls/${callId}`);
      setSelectedCall(data);
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <main className="container">
      <Nav />
      <h1>Calls</h1>
      <div className="grid-2">
        <section className="card">
          <h2>Trigger Outbound</h2>
          <form onSubmit={triggerOutbound}>
            <label>To Number</label>
            <input
              value={dialForm.to_number}
              onChange={(e) => setDialForm({ ...dialForm, to_number: e.target.value })}
            />
            <label>Agent</label>
            <select
              value={dialForm.agent_id}
              onChange={(e) => setDialForm({ ...dialForm, agent_id: e.target.value })}
            >
              {agents.map((agent) => (
                <option value={agent.id} key={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
            <label>Campaign ID</label>
            <input
              value={dialForm.campaign_id}
              onChange={(e) => setDialForm({ ...dialForm, campaign_id: e.target.value })}
            />
            <button type="submit">Dial</button>
          </form>
        </section>

        <section className="card">
          <h2>Call List</h2>
          {calls.map((call) => (
            <div key={call.id} className="card" style={{ marginBottom: 8 }}>
              <div>
                <strong>{call.direction}</strong> {call.from_number} → {call.to_number}
              </div>
              <div>Status: {call.status}</div>
              <button className="secondary" onClick={() => openCall(call.id)}>
                View Transcript
              </button>
            </div>
          ))}
        </section>
      </div>

      <section className="card">
        <h2>Selected Call Detail</h2>
        <pre>{JSON.stringify(selectedCall, null, 2)}</pre>
      </section>

      <section className="card">{message || 'Ready.'}</section>
    </main>
  );
}

'use client';

import { useEffect, useState } from 'react';
import Nav from '../../components/nav';
import { api } from '../../lib/api';

const seedRequiredFields = {
  name: { prompt: 'Can I have your full name?' },
  phone: { prompt: 'What is the best callback number?' },
  appointment_type: { prompt: 'What kind of appointment do you need?' }
};

export default function AgentsPage() {
  const [agents, setAgents] = useState([]);
  const [message, setMessage] = useState('');
  const [form, setForm] = useState({
    name: 'Sales Agent',
    persona: 'Helpful and concise revenue assistant',
    script: 'Qualify leads and book appointments.',
    required_fields: JSON.stringify(seedRequiredFields, null, 2),
    tools_config: JSON.stringify({ booking: true, crm_writeback: true, sms_follow_up: true }, null, 2),
    policy_config: JSON.stringify({ human_handoff_number: '+15550000000', business_hours_only: true }, null, 2),
    workflow_dsl: JSON.stringify({ post_call: [{ type: 'ticket' }] }, null, 2)
  });

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const data = await api('/agents');
      setAgents(data);
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function createAgent(e) {
    e.preventDefault();
    try {
      await api('/agents', {
        method: 'POST',
        body: JSON.stringify({
          name: form.name,
          persona: form.persona,
          script: form.script,
          required_fields: JSON.parse(form.required_fields),
          tools_config: JSON.parse(form.tools_config),
          policy_config: JSON.parse(form.policy_config),
          workflow_dsl: JSON.parse(form.workflow_dsl)
        })
      });
      setMessage('Agent created.');
      await load();
    } catch (err) {
      setMessage(`Create failed: ${err.message}`);
    }
  }

  async function patchAgent(agentId) {
    try {
      await api(`/agents/${agentId}/config`, {
        method: 'PUT',
        body: JSON.stringify({ script: `${form.script}\n(Updated ${new Date().toISOString()})` })
      });
      setMessage('Agent config updated.');
      await load();
    } catch (err) {
      setMessage(`Update failed: ${err.message}`);
    }
  }

  return (
    <main className="container">
      <Nav />
      <h1>Agent Builder</h1>
      <div className="grid-2">
        <section className="card">
          <h2>Create Agent Persona</h2>
          <form onSubmit={createAgent}>
            <label>Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <label>Persona</label>
            <textarea value={form.persona} onChange={(e) => setForm({ ...form, persona: e.target.value })} />
            <label>Script</label>
            <textarea value={form.script} onChange={(e) => setForm({ ...form, script: e.target.value })} />
            <label>Required Fields JSON</label>
            <textarea
              value={form.required_fields}
              onChange={(e) => setForm({ ...form, required_fields: e.target.value })}
            />
            <label>Tools Config JSON</label>
            <textarea value={form.tools_config} onChange={(e) => setForm({ ...form, tools_config: e.target.value })} />
            <label>Policy Config JSON</label>
            <textarea value={form.policy_config} onChange={(e) => setForm({ ...form, policy_config: e.target.value })} />
            <label>Workflow DSL JSON</label>
            <textarea value={form.workflow_dsl} onChange={(e) => setForm({ ...form, workflow_dsl: e.target.value })} />
            <button type="submit">Create Agent</button>
          </form>
        </section>

        <section className="card">
          <h2>Existing Agents</h2>
          {agents.map((agent) => (
            <div key={agent.id} className="card" style={{ marginBottom: 10 }}>
              <strong>{agent.name}</strong>
              <p>{agent.persona}</p>
              <button className="secondary" onClick={() => patchAgent(agent.id)}>
                Quick Update Config
              </button>
            </div>
          ))}
        </section>
      </div>
      <section className="card">{message || 'Ready.'}</section>
    </main>
  );
}

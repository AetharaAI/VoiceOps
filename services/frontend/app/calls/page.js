'use client';

import { useEffect, useState } from 'react';
import Nav from '../../components/nav';
import { api } from '../../lib/api';

export default function CallsPage() {
  const [calls, setCalls] = useState([]);
  const [agents, setAgents] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [tenantId, setTenantId] = useState('');
  const [selectedCall, setSelectedCall] = useState(null);
  const [selectedCallLog, setSelectedCallLog] = useState(null);
  const [message, setMessage] = useState('');

  const [dialForm, setDialForm] = useState({ to_number: '+15551230099', agent_id: '', campaign_id: '' });

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const [tenant, callList, agentList, campaignList] = await Promise.all([
        api('/tenants/me'),
        api('/calls'),
        api('/agents'),
        api('/campaigns/outbound').catch(() => [])
      ]);
      setTenantId(tenant.id);
      setCalls(callList);
      setAgents(agentList);
      setCampaigns(campaignList || []);
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
      if (data.external_call_id) {
        try {
          const log = await api(`/call-logs/by-call-sid/${encodeURIComponent(data.external_call_id)}`);
          setSelectedCallLog(log);
        } catch (_err) {
          setSelectedCallLog(null);
        }
      } else {
        setSelectedCallLog(null);
      }
    } catch (err) {
      setMessage(err.message);
    }
  }

  const selectedTelemetry = selectedCall?.outcome_tags?.telemetry || {};
  const selectedMode = selectedCall?.outcome_tags?.llm_mode || selectedTelemetry.llm_mode || 'unknown';
  const selectedIntent = selectedCall?.outcome_tags?.detected_intent || selectedTelemetry.detected_intent || 'unknown';
  const selectedSource = selectedCall?.outcome_tags?.last_response_source || 'unknown';
  const selectedArtifacts = selectedCall?.outcome_tags?.operator_artifacts || {};
  const visibleEvents = (selectedCallLog?.events || []).filter((event) =>
    [
      'call.started',
      'call.greeting.sent',
      'call.llm.request.start',
      'call.llm.request.end',
      'call.llm.request.fail',
      'call.intent.detected',
      'call.required_fields.missing',
      'call.required_fields.collected',
      'call.fallback.engaged',
      'call.response.generated',
      'call.response.spoken',
      'call.extraction.ready',
      'call.action.ready'
    ].includes(event.event_type)
  );

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
            <select
              value={dialForm.campaign_id}
              onChange={(e) => setDialForm({ ...dialForm, campaign_id: e.target.value })}
            >
              <option value="">No campaign</option>
              {campaigns.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>
                  {campaign.name}
                </option>
              ))}
            </select>
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
        {selectedCall?.outcome_tags ? (
          <div className="card" style={{ marginBottom: 12 }}>
            <div><strong>Disposition:</strong> {selectedCall.outcome_tags.final_disposition || selectedCall.outcome || 'unknown'}</div>
            <div><strong>Duration:</strong> {selectedCall.outcome_tags.duration_seconds ?? 'n/a'}s</div>
            <div><strong>LLM Mode:</strong> {selectedMode}</div>
            <div><strong>Detected Intent:</strong> {selectedIntent}</div>
            <div><strong>Last Response Source:</strong> {selectedSource}</div>
            <div><strong>Campaign:</strong> {campaigns.find((campaign) => campaign.id === selectedCall.campaign_id)?.name || selectedCall.campaign_id || 'none'}</div>
            <div><strong>Captured:</strong> {Object.keys(selectedCall.outcome_tags.fields_captured || {}).join(', ') || 'none'}</div>
            <div><strong>Missing:</strong> {(selectedCall.outcome_tags.missing_fields || []).join(', ') || 'none'}</div>
            <div><strong>Errors:</strong> {(selectedCall.outcome_tags.notable_errors || []).join(', ') || 'none'}</div>
          </div>
        ) : null}
        {selectedCallLog ? (
          <div className="card" style={{ marginBottom: 12 }}>
            <h3>Decision Log</h3>
            {visibleEvents.length ? (
              visibleEvents.map((event, index) => (
                <div key={`${event.timestamp}-${event.event_type}-${index}`} className="card" style={{ marginBottom: 8 }}>
                  <div><strong>{event.event_type}</strong></div>
                  <div>{event.timestamp}</div>
                  <div>Mode: {event.llm_mode || event.payload?.llm_mode || 'n/a'}</div>
                  <div>Payload: {JSON.stringify(event.payload || {})}</div>
                </div>
              ))
            ) : (
              <div>No decision events recorded for this call yet.</div>
            )}
          </div>
        ) : null}
        {selectedArtifacts.extraction ? (
          <div className="card" style={{ marginBottom: 12 }}>
            <h3>Extraction Artifact</h3>
            <pre>{JSON.stringify(selectedArtifacts.extraction, null, 2)}</pre>
          </div>
        ) : null}
        {selectedArtifacts.action ? (
          <div className="card" style={{ marginBottom: 12 }}>
            <h3>Action Artifact</h3>
            <pre>{JSON.stringify(selectedArtifacts.action, null, 2)}</pre>
          </div>
        ) : null}
        <pre>{JSON.stringify(selectedCall, null, 2)}</pre>
      </section>

      <section className="card">{message || 'Ready.'}</section>
    </main>
  );
}

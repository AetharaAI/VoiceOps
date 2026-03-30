'use client';

import { useEffect, useState } from 'react';
import Nav from '../../components/nav';
import { api } from '../../lib/api';
import {
  DEFAULT_VOICE_OPTIONS,
  buildLlmModelOptions,
  buildVoiceOptions,
  compatibleVoices,
  defaultInboundForm,
  parseJsonObject,
  resolvedTtsModel,
  resolvedVoice,
  ttsModelOptions,
  voiceLabel
} from '../../lib/operator-builder';

function runtimeFromAgent(agent) {
  return agent?.policy_config?.runtime || {};
}

function inboundConfigFromAgent(agent) {
  return agent?.workflow_dsl?.inbound_builder || {};
}

const DEFAULT_TRANSFER_KEYWORDS = ['human', 'representative', 'real person', 'operator', 'manager', 'sales', 'transfer me'];

function humanTransferFromBuilder(builder) {
  const transfer = builder?.human_transfer || {};
  const keywords = Array.isArray(transfer.keywords)
    ? transfer.keywords.filter((value) => typeof value === 'string' && value.trim())
    : DEFAULT_TRANSFER_KEYWORDS;
  return {
    enabled: Boolean(transfer.enabled),
    trigger_mode: transfer.trigger_mode || 'explicit_or_keyword',
    keywords,
    destination_type: transfer.destination_type || 'phone_number',
    destination: transfer.destination || '',
    label: transfer.label || 'Front Desk',
    confirmation_message: transfer.confirmation_message || 'Absolutely. I will transfer you to a team member now.',
    no_answer_fallback: transfer.no_answer_fallback || 'return_to_ai',
    ring_timeout_seconds: Number.isInteger(transfer.ring_timeout_seconds) ? transfer.ring_timeout_seconds : 20
  };
}

function parseKeywords(text) {
  return text
    .split(/[\n,]/)
    .map((value) => value.trim())
    .filter((value, index, arr) => value && arr.indexOf(value) === index);
}

function formFromAgent(agent, voices, phoneNumbers) {
  const runtime = runtimeFromAgent(agent);
  const builder = inboundConfigFromAgent(agent);
  const transfer = humanTransferFromBuilder(builder);
  const assignedNumber = phoneNumbers.find((row) => row.agent_id === agent.id);
  const ttsModel = runtime.tts_model || 'kokoro_realtime';
  const ttsVoice = runtime.tts_voice || 'af_bella';
  const knownVoice = voices.some((voice) => voice.id === ttsVoice);

  return {
    name: agent.name,
    assigned_number_id: assignedNumber?.id || '',
    greeting_mode: builder.greeting_mode || 'tts_fixed',
    opening_greeting: runtime.opening_greeting || '',
    persona: builder.business_context || agent.persona || '',
    script: builder.goal || agent.script || '',
    required_fields: JSON.stringify(agent.required_fields || {}, null, 2),
    action_config: JSON.stringify(builder.action_config || {}, null, 2),
    crm_mapping: JSON.stringify(builder.crm_mapping || {}, null, 2),
    human_transfer_enabled: transfer.enabled,
    human_transfer_trigger_mode: transfer.trigger_mode,
    human_transfer_keywords: transfer.keywords.join(', '),
    human_transfer_destination_type: transfer.destination_type,
    human_transfer_destination: transfer.destination,
    human_transfer_label: transfer.label,
    human_transfer_confirmation_message: transfer.confirmation_message,
    human_transfer_no_answer_fallback: transfer.no_answer_fallback,
    human_transfer_ring_timeout_seconds: transfer.ring_timeout_seconds,
    llm_model: runtime.llm_model || '',
    tts_model_select: ttsModel,
    custom_tts_model: '',
    tts_voice_select: knownVoice ? ttsVoice : '__custom__',
    custom_tts_voice: knownVoice ? '' : ttsVoice,
    fsm_config: JSON.stringify(builder.fsm_config || {}, null, 2)
  };
}

function buildAgentPayload(form) {
  const ttsModel = resolvedTtsModel(form.tts_model_select, form.custom_tts_model) || 'kokoro_realtime';
  const ttsVoice = resolvedVoice(form.tts_voice_select, form.custom_tts_voice) || 'af_bella';
  const requiredFields = parseJsonObject('Required Fields JSON', form.required_fields);
  const actionConfig = parseJsonObject('Action Execution JSON', form.action_config);
  const crmMapping = parseJsonObject('CRM Mapping JSON', form.crm_mapping);
  const ringTimeout = Number.parseInt(String(form.human_transfer_ring_timeout_seconds || '20'), 10);
  if (!Number.isFinite(ringTimeout) || ringTimeout < 5 || ringTimeout > 120) {
    throw new Error('Human transfer ring timeout must be an integer between 5 and 120 seconds.');
  }
  const transferKeywords = parseKeywords(form.human_transfer_keywords || '');

  return {
    name: form.name.trim(),
    persona: form.persona.trim(),
    script: form.script.trim(),
    required_fields: requiredFields,
    tools_config: actionConfig,
    policy_config: {
      runtime: {
        llm_provider: 'openai',
        llm_model: form.llm_model,
        enable_thinking: false,
        opening_greeting: form.opening_greeting.trim(),
        tts_provider: 'aether_voice',
        tts_model: ttsModel,
        tts_voice: ttsVoice,
        tts_metadata: {}
      }
    },
    workflow_dsl: {
      workflow_type: 'inbound',
      inbound_builder: {
        greeting_mode: form.greeting_mode,
        business_context: form.persona.trim(),
        goal: form.script.trim(),
        action_config: actionConfig,
        crm_mapping: crmMapping,
        human_transfer: {
          enabled: Boolean(form.human_transfer_enabled),
          trigger_mode: form.human_transfer_trigger_mode,
          keywords: transferKeywords.length ? transferKeywords : DEFAULT_TRANSFER_KEYWORDS,
          destination_type: form.human_transfer_destination_type,
          destination: form.human_transfer_destination.trim(),
          label: form.human_transfer_label.trim() || 'Front Desk',
          confirmation_message:
            form.human_transfer_confirmation_message.trim() ||
            'Absolutely. I will transfer you to a team member now.',
          no_answer_fallback: form.human_transfer_no_answer_fallback,
          ring_timeout_seconds: ringTimeout
        },
        // fsm_config is persisted as-is; the State Controller reads it at call start.
        // An empty object is valid — defaults apply.
        fsm_config: parseJsonObject('FSM Config JSON', form.fsm_config)
      }
    }
  };
}

export default function InboundPage() {
  const [agents, setAgents] = useState([]);
  const [llmModels, setLlmModels] = useState([]);
  const [llmModelError, setLlmModelError] = useState('');
  const [voices, setVoices] = useState(DEFAULT_VOICE_OPTIONS);
  const [phoneNumbers, setPhoneNumbers] = useState([]);
  const [editingAgentId, setEditingAgentId] = useState('');
  const [form, setForm] = useState(defaultInboundForm());
  const [message, setMessage] = useState('');
  const [fsmConfigOpen, setFsmConfigOpen] = useState(false);
  const [humanTransferOpen, setHumanTransferOpen] = useState(false);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const [agentList, numberList, modelResult, voiceResult] = await Promise.allSettled([
        api('/agents'),
        api('/phone-numbers'),
        api('/llm/models'),
        api('/tts/voices')
      ]);

      if (agentList.status !== 'fulfilled') {
        throw agentList.reason;
      }
      if (numberList.status !== 'fulfilled') {
        throw numberList.reason;
      }

      const inboundAgents = (agentList.value || []).filter((agent) => {
        const kind = agent?.workflow_dsl?.workflow_type;
        return !kind || kind === 'inbound';
      });

      setAgents(inboundAgents);
      setPhoneNumbers(numberList.value || []);

      if (modelResult.status === 'fulfilled' && Array.isArray(modelResult.value)) {
        setLlmModels(modelResult.value);
        setLlmModelError('');
      } else {
        setLlmModels([]);
        setLlmModelError(modelResult.status === 'rejected' ? modelResult.reason.message : 'Live model list failed.');
      }

      if (voiceResult.status === 'fulfilled' && Array.isArray(voiceResult.value) && voiceResult.value.length) {
        setVoices(voiceResult.value);
      } else {
        setVoices(DEFAULT_VOICE_OPTIONS);
      }
    } catch (err) {
      setMessage(err.message);
    }
  }

  useEffect(() => {
    if (!form.llm_model && llmModels.length) {
      setForm((current) => ({ ...current, llm_model: current.llm_model || llmModels[0] }));
    }
  }, [form.llm_model, llmModels]);

  async function assignNumber(agentId, phoneRowId) {
    if (!phoneRowId) return;
    const row = phoneNumbers.find((item) => item.id === phoneRowId);
    if (!row) return;
    await api('/phone-numbers', {
      method: 'POST',
      body: JSON.stringify({
        phone_number: row.phone_number,
        provider: row.provider,
        agent_id: agentId
      })
    });
  }

  async function submitForm(e) {
    e.preventDefault();
    try {
      const payload = buildAgentPayload(form);
      let saved;
      if (editingAgentId) {
        saved = await api(`/agents/${editingAgentId}/config`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        });
      } else {
        saved = await api('/agents', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
      }

      if (form.assigned_number_id) {
        await assignNumber(saved.id, form.assigned_number_id);
      }

      setEditingAgentId(saved.id);
      setMessage(`Inbound workflow ${saved.name} saved.`);
      await load();
    } catch (err) {
      setMessage(err.message);
    }
  }

  function loadWorkflow(agent) {
    setEditingAgentId(agent.id);
    setForm(formFromAgent(agent, voices, phoneNumbers));
    setMessage(`Loaded inbound workflow ${agent.name}.`);
  }

  const selectedModel = resolvedTtsModel(form.tts_model_select, form.custom_tts_model);
  const voiceOptions = buildVoiceOptions(compatibleVoices(voices, selectedModel));
  const modelOptions = buildLlmModelOptions(llmModels, form.llm_model);

  return (
    <main className="container">
      <Nav />
      <h1>Inbound Workflow Builder</h1>
      <section className="card" style={{ marginBottom: 16 }}>
        <strong>Operator Intent</strong>
        <p>
          Configure who answers, how the greeting sounds, what gets extracted, and which actions can execute after the
          live ASR → LLM → TTS loop begins.
        </p>
        {llmModelError ? (
          <p style={{ color: '#b42318', marginBottom: 0 }}>
            Live model list unavailable: {llmModelError}
          </p>
        ) : null}
      </section>

      <div className="grid-2">
        <section className="card">
          <h2>{editingAgentId ? 'Edit Inbound Workflow' : 'Create Inbound Workflow'}</h2>
          <form onSubmit={submitForm}>
            <label>Workflow Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />

            <label>Assigned Inbound Number</label>
            <select
              value={form.assigned_number_id}
              onChange={(e) => setForm({ ...form, assigned_number_id: e.target.value })}
            >
              <option value="">Unassigned</option>
              {phoneNumbers.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.phone_number}
                </option>
              ))}
            </select>

            <label>Greeting Mode</label>
            <select value={form.greeting_mode} onChange={(e) => setForm({ ...form, greeting_mode: e.target.value })}>
              <option value="prerecorded">Prerecorded</option>
              <option value="tts_fixed">Fixed TTS Greeting</option>
              <option value="generated">Generated Greeting</option>
            </select>

            <label>Opening Greeting</label>
            <textarea
              value={form.opening_greeting}
              onChange={(e) => setForm({ ...form, opening_greeting: e.target.value })}
              placeholder="Thank you for calling Syndicate AI. This is Maya..."
            />

            <label>Business Context</label>
            <textarea value={form.persona} onChange={(e) => setForm({ ...form, persona: e.target.value })} />

            <label>Operator Goal / Flow Guidance</label>
            <textarea value={form.script} onChange={(e) => setForm({ ...form, script: e.target.value })} />

            <label>Live Model</label>
            <select value={form.llm_model} onChange={(e) => setForm({ ...form, llm_model: e.target.value })}>
              {!modelOptions.length ? <option value="">No live models found</option> : null}
              {modelOptions.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>

            <label>TTS Lane</label>
            <select
              value={form.tts_model_select}
              onChange={(e) => setForm({ ...form, tts_model_select: e.target.value })}
            >
              {ttsModelOptions().map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>

            {form.tts_model_select === '__custom__' ? (
              <>
                <label>Custom TTS Model</label>
                <input
                  value={form.custom_tts_model}
                  onChange={(e) => setForm({ ...form, custom_tts_model: e.target.value })}
                />
              </>
            ) : null}

            <label>Voice</label>
            <select
              value={form.tts_voice_select}
              onChange={(e) => setForm({ ...form, tts_voice_select: e.target.value })}
            >
              {voiceOptions.map((voice) => (
                <option key={voice.id} value={voice.id}>
                  {voice.label ? voiceLabel(voice) : voice.id}
                </option>
              ))}
            </select>

            {form.tts_voice_select === '__custom__' ? (
              <>
                <label>Custom Voice</label>
                <input
                  value={form.custom_tts_voice}
                  onChange={(e) => setForm({ ...form, custom_tts_voice: e.target.value })}
                />
              </>
            ) : null}

            <label>Required Fields JSON</label>
            <textarea value={form.required_fields} onChange={(e) => setForm({ ...form, required_fields: e.target.value })} />

            <label>Action Execution JSON</label>
            <textarea value={form.action_config} onChange={(e) => setForm({ ...form, action_config: e.target.value })} />

            <label>CRM Mapping JSON</label>
            <textarea value={form.crm_mapping} onChange={(e) => setForm({ ...form, crm_mapping: e.target.value })} />

            <div style={{ marginTop: 16, borderTop: '1px solid #e0e0e0', paddingTop: 12 }}>
              <button
                type="button"
                className="secondary"
                style={{ width: '100%', textAlign: 'left', fontWeight: 500 }}
                onClick={() => setHumanTransferOpen((open) => !open)}
              >
                {humanTransferOpen ? '▾' : '▸'} Human Transfer Settings
              </button>
              {humanTransferOpen && (
                <div style={{ marginTop: 10 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <input
                      type="checkbox"
                      checked={Boolean(form.human_transfer_enabled)}
                      onChange={(e) => setForm({ ...form, human_transfer_enabled: e.target.checked })}
                    />
                    Enable human transfer
                  </label>

                  <label>Trigger Mode</label>
                  <select
                    value={form.human_transfer_trigger_mode}
                    onChange={(e) => setForm({ ...form, human_transfer_trigger_mode: e.target.value })}
                  >
                    <option value="explicit_only">Explicit only</option>
                    <option value="keyword_only">Keyword only</option>
                    <option value="explicit_or_keyword">Explicit or keyword</option>
                  </select>

                  <label>Keywords (comma or newline separated)</label>
                  <textarea
                    value={form.human_transfer_keywords}
                    onChange={(e) => setForm({ ...form, human_transfer_keywords: e.target.value })}
                  />

                  <label>Target Label</label>
                  <input
                    value={form.human_transfer_label}
                    onChange={(e) => setForm({ ...form, human_transfer_label: e.target.value })}
                    placeholder="Front Desk"
                  />

                  <label>Destination Type</label>
                  <select
                    value={form.human_transfer_destination_type}
                    onChange={(e) => setForm({ ...form, human_transfer_destination_type: e.target.value })}
                  >
                    <option value="phone_number">Phone Number</option>
                    <option value="sip">SIP</option>
                    <option value="twilio_client">Twilio Client</option>
                  </select>

                  <label>Destination</label>
                  <input
                    value={form.human_transfer_destination}
                    onChange={(e) => setForm({ ...form, human_transfer_destination: e.target.value })}
                    placeholder="+18129691371 or sip:agent@yourpbx.com"
                  />

                  <label>Confirmation Message</label>
                  <textarea
                    value={form.human_transfer_confirmation_message}
                    onChange={(e) => setForm({ ...form, human_transfer_confirmation_message: e.target.value })}
                  />

                  <label>No Answer Fallback</label>
                  <select
                    value={form.human_transfer_no_answer_fallback}
                    onChange={(e) => setForm({ ...form, human_transfer_no_answer_fallback: e.target.value })}
                  >
                    <option value="return_to_ai">Return to AI</option>
                    <option value="voicemail">Voicemail</option>
                    <option value="callback_capture">Callback capture</option>
                    <option value="end_call">End call</option>
                  </select>

                  <label>Ring Timeout (seconds)</label>
                  <input
                    type="number"
                    min="5"
                    max="120"
                    value={form.human_transfer_ring_timeout_seconds}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        human_transfer_ring_timeout_seconds: e.target.value,
                      })
                    }
                  />
                </div>
              )}
            </div>

            {/* FUTURE: Visual FSM configurator — lane editor, field editor, timeout sliders,
                greeting per-state. See FSM/voiceops_inbound_state_machine.svg for reference. */}
            <div style={{ marginTop: 16, borderTop: '1px solid #e0e0e0', paddingTop: 12 }}>
              <button
                type="button"
                className="secondary"
                style={{ width: '100%', textAlign: 'left', fontWeight: 500 }}
                onClick={() => setFsmConfigOpen((open) => !open)}
              >
                {fsmConfigOpen ? '▾' : '▸'} Call flow configuration (advanced)
              </button>
              {fsmConfigOpen && (
                <div style={{ marginTop: 10 }}>
                  <p style={{ fontSize: 13, color: '#555', marginBottom: 8 }}>
                    FSM config is persisted with the workflow and read by the State Controller at call start.
                    Visual lane editor coming soon.
                  </p>
                  <pre style={{
                    background: '#f5f5f5',
                    border: '1px solid #ddd',
                    borderRadius: 4,
                    padding: 10,
                    fontSize: 12,
                    overflowX: 'auto',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word'
                  }}>
                    {form.fsm_config || '{}'}
                  </pre>
                </div>
              )}
            </div>

            <button type="submit" style={{ marginTop: 16 }}>{editingAgentId ? 'Save Inbound Workflow' : 'Create Inbound Workflow'}</button>
          </form>
        </section>

        <section className="card">
          <h2>Existing Inbound Workflows</h2>
          {agents.length ? (
            agents.map((agent) => {
              const runtime = runtimeFromAgent(agent);
              const assigned = phoneNumbers.filter((row) => row.agent_id === agent.id);
              return (
                <div key={agent.id} className="card" style={{ marginBottom: 12 }}>
                  <div><strong>{agent.name}</strong></div>
                  <div>Greeting: {runtime.opening_greeting || 'Not set'}</div>
                  <div>Live model: {runtime.llm_model || 'Not set'}</div>
                  <div>TTS lane: {runtime.tts_model || 'Not set'}</div>
                  <div>Voice: {runtime.tts_voice || 'Not set'}</div>
                  <div>Inbound numbers: {assigned.length ? assigned.map((row) => row.phone_number).join(', ') : 'Unassigned'}</div>
                  <button className="secondary" onClick={() => loadWorkflow(agent)}>
                    Edit Inbound Workflow
                  </button>
                </div>
              );
            })
          ) : (
            <div>No inbound workflows saved yet.</div>
          )}
        </section>
      </div>

      <section className="card" style={{ marginTop: 16 }}>
        {message || 'Ready.'}
      </section>
    </main>
  );
}

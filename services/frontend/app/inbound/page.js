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

function formFromAgent(agent, voices, phoneNumbers) {
  const runtime = runtimeFromAgent(agent);
  const builder = inboundConfigFromAgent(agent);
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
    llm_model: runtime.llm_model || '',
    tts_model_select: ttsModel,
    custom_tts_model: '',
    tts_voice_select: knownVoice ? ttsVoice : '__custom__',
    custom_tts_voice: knownVoice ? '' : ttsVoice
  };
}

function buildAgentPayload(form) {
  const ttsModel = resolvedTtsModel(form.tts_model_select, form.custom_tts_model) || 'kokoro_realtime';
  const ttsVoice = resolvedVoice(form.tts_voice_select, form.custom_tts_voice) || 'af_bella';
  const requiredFields = parseJsonObject('Required Fields JSON', form.required_fields);
  const actionConfig = parseJsonObject('Action Execution JSON', form.action_config);
  const crmMapping = parseJsonObject('CRM Mapping JSON', form.crm_mapping);

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
        crm_mapping: crmMapping
      }
    }
  };
}

export default function InboundPage() {
  const [agents, setAgents] = useState([]);
  const [llmModels, setLlmModels] = useState([]);
  const [voices, setVoices] = useState(DEFAULT_VOICE_OPTIONS);
  const [phoneNumbers, setPhoneNumbers] = useState([]);
  const [editingAgentId, setEditingAgentId] = useState('');
  const [form, setForm] = useState(defaultInboundForm());
  const [message, setMessage] = useState('');

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const [agentList, numberList, modelList, voiceList] = await Promise.all([
        api('/agents'),
        api('/phone-numbers'),
        api('/llm/models').catch(() => []),
        api('/tts/voices').catch(() => DEFAULT_VOICE_OPTIONS)
      ]);

      const inboundAgents = (agentList || []).filter((agent) => {
        const kind = agent?.workflow_dsl?.workflow_type;
        return !kind || kind === 'inbound';
      });

      setAgents(inboundAgents);
      setPhoneNumbers(numberList || []);
      setLlmModels(Array.isArray(modelList) ? modelList : []);
      setVoices(Array.isArray(voiceList) && voiceList.length ? voiceList : DEFAULT_VOICE_OPTIONS);
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

            <button type="submit">{editingAgentId ? 'Save Inbound Workflow' : 'Create Inbound Workflow'}</button>
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

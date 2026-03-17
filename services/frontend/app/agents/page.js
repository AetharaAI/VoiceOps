'use client';

import { useEffect, useState } from 'react';
import Nav from '../../components/nav';
import { api } from '../../lib/api';

const MODEL_OPTIONS = [
  'qwen3.5-35b',
  'qwen3.5-122',
  'qwen3.5-9b',
  'omnicoder',
  'devstral-123b',
  'qwen3.5-4b',
  'qwen3.5-2b',
  'qwen3.5-9b-h',
  'jan-code-4b',
  'nanbeige4-3b-thinking',
  'minicpm-v',
  'redqwen-vl',
  'cisco-sec',
  'vulnllm-r-7b',
  'phi-4-instruct'
];

const VOICE_OPTIONS = [
  { value: 'af_bella', label: 'af_bella (Default)' },
  { value: 'af_nicole', label: 'af_nicole' },
  { value: 'af_sky', label: 'af_sky' },
  { value: '__custom__', label: 'Custom Voice' }
];

const seedRequiredFields = {
  name: { prompt: 'Can I have your full name?' },
  phone: { prompt: 'What is the best callback number?' },
  appointment_type: { prompt: 'What kind of appointment do you need?' }
};

const defaultPolicyConfig = {
  human_handoff_number: '+15550000000',
  business_hours_only: true
};

const defaultToolsConfig = { booking: true, crm_writeback: true, sms_follow_up: true };
const defaultWorkflowDsl = { post_call: [{ type: 'ticket' }] };

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

function parseJsonField(label, value) {
  try {
    const parsed = JSON.parse(value);
    if (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error(`${label} must be a JSON object.`);
    }
    return parsed;
  } catch (err) {
    throw new Error(`${label} is invalid JSON: ${err.message}`);
  }
}

function stripRuntime(policyConfig) {
  const next = { ...(policyConfig || {}) };
  delete next.runtime;
  return next;
}

function emptyForm() {
  return {
    name: 'Sales Agent',
    persona: 'Helpful and concise revenue assistant',
    script: 'Qualify leads and book appointments.',
    llm_provider: 'openai',
    llm_model: 'omnicoder',
    tts_voice_select: 'af_bella',
    custom_tts_voice: '',
    required_fields: prettyJson(seedRequiredFields),
    tools_config: prettyJson(defaultToolsConfig),
    policy_config: prettyJson(defaultPolicyConfig),
    workflow_dsl: prettyJson(defaultWorkflowDsl)
  };
}

function runtimeConfigFromAgent(agent) {
  return agent?.policy_config?.runtime || {};
}

function formFromAgent(agent) {
  const runtime = runtimeConfigFromAgent(agent);
  const ttsVoice = runtime.tts_voice || 'af_bella';
  const hasPresetVoice = VOICE_OPTIONS.some((option) => option.value === ttsVoice);

  return {
    name: agent.name,
    persona: agent.persona,
    script: agent.script,
    llm_provider: runtime.llm_provider || 'openai',
    llm_model: runtime.llm_model || 'omnicoder',
    tts_voice_select: hasPresetVoice ? ttsVoice : '__custom__',
    custom_tts_voice: hasPresetVoice ? '' : ttsVoice,
    required_fields: prettyJson(agent.required_fields || {}),
    tools_config: prettyJson(agent.tools_config || {}),
    policy_config: prettyJson(stripRuntime(agent.policy_config || {})),
    workflow_dsl: prettyJson(agent.workflow_dsl || {})
  };
}

function resolvedVoice(form) {
  return form.tts_voice_select === '__custom__' ? form.custom_tts_voice.trim() : form.tts_voice_select;
}

function buildAgentPayload(form) {
  const voice = resolvedVoice(form) || 'af_bella';
  const policyConfig = parseJsonField('Policy Config', form.policy_config);

  return {
    name: form.name,
    persona: form.persona,
    script: form.script,
    required_fields: parseJsonField('Required Fields', form.required_fields),
    tools_config: parseJsonField('Tools Config', form.tools_config),
    policy_config: {
      ...policyConfig,
      runtime: {
        ...(policyConfig.runtime || {}),
        llm_provider: form.llm_provider,
        llm_model: form.llm_model,
        enable_thinking: false,
        tts_voice: voice
      }
    },
    workflow_dsl: parseJsonField('Workflow DSL', form.workflow_dsl)
  };
}

export default function AgentsPage() {
  const [agents, setAgents] = useState([]);
  const [message, setMessage] = useState('');
  const [editingAgentId, setEditingAgentId] = useState('');
  const [form, setForm] = useState(emptyForm());

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
        body: JSON.stringify(buildAgentPayload(form))
      });
      setMessage('Agent created.');
      setEditingAgentId('');
      setForm(emptyForm());
      await load();
    } catch (err) {
      setMessage(`Create failed: ${err.message}`);
    }
  }

  async function saveAgent(agentId) {
    try {
      const payload = buildAgentPayload(form);
      await api(`/agents/${agentId}/config`, {
        method: 'PUT',
        body: JSON.stringify({
          persona: payload.persona,
          script: payload.script,
          required_fields: payload.required_fields,
          tools_config: payload.tools_config,
          policy_config: payload.policy_config,
          workflow_dsl: payload.workflow_dsl
        })
      });
      setMessage('Agent updated.');
      await load();
    } catch (err) {
      setMessage(`Update failed: ${err.message}`);
    }
  }

  function loadIntoEditor(agent) {
    setEditingAgentId(agent.id);
    setForm(formFromAgent(agent));
    setMessage(`Loaded ${agent.name} into editor.`);
  }

  return (
    <main className="container">
      <Nav />
      <h1>Agent Builder</h1>
      <div className="grid-2">
        <section className="card">
          <h2>{editingAgentId ? 'Edit Agent Runtime' : 'Create Agent Persona'}</h2>
          <form onSubmit={createAgent}>
            <label>Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <label>Persona</label>
            <textarea value={form.persona} onChange={(e) => setForm({ ...form, persona: e.target.value })} />
            <label>Script</label>
            <textarea value={form.script} onChange={(e) => setForm({ ...form, script: e.target.value })} />
            <label>Live Call Model</label>
            <select value={form.llm_model} onChange={(e) => setForm({ ...form, llm_model: e.target.value })}>
              {MODEL_OPTIONS.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
            <label>Voice</label>
            <select
              value={form.tts_voice_select}
              onChange={(e) => setForm({ ...form, tts_voice_select: e.target.value })}
            >
              {VOICE_OPTIONS.map((voice) => (
                <option key={voice.value} value={voice.value}>
                  {voice.label}
                </option>
              ))}
            </select>
            {form.tts_voice_select === '__custom__' ? (
              <>
                <label>Custom Voice ID</label>
                <input
                  value={form.custom_tts_voice}
                  onChange={(e) => setForm({ ...form, custom_tts_voice: e.target.value })}
                  placeholder="Enter provider voice ID"
                />
              </>
            ) : null}
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
            {editingAgentId ? (
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setEditingAgentId('');
                  setForm(emptyForm());
                  setMessage('Editor reset to new-agent defaults.');
                }}
              >
                Reset Editor
              </button>
            ) : null}
          </form>
        </section>

        <section className="card">
          <h2>Existing Agents</h2>
          {agents.map((agent) => {
            const runtime = runtimeConfigFromAgent(agent);
            return (
              <div key={agent.id} className="card" style={{ marginBottom: 10 }}>
                <strong>{agent.name}</strong>
                <p>{agent.persona}</p>
                <p>
                  Live model: <strong>{runtime.llm_model || 'omnicoder'}</strong>
                </p>
                <p>
                  Voice: <strong>{runtime.tts_voice || 'af_bella'}</strong>
                </p>
                <button className="secondary" onClick={() => loadIntoEditor(agent)}>
                  Load Into Editor
                </button>
                <button className="secondary" onClick={() => saveAgent(agent.id)}>
                  Save Editor To This Agent
                </button>
              </div>
            );
          })}
        </section>
      </div>
      <section className="card">{message || 'Ready.'}</section>
    </main>
  );
}

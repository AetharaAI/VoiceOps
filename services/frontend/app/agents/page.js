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

const TTS_MODEL_OPTIONS = [
  { id: 'kokoro_realtime', label: 'Kokoro Realtime', provider: 'aether_voice' },
  { id: 'qwen_customvoice', label: 'Qwen Custom Voice Batch', provider: 'aether_voice' },
  { id: 'qwen_customvoice_streaming', label: 'Qwen Custom Voice Streaming', provider: 'aether_voice' },
  { id: 'qwen_voice_design', label: 'Qwen Voice Design', provider: 'aether_voice' }
];
const CUSTOM_TTS_MODEL_OPTION = { id: '__custom__', label: 'Custom TTS Model' };

const DEFAULT_VOICE_OPTIONS = [
  {
    id: 'af_bella',
    label: 'Bella',
    family: 'kokoro_realtime',
    gender: 'female',
    style_tag: 'warm',
    provider: 'aether_voice',
    models: ['kokoro_realtime'],
    is_default: true
  },
  {
    id: 'af_heart',
    label: 'Heart',
    family: 'kokoro_realtime',
    gender: 'female',
    style_tag: 'bright',
    provider: 'aether_voice',
    models: ['kokoro_realtime'],
    is_default: false
  },
  {
    id: 'af_nicole',
    label: 'Nicole',
    family: 'kokoro_realtime',
    gender: 'female',
    style_tag: 'confident',
    provider: 'aether_voice',
    models: ['kokoro_realtime'],
    is_default: false
  },
  {
    id: 'af_sarah',
    label: 'Sarah',
    family: 'kokoro_realtime',
    gender: 'female',
    style_tag: 'clear',
    provider: 'aether_voice',
    models: ['kokoro_realtime'],
    is_default: false
  },
  {
    id: 'af_sky',
    label: 'Sky',
    family: 'kokoro_realtime',
    gender: 'female',
    style_tag: 'neutral',
    provider: 'aether_voice',
    models: ['kokoro_realtime'],
    is_default: false
  },
  {
    id: 'am_adam',
    label: 'Adam',
    family: 'kokoro_realtime',
    gender: 'male',
    style_tag: 'steady',
    provider: 'aether_voice',
    models: ['kokoro_realtime'],
    is_default: false
  },
  {
    id: 'am_michael',
    label: 'Michael',
    family: 'kokoro_realtime',
    gender: 'male',
    style_tag: 'clear',
    provider: 'aether_voice',
    models: ['kokoro_realtime'],
    is_default: false
  },
  {
    id: 'bf_emma',
    label: 'Emma',
    family: 'kokoro_realtime',
    gender: 'female',
    style_tag: 'british',
    provider: 'aether_voice',
    models: ['kokoro_realtime'],
    is_default: false
  },
  {
    id: 'bf_isabella',
    label: 'Isabella',
    family: 'kokoro_realtime',
    gender: 'female',
    style_tag: 'british',
    provider: 'aether_voice',
    models: ['kokoro_realtime'],
    is_default: false
  },
  {
    id: 'bm_george',
    label: 'George',
    family: 'kokoro_realtime',
    gender: 'male',
    style_tag: 'british',
    provider: 'aether_voice',
    models: ['kokoro_realtime'],
    is_default: false
  },
  {
    id: 'bm_lewis',
    label: 'Lewis',
    family: 'kokoro_realtime',
    gender: 'male',
    style_tag: 'british',
    provider: 'aether_voice',
    models: ['kokoro_realtime'],
    is_default: false
  },
  {
    id: 'qwen_ryan',
    label: 'Ryan',
    family: 'qwen_customvoice',
    gender: 'male',
    style_tag: 'clear',
    provider: 'aether_voice',
    models: ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design'],
    is_default: false
  },
  {
    id: 'qwen_aiden',
    label: 'Aiden',
    family: 'qwen_customvoice',
    gender: 'male',
    style_tag: 'steady',
    provider: 'aether_voice',
    models: ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design'],
    is_default: false
  },
  {
    id: 'qwen_serena',
    label: 'Serena',
    family: 'qwen_customvoice',
    gender: 'female',
    style_tag: 'calm',
    provider: 'aether_voice',
    models: ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design'],
    is_default: false
  },
  {
    id: 'qwen_vivian',
    label: 'Vivian',
    family: 'qwen_customvoice',
    gender: 'female',
    style_tag: 'polished',
    provider: 'aether_voice',
    models: ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design'],
    is_default: false
  },
  {
    id: 'qwen_uncle_fu',
    label: 'Uncle Fu',
    family: 'qwen_customvoice',
    gender: 'male',
    style_tag: 'warm',
    provider: 'aether_voice',
    models: ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design'],
    is_default: false
  },
  {
    id: 'qwen_sohee',
    label: 'Sohee',
    family: 'qwen_customvoice',
    gender: 'female',
    style_tag: 'bright',
    provider: 'aether_voice',
    models: ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design'],
    is_default: false
  },
  {
    id: 'qwen_dylan',
    label: 'Dylan',
    family: 'qwen_customvoice',
    gender: 'male',
    style_tag: 'neutral',
    provider: 'aether_voice',
    models: ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design'],
    is_default: false
  },
  {
    id: 'qwen_eric',
    label: 'Eric',
    family: 'qwen_customvoice',
    gender: 'male',
    style_tag: 'confident',
    provider: 'aether_voice',
    models: ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design'],
    is_default: false
  },
  {
    id: 'qwen_ono_anna',
    label: 'Ono Anna',
    family: 'qwen_customvoice',
    gender: 'female',
    style_tag: 'soft',
    provider: 'aether_voice',
    models: ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design'],
    is_default: false
  }
];
const CUSTOM_VOICE_OPTION = { id: '__custom__', label: 'Custom Voice' };

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
    tts_model_select: 'kokoro_realtime',
    custom_tts_model: '',
    tts_voice_select: 'af_bella',
    custom_tts_voice: '',
    tts_metadata: prettyJson({}),
    required_fields: prettyJson(seedRequiredFields),
    tools_config: prettyJson(defaultToolsConfig),
    policy_config: prettyJson(defaultPolicyConfig),
    workflow_dsl: prettyJson(defaultWorkflowDsl)
  };
}

function runtimeConfigFromAgent(agent) {
  return agent?.policy_config?.runtime || {};
}

function buildVoiceOptions(voices) {
  return [...voices, CUSTOM_VOICE_OPTION];
}

function voiceLabel(voice) {
  const suffix = [voice.gender, voice.style_tag].filter(Boolean).join(', ');
  const modelHint = Array.isArray(voice.models) && voice.models.length ? `, ${voice.models.join(' / ')}` : '';
  return voice.is_default
    ? `${voice.label} (${voice.id}, default${modelHint})`
    : `${voice.label} (${voice.id}${suffix ? `, ${suffix}` : ''}${modelHint})`;
}

function resolvedTtsModel(form) {
  return form.tts_model_select === '__custom__' ? form.custom_tts_model.trim() : form.tts_model_select;
}

function voiceSupportsModel(voice, model) {
  if (!model) return true;
  if (Array.isArray(voice.models) && voice.models.length) {
    return voice.models.includes(model);
  }
  return voice.family === model;
}

function compatibleVoices(voices, model) {
  return voices.filter((voice) => voiceSupportsModel(voice, model));
}

function formFromAgent(agent, voices) {
  const runtime = runtimeConfigFromAgent(agent);
  const ttsModel = runtime.tts_model || 'kokoro_realtime';
  const ttsVoice = runtime.tts_voice || 'af_bella';
  const hasPresetModel = TTS_MODEL_OPTIONS.some((option) => option.id === ttsModel);
  const hasPresetVoice = voices.some((option) => option.id === ttsVoice && voiceSupportsModel(option, ttsModel));

  return {
    name: agent.name,
    persona: agent.persona,
    script: agent.script,
    llm_provider: runtime.llm_provider || 'openai',
    llm_model: runtime.llm_model || 'omnicoder',
    tts_model_select: hasPresetModel ? ttsModel : '__custom__',
    custom_tts_model: hasPresetModel ? '' : ttsModel,
    tts_voice_select: hasPresetVoice ? ttsVoice : '__custom__',
    custom_tts_voice: hasPresetVoice ? '' : ttsVoice,
    tts_metadata: prettyJson(runtime.tts_metadata || {}),
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
  const ttsModel = resolvedTtsModel(form) || 'kokoro_realtime';
  const voice = resolvedVoice(form) || 'af_bella';
  const policyConfig = parseJsonField('Policy Config', form.policy_config);
  const ttsModelOption = TTS_MODEL_OPTIONS.find((option) => option.id === ttsModel);

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
        tts_provider: ttsModelOption?.provider || 'aether_voice',
        tts_model: ttsModel,
        tts_metadata: parseJsonField('TTS Metadata', form.tts_metadata),
        tts_voice: voice
      }
    },
    workflow_dsl: parseJsonField('Workflow DSL', form.workflow_dsl)
  };
}

export default function AgentsPage() {
  const [agents, setAgents] = useState([]);
  const [voices, setVoices] = useState(DEFAULT_VOICE_OPTIONS);
  const [message, setMessage] = useState('');
  const [editingAgentId, setEditingAgentId] = useState('');
  const [form, setForm] = useState(emptyForm());

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const [agentResult, voiceResult] = await Promise.allSettled([api('/agents'), api('/tts/voices')]);
      if (agentResult.status !== 'fulfilled') {
        throw agentResult.reason;
      }
      setAgents(agentResult.value);
      if (voiceResult.status === 'fulfilled' && Array.isArray(voiceResult.value) && voiceResult.value.length) {
        setVoices(voiceResult.value);
      } else {
        setVoices(DEFAULT_VOICE_OPTIONS);
      }
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
    setForm(formFromAgent(agent, voices));
    setMessage(`Loaded ${agent.name} into editor.`);
  }

  const selectedTtsModel = resolvedTtsModel(form);
  const voiceOptions = buildVoiceOptions(compatibleVoices(voices, selectedTtsModel));
  const ttsModelOptions = [...TTS_MODEL_OPTIONS, CUSTOM_TTS_MODEL_OPTION];

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
            <label>TTS Lane</label>
            <select
              value={form.tts_model_select}
              onChange={(e) => {
                const nextModelSelect = e.target.value;
                const nextModel =
                  nextModelSelect === '__custom__' ? form.custom_tts_model.trim() : nextModelSelect;
                const nextVoices = compatibleVoices(voices, nextModel);
                const currentVoice = form.tts_voice_select;
                const nextVoiceSelect =
                  currentVoice === '__custom__' || nextVoices.some((voice) => voice.id === currentVoice)
                    ? currentVoice
                    : nextVoices[0]?.id || '__custom__';

                setForm({
                  ...form,
                  tts_model_select: nextModelSelect,
                  tts_voice_select: nextVoiceSelect
                });
              }}
            >
              {ttsModelOptions.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.label}
                </option>
              ))}
            </select>
            {form.tts_model_select === '__custom__' ? (
              <>
                <label>Custom TTS Model</label>
                <input
                  value={form.custom_tts_model}
                  onChange={(e) => setForm({ ...form, custom_tts_model: e.target.value })}
                  placeholder="Enter provider model ID"
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
                  {voice.id === '__custom__' ? voice.label : voiceLabel(voice)}
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
            <label>TTS Metadata JSON</label>
            <textarea value={form.tts_metadata} onChange={(e) => setForm({ ...form, tts_metadata: e.target.value })} />
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
                  TTS lane: <strong>{runtime.tts_model || 'kokoro_realtime'}</strong>
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

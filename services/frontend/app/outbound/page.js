'use client';

import { useEffect, useState } from 'react';
import Nav from '../../components/nav';
import { api } from '../../lib/api';
import {
  DEFAULT_VOICE_OPTIONS,
  buildLlmModelOptions,
  buildVoiceOptions,
  compatibleVoices,
  defaultOutboundForm,
  parseJsonObject,
  resolvedTtsModel,
  resolvedVoice,
  ttsModelOptions,
  voiceLabel
} from '../../lib/operator-builder';

function formFromCampaign(campaign, voices) {
  const llmConfig = campaign.llm_config || {};
  const ttsConfig = campaign.tts_config || {};
  const knownVoice = voices.some((voice) => voice.id === ttsConfig.tts_voice);

  return {
    name: campaign.name,
    agent_id: campaign.agent_id || '',
    caller_id_number: campaign.caller_id_number || '',
    lead_source: campaign.lead_source || '',
    objective: campaign.objective || '',
    opening_line: campaign.opening_line || '',
    qualification_fields: JSON.stringify(campaign.qualification_fields || {}, null, 2),
    objection_guidance: campaign.objection_guidance || '',
    booking_target: campaign.booking_target || '',
    retry_rules: JSON.stringify(campaign.retry_rules || {}, null, 2),
    voicemail_config: JSON.stringify(campaign.voicemail_config || {}, null, 2),
    handoff_rules: JSON.stringify(campaign.handoff_rules || {}, null, 2),
    crm_mapping: JSON.stringify(campaign.crm_mapping || {}, null, 2),
    llm_model: llmConfig.llm_model || '',
    tts_model_select: ttsConfig.tts_model || 'kokoro_realtime',
    custom_tts_model: '',
    tts_voice_select: knownVoice ? (ttsConfig.tts_voice || 'af_bella') : '__custom__',
    custom_tts_voice: knownVoice ? '' : (ttsConfig.tts_voice || '')
  };
}

function buildCampaignPayload(form) {
  return {
    name: form.name.trim(),
    agent_id: form.agent_id || null,
    caller_id_number: form.caller_id_number.trim() || null,
    lead_source: form.lead_source.trim() || null,
    objective: form.objective.trim(),
    opening_line: form.opening_line.trim(),
    qualification_fields: parseJsonObject('Qualification Fields JSON', form.qualification_fields),
    objection_guidance: form.objection_guidance.trim() || null,
    booking_target: form.booking_target.trim() || null,
    retry_rules: parseJsonObject('Retry Rules JSON', form.retry_rules),
    voicemail_config: parseJsonObject('Voicemail JSON', form.voicemail_config),
    handoff_rules: parseJsonObject('Handoff Rules JSON', form.handoff_rules),
    crm_mapping: parseJsonObject('CRM Mapping JSON', form.crm_mapping),
    llm_config: {
      llm_provider: 'openai',
      llm_model: form.llm_model
    },
    tts_config: {
      tts_provider: 'aether_voice',
      tts_model: resolvedTtsModel(form.tts_model_select, form.custom_tts_model) || 'kokoro_realtime',
      tts_voice: resolvedVoice(form.tts_voice_select, form.custom_tts_voice) || 'af_bella'
    }
  };
}

export default function OutboundPage() {
  const [campaigns, setCampaigns] = useState([]);
  const [agents, setAgents] = useState([]);
  const [phoneNumbers, setPhoneNumbers] = useState([]);
  const [llmModels, setLlmModels] = useState([]);
  const [voices, setVoices] = useState(DEFAULT_VOICE_OPTIONS);
  const [editingCampaignId, setEditingCampaignId] = useState('');
  const [form, setForm] = useState(defaultOutboundForm());
  const [message, setMessage] = useState('');

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const [campaignList, agentList, numberList, modelList, voiceList] = await Promise.all([
        api('/campaigns/outbound').catch(() => []),
        api('/agents'),
        api('/phone-numbers'),
        api('/llm/models').catch(() => []),
        api('/tts/voices').catch(() => DEFAULT_VOICE_OPTIONS)
      ]);
      setCampaigns(campaignList || []);
      setAgents(agentList || []);
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

  async function submitForm(e) {
    e.preventDefault();
    try {
      const payload = buildCampaignPayload(form);
      if (editingCampaignId) {
        await api(`/campaigns/outbound/${editingCampaignId}`, {
          method: 'PUT',
          body: JSON.stringify(payload)
        });
        setMessage(`Outbound campaign ${payload.name} saved.`);
      } else {
        const created = await api('/campaigns/outbound', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        setEditingCampaignId(created.id);
        setMessage(`Outbound campaign ${created.name} created.`);
      }
      await load();
    } catch (err) {
      setMessage(err.message);
    }
  }

  function loadCampaign(campaign) {
    setEditingCampaignId(campaign.id);
    setForm(formFromCampaign(campaign, voices));
    setMessage(`Loaded outbound campaign ${campaign.name}.`);
  }

  const selectedTtsModel = resolvedTtsModel(form.tts_model_select, form.custom_tts_model);
  const voiceOptions = buildVoiceOptions(compatibleVoices(voices, selectedTtsModel));
  const modelOptions = buildLlmModelOptions(llmModels, form.llm_model);

  return (
    <main className="container">
      <Nav />
      <h1>Outbound Campaign Builder</h1>
      <section className="card" style={{ marginBottom: 16 }}>
        <strong>Operator Intent</strong>
        <p>
          Build outbound campaigns as a separate lane from inbound answering. Save campaign objective, qualification,
          retry behavior, CRM mapping, and runtime selection in one place.
        </p>
      </section>

      <div className="grid-2">
        <section className="card">
          <h2>{editingCampaignId ? 'Edit Outbound Campaign' : 'Create Outbound Campaign'}</h2>
          <form onSubmit={submitForm}>
            <label>Campaign Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />

            <label>Assigned Agent</label>
            <select value={form.agent_id} onChange={(e) => setForm({ ...form, agent_id: e.target.value })}>
              <option value="">Select agent</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>

            <label>Caller ID Number</label>
            <select
              value={form.caller_id_number}
              onChange={(e) => setForm({ ...form, caller_id_number: e.target.value })}
            >
              <option value="">Default platform number</option>
              {phoneNumbers.map((row) => (
                <option key={row.id} value={row.phone_number}>
                  {row.phone_number}
                </option>
              ))}
            </select>

            <label>Lead Source</label>
            <input value={form.lead_source} onChange={(e) => setForm({ ...form, lead_source: e.target.value })} />

            <label>Objective</label>
            <textarea value={form.objective} onChange={(e) => setForm({ ...form, objective: e.target.value })} />

            <label>Opening Line</label>
            <textarea value={form.opening_line} onChange={(e) => setForm({ ...form, opening_line: e.target.value })} />

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

            <label>Qualification Fields JSON</label>
            <textarea
              value={form.qualification_fields}
              onChange={(e) => setForm({ ...form, qualification_fields: e.target.value })}
            />

            <label>Objection Guidance</label>
            <textarea
              value={form.objection_guidance}
              onChange={(e) => setForm({ ...form, objection_guidance: e.target.value })}
            />

            <label>Booking Target</label>
            <input value={form.booking_target} onChange={(e) => setForm({ ...form, booking_target: e.target.value })} />

            <label>Retry Rules JSON</label>
            <textarea value={form.retry_rules} onChange={(e) => setForm({ ...form, retry_rules: e.target.value })} />

            <label>Voicemail JSON</label>
            <textarea
              value={form.voicemail_config}
              onChange={(e) => setForm({ ...form, voicemail_config: e.target.value })}
            />

            <label>Handoff Rules JSON</label>
            <textarea
              value={form.handoff_rules}
              onChange={(e) => setForm({ ...form, handoff_rules: e.target.value })}
            />

            <label>CRM Mapping JSON</label>
            <textarea value={form.crm_mapping} onChange={(e) => setForm({ ...form, crm_mapping: e.target.value })} />

            <button type="submit">{editingCampaignId ? 'Save Outbound Campaign' : 'Create Outbound Campaign'}</button>
          </form>
        </section>

        <section className="card">
          <h2>Existing Campaigns</h2>
          {campaigns.length ? (
            campaigns.map((campaign) => (
              <div key={campaign.id} className="card" style={{ marginBottom: 12 }}>
                <div><strong>{campaign.name}</strong></div>
                <div>Agent: {agents.find((agent) => agent.id === campaign.agent_id)?.name || 'Unassigned'}</div>
                <div>Lead source: {campaign.lead_source || 'Not set'}</div>
                <div>Live model: {campaign.llm_config?.llm_model || 'Not set'}</div>
                <div>TTS lane: {campaign.tts_config?.tts_model || 'Not set'}</div>
                <div>Caller ID: {campaign.caller_id_number || 'Default platform number'}</div>
                <button className="secondary" onClick={() => loadCampaign(campaign)}>
                  Edit Outbound Campaign
                </button>
              </div>
            ))
          ) : (
            <div>No outbound campaigns saved yet.</div>
          )}
        </section>
      </div>

      <section className="card" style={{ marginTop: 16 }}>
        {message || 'Ready.'}
      </section>
    </main>
  );
}

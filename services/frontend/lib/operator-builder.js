export const TTS_MODEL_OPTIONS = [
  { id: 'kokoro_realtime', label: 'Kokoro Realtime', provider: 'aether_voice' },
  { id: 'voxtream2_realtime', label: 'Voxtream2 Realtime', provider: 'aether_voice' },
  { id: 'qwen_customvoice', label: 'Qwen Custom Voice Batch', provider: 'aether_voice' },
  { id: 'qwen_customvoice_streaming', label: 'Qwen Custom Voice Streaming', provider: 'aether_voice' },
  { id: 'qwen_voice_design', label: 'Qwen Voice Design', provider: 'aether_voice' }
];

const QWEN_PROVIDER_MODELS = ['qwen_customvoice', 'qwen_customvoice_streaming', 'qwen_voice_design'];

export const DEFAULT_VOICE_OPTIONS = [
  { id: 'af_bella', label: 'Bella', family: 'kokoro_realtime', gender: 'female', style_tag: 'warm', provider: 'aether_voice', models: ['kokoro_realtime'], is_default: true },
  { id: 'af_heart', label: 'Heart', family: 'kokoro_realtime', gender: 'female', style_tag: 'bright', provider: 'aether_voice', models: ['kokoro_realtime'], is_default: false },
  { id: 'af_nicole', label: 'Nicole', family: 'kokoro_realtime', gender: 'female', style_tag: 'confident', provider: 'aether_voice', models: ['kokoro_realtime'], is_default: false },
  { id: 'af_sarah', label: 'Sarah', family: 'kokoro_realtime', gender: 'female', style_tag: 'clear', provider: 'aether_voice', models: ['kokoro_realtime'], is_default: false },
  { id: 'am_adam', label: 'Adam', family: 'kokoro_realtime', gender: 'male', style_tag: 'steady', provider: 'aether_voice', models: ['kokoro_realtime'], is_default: false },
  { id: 'qwen_vivian', label: 'Vivian', family: 'qwen_customvoice', gender: 'female', style_tag: 'polished', provider: 'aether_voice', models: QWEN_PROVIDER_MODELS, is_default: false },
  { id: 'qwen_serena', label: 'Serena', family: 'qwen_customvoice', gender: 'female', style_tag: 'calm', provider: 'aether_voice', models: QWEN_PROVIDER_MODELS, is_default: false },
  { id: 'qwen_ryan', label: 'Ryan', family: 'qwen_customvoice', gender: 'male', style_tag: 'clear', provider: 'aether_voice', models: QWEN_PROVIDER_MODELS, is_default: false }
];

const CUSTOM_TTS_MODEL_OPTION = { id: '__custom__', label: 'Custom TTS Model' };
const CUSTOM_VOICE_OPTION = { id: '__custom__', label: 'Custom Voice' };

export const seedInboundRequiredFields = {
  intent: { prompt: 'What are you calling about today?' },
  name: { prompt: 'Can I have your full name?' },
  callback_number: { prompt: 'What is the best callback number in case we get disconnected?' }
};

export function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

export function parseJsonObject(label, value) {
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

export function tryParseJsonObject(label, value) {
  try {
    return {
      value: parseJsonObject(label, value),
      error: ''
    };
  } catch (err) {
    return {
      value: null,
      error: err.message
    };
  }
}

export function validateInboundJsonFields(form) {
  const requiredFields = tryParseJsonObject('Required Fields JSON', form.required_fields);
  const actionConfig = tryParseJsonObject('Action Execution JSON', form.action_config);
  const crmMapping = tryParseJsonObject('CRM Mapping JSON', form.crm_mapping);
  const fsmConfig = tryParseJsonObject('FSM Config JSON', form.fsm_config);

  const errors = {
    required_fields: requiredFields.error,
    action_config: actionConfig.error,
    crm_mapping: crmMapping.error,
    fsm_config: fsmConfig.error
  };

  if (!errors.required_fields && requiredFields.value) {
    for (const [fieldName, config] of Object.entries(requiredFields.value)) {
      if (!config || typeof config !== 'object' || Array.isArray(config)) {
        errors.required_fields = `Required Fields JSON field "${fieldName}" must map to an object.`;
        break;
      }
      if (typeof config.prompt !== 'string' || !config.prompt.trim()) {
        errors.required_fields = `Required Fields JSON field "${fieldName}" must include a non-empty prompt string.`;
        break;
      }
    }
  }

  if (!errors.crm_mapping && crmMapping.value) {
    for (const [bucket, mappedFields] of Object.entries(crmMapping.value)) {
      if (!Array.isArray(mappedFields)) {
        errors.crm_mapping = `CRM Mapping JSON key "${bucket}" must map to an array of field names.`;
        break;
      }
      if (mappedFields.some((value) => typeof value !== 'string' || !value.trim())) {
        errors.crm_mapping = `CRM Mapping JSON key "${bucket}" must contain only non-empty string field names.`;
        break;
      }
    }
  }

  const hasErrors = Object.values(errors).some(Boolean);

  return {
    errors,
    hasErrors
  };
}

export function buildLlmModelOptions(models, selectedModel) {
  const options = [];
  for (const model of models || []) {
    if (typeof model === 'string' && model.trim() && !options.includes(model.trim())) {
      options.push(model.trim());
    }
  }
  if (selectedModel && !options.includes(selectedModel)) {
    options.push(selectedModel);
  }
  return options;
}

export function ttsModelOptions() {
  return [...TTS_MODEL_OPTIONS, CUSTOM_TTS_MODEL_OPTION];
}

export function voiceLabel(voice) {
  const suffix = [voice.gender, voice.style_tag].filter(Boolean).join(', ');
  const modelHint = Array.isArray(voice.models) && voice.models.length ? `, ${voice.models.join(' / ')}` : '';
  return voice.is_default
    ? `${voice.label} (${voice.id}, default${modelHint})`
    : `${voice.label} (${voice.id}${suffix ? `, ${suffix}` : ''}${modelHint})`;
}

export function resolvedTtsModel(modelSelect, customModel) {
  return modelSelect === '__custom__' ? customModel.trim() : modelSelect;
}

export function resolvedVoice(voiceSelect, customVoice) {
  return voiceSelect === '__custom__' ? customVoice.trim() : voiceSelect;
}

export function voiceSupportsModel(voice, model) {
  if (!model) return true;
  if (Array.isArray(voice.models) && voice.models.length) {
    return voice.models.includes(model);
  }
  return voice.family === model;
}

export function compatibleVoices(voices, model) {
  return voices.filter((voice) => voiceSupportsModel(voice, model));
}

export function buildVoiceOptions(voices) {
  return [...voices, CUSTOM_VOICE_OPTION];
}

export function defaultInboundForm() {
  return {
    name: '',
    assigned_number_id: '',
    greeting_mode: 'tts_fixed',
    opening_greeting: '',
    persona: '',
    script: '',
    required_fields: prettyJson(seedInboundRequiredFields),
    action_config: prettyJson({
      transfer_call: true,
      send_sms: true,
      schedule_appointment: true,
      create_or_update_contact: true
    }),
    crm_mapping: prettyJson({
      contact: ['name', 'callback_number'],
      note: ['intent']
    }),
    human_transfer_enabled: false,
    human_transfer_trigger_mode: 'explicit_or_keyword',
    human_transfer_keywords: 'human, representative, real person, operator, manager, sales, transfer me',
    human_transfer_destination_type: 'phone_number',
    human_transfer_destination: '',
    human_transfer_label: 'Front Desk',
    human_transfer_confirmation_message: 'Absolutely. I will transfer you to a team member now.',
    human_transfer_no_answer_fallback: 'return_to_ai',
    human_transfer_ring_timeout_seconds: 20,
    llm_model: '',
    tts_model_select: 'kokoro_realtime',
    custom_tts_model: '',
    tts_voice_select: 'af_bella',
    custom_tts_voice: '',
    fsm_config: prettyJson({})
  };
}

export function defaultOutboundForm() {
  return {
    name: '',
    agent_id: '',
    caller_id_number: '',
    lead_source: '',
    objective: '',
    opening_line: '',
    qualification_fields: prettyJson({
      company: { prompt: 'Which company are you with?' },
      interest: { prompt: 'What are you hoping to solve?' }
    }),
    objection_guidance: '',
    booking_target: '',
    retry_rules: prettyJson({ max_attempts: 3, spacing_minutes: [15, 180, 1440] }),
    voicemail_config: prettyJson({ enabled: true, drop_message: false }),
    handoff_rules: prettyJson({ transfer_on_request: true }),
    crm_mapping: prettyJson({ contact: ['company'], opportunity: ['interest'] }),
    llm_model: '',
    tts_model_select: 'kokoro_realtime',
    custom_tts_model: '',
    tts_voice_select: 'af_bella',
    custom_tts_voice: ''
  };
}

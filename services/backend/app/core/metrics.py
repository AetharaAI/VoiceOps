from prometheus_client import Counter, Histogram

CALLS_STARTED = Counter('voiceops_calls_started_total', 'Total calls started', ['tenant_id', 'direction'])
CALLS_COMPLETED = Counter('voiceops_calls_completed_total', 'Total calls completed', ['tenant_id', 'status'])
ASR_LATENCY = Histogram('voiceops_asr_latency_seconds', 'ASR latency seconds')
TTS_LATENCY = Histogram('voiceops_tts_latency_seconds', 'TTS latency seconds')
LLM_LATENCY = Histogram('voiceops_llm_latency_seconds', 'LLM latency seconds')

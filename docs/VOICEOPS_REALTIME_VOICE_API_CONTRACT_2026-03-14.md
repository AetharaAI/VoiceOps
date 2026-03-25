# VoiceOps Realtime Voice API Contract

This note is the external integration handoff for the separate `VoiceOps` / telephony repo.

It defines the current known-good public contract for:

1. realtime ASR through the gateway-backed Voxtral lane
2. realtime TTS through the gateway-backed Kokoro lane
3. optional server-side turn mode through `/v1/voice/turn`

This is the contract the VoiceOps repo should implement against.

## Non-negotiable Rule

Do not connect VoiceOps directly to:

- the internal Voxtral container
- the internal Kokoro sidecar
- the internal TTS service

Use the public gateway contract only.

That is the stable interface.

## Current Product Split

For the VoiceOps repo, the clean split is:

- Aether Voice handles speech infrastructure
  - realtime ASR
  - realtime TTS
  - optional server-side turn mode
- VoiceOps handles agent behavior
  - telephony session state
  - tool calling
  - business routing
  - LLM / agent orchestration

Recommended primary integration:

`caller audio -> ASR -> VoiceOps agent/LLM -> Kokoro realtime TTS`

Optional shortcut:

`final transcript -> /v1/voice/turn`

Use the shortcut only if you want Aether Voice to own the LLM hop for that turn.

## Base URLs

Current deployed working surface:

- HTTP base: `https://asr.aetherpro.us/api`
- WebSocket base: `wss://asr.aetherpro.us`

If VoiceOps later fronts the same gateway on another hostname, keep the paths identical and only swap the base URL.

## Auth

Current gateway mode allows:

- no auth in optional mode
- `X-API-Key: <key>`
- `Authorization: Bearer <valid JWT>`

Important:

- do not send a stale bearer token
- if VoiceOps does not have a valid JWT or API key yet, omit `Authorization`

## Part 1: Realtime ASR Contract

### Start ASR stream

`POST /v1/asr/stream/start`

Example:

```http
POST https://asr.aetherpro.us/api/v1/asr/stream/start
Content-Type: application/json
```

```json
{
  "model": "auto",
  "language": "auto",
  "sample_rate": 16000,
  "encoding": "pcm_s16le",
  "channels": 1,
  "triage_enabled": false,
  "metadata": {
    "source": "voiceops_call_ingest",
    "extra": {
      "surface": "voiceops",
      "mode": "live_call",
      "call_id": "call_123"
    }
  }
}
```

Expected response:

```json
{
  "session_id": "sess_live_...",
  "ws_url": "/api/v1/asr/stream/sess_live_...",
  "expires_in_seconds": 3600,
  "model_requested": "auto",
  "model_used": "voxtral_realtime",
  "fallback_used": false
}
```

### Open ASR websocket

Resolve the returned `ws_url` against the websocket base:

- `wss://asr.aetherpro.us/api/v1/asr/stream/{session_id}`

### Send ASR audio frames

VoiceOps must send JSON messages shaped like:

```json
{
  "type": "audio_frame",
  "seq": 1,
  "timestamp_ms": 0,
  "sample_rate": 16000,
  "encoding": "pcm_s16le",
  "channels": 1,
  "payload_b64": "<base64 raw pcm16 little-endian bytes>"
}
```

ASR input contract:

- `16000 Hz`
- `pcm_s16le`
- mono only
- `payload_b64` is raw PCM bytes, not WAV

### End ASR stream

When the caller turn is complete, send:

```json
{
  "type": "end_stream"
}
```

Do not just drop the socket if you want the final transcript.

### ASR events VoiceOps must handle

Partial transcript:

```json
{
  "type": "partial_transcript",
  "session_id": "sess_live_...",
  "seq": 12,
  "stable": false,
  "text": "partial text here",
  "start_ms": 0,
  "end_ms": 1440
}
```

Final transcript:

```json
{
  "type": "final_transcript",
  "session_id": "sess_live_...",
  "text": "final normalized transcript here",
  "segments": [
    {
      "segment_id": "seg_1",
      "start_ms": 0,
      "end_ms": 3120,
      "text": "final normalized transcript here"
    }
  ]
}
```

VoiceOps behavior:

- use `partial_transcript` only for live UI or early agent hints
- treat `final_transcript` as the source of truth for the turn

## Part 2: Realtime Kokoro TTS Contract

This is the new live reply lane.

### Start TTS stream

`POST /v1/tts/stream/start`

Example:

```http
POST https://asr.aetherpro.us/api/v1/tts/stream/start
Content-Type: application/json
```

```json
{
  "model": "kokoro_realtime",
  "voice": "af_sky",
  "sample_rate": 24000,
  "format": "wav",
  "context_mode": "conversation",
  "metadata": {
    "source": "voiceops_live_reply",
    "extra": {
      "surface": "voiceops",
      "call_id": "call_123",
      "agent_id": "agent_abc"
    }
  }
}
```

Expected response:

```json
{
  "session_id": "sess_tts_live_...",
  "ws_url": "/api/v1/tts/stream/sess_tts_live_...",
  "model_requested": "kokoro_realtime",
  "model_used": "kokoro_realtime",
  "fallback_used": false,
  "runtime": {
    "requested_route": "kokoro_realtime",
    "runtime_path_used": "kokoro_realtime",
    "live_chunk_source_route": "kokoro_realtime",
    "final_artifact_source_route": "kokoro_realtime",
    "selected_voice_id": "af_sky",
    "selected_voice_asset": "Sky",
    "requested_preset": "af_sky",
    "actual_runtime_conditioning_source": "af_sky",
    "conditioning_active": true,
    "fallback_route_used": null,
    "notes": []
  }
}
```

### Open TTS websocket

Resolve the returned `ws_url` against the websocket base:

- `wss://asr.aetherpro.us/api/v1/tts/stream/{session_id}`

### Send reply text

VoiceOps sends one or more text chunks:

```json
{
  "type": "text_chunk",
  "text": "Thank you for calling Aether Pro Technologies."
}
```

Then seal the text stream:

```json
{
  "type": "text_complete"
}
```

Then request final audio flush:

```json
{
  "type": "end_stream"
}
```

Important:

- the current live lane is still one reply utterance per stream
- open a new TTS stream for the next agent reply
- do not treat the websocket as an infinite full-duplex conversation socket yet

### TTS events VoiceOps must handle

Realtime chunk:

```json
{
  "type": "audio_chunk",
  "session_id": "sess_tts_live_...",
  "sequence": 1,
  "audio_b64": "<base64 wav bytes>",
  "format": "wav",
  "metadata": {
    "runtime": {
      "runtime_path_used": "kokoro_realtime"
    },
    "live_chunk_source_route": "kokoro_realtime"
  }
}
```

Final audio:

```json
{
  "type": "final_audio",
  "session_id": "sess_tts_live_...",
  "audio_b64": "<base64 wav bytes>",
  "format": "wav",
  "metadata": {
    "audio_url": "/api/v1/tts/artifacts/download?uri=...",
    "runtime": {
      "runtime_path_used": "kokoro_realtime"
    },
    "live_chunk_source_route": "kokoro_realtime",
    "final_artifact_source_route": "kokoro_realtime",
    "fallback_route_used": null
  }
}
```

Error event:

```json
{
  "type": "error",
  "session_id": "sess_tts_live_...",
  "message": "..."
}
```

### Voice contract

Current built-in Kokoro presets exposed in the shared registry include:

- `af_sky`
- `af_bella`
- `af_heart`
- `af_nicole`
- `af_sarah`
- `am_adam`
- `am_michael`
- `bf_emma`
- `bf_isabella`
- `bm_george`
- `bm_lewis`

Current default fast voice:

- `af_sky`

### TTS output contract

Current live output is:

- `24000 Hz`
- `wav`

If VoiceOps is feeding telephony media streams, it should transcode the returned WAV chunks/final audio into the codec required by the telephony edge.

## Part 3: Optional Server-Side Turn Shortcut

If VoiceOps wants to skip owning the LLM hop temporarily, it can call:

`POST /v1/voice/turn`

Example:

```http
POST https://asr.aetherpro.us/api/v1/voice/turn
Content-Type: application/json
```

```json
{
  "transcript_text": "Thank you for calling. I need help with my electrical panel.",
  "voice": "af_sky",
  "tts_model": "kokoro_realtime",
  "format": "wav",
  "sample_rate": 24000,
  "metadata": {
    "source": "voiceops_server_turn",
    "extra": {
      "surface": "voiceops",
      "call_id": "call_123"
    }
  }
}
```

Expected response shape:

```json
{
  "request_id": "req_...",
  "session_id": "sess_voice_...",
  "transcript_text": "...",
  "response_text": "...",
  "llm_provider": "litellm",
  "llm_model_requested": "minicpm-v",
  "llm_model_used": "minicpm-v",
  "tts_model_requested": "kokoro_realtime",
  "tts_model_used": "kokoro_realtime",
  "audio_url": "/api/v1/tts/artifacts/download?uri=...",
  "duration_ms": 1800,
  "llm_timings": {
    "total_ms": 915
  },
  "tts_timings": {
    "total_ms": 225
  },
  "timings": {
    "llm_ms": 915,
    "tts_ms": 225,
    "total_ms": 1140
  },
  "artifacts": {
    "tts_mode": "streaming",
    "tts_first_chunk_ms": 225,
    "tts_chunk_events": 3
  }
}
```

Important:

- this route currently waits for the finalized transcript
- then runs the saved backend LLM route
- then runs Kokoro live synthesis internally if `tts_model` is a realtime lane

That is a good fast baseline, but it is not the same thing as VoiceOps owning the agent loop.

## Recommended VoiceOps Rollout

### Phase 1

- integrate realtime ASR
- verify final transcript handling per caller turn

### Phase 2

- keep the agent/LLM inside VoiceOps
- start a Kokoro TTS stream per reply turn
- play audio chunks as they arrive
- flush final audio and close the stream

### Phase 3

- add interruption / barge-in control
- add partial-transcript driven early agent planning
- only then consider true duplex speech orchestration

## Current Truth About Realtime

What is working now:

- realtime ASR is production-promising
- Kokoro realtime TTS is fast and operator-verified
- the current `ASR Live` page now proves `ASR -> LLM -> Kokoro` turn mode end-to-end

What is not yet the contract:

- a single always-open bidirectional agent conversation socket
- full duplex overlapping ASR partials, LLM generation, and TTS barge-in on one session

VoiceOps should therefore model the current system as turn-based realtime infrastructure, not yet full duplex agent speech.

## Leakage / Output Sanitization

If VoiceOps owns the LLM step, sanitize the agent text before sending it to TTS.

At minimum strip:

- `<think>...</think>`
- `<tool_call>...</tool_call>`
- reserved control tokens

The server-side `/v1/voice/turn` path already does this cleanup before handing text to TTS.

## Repo References

- [POLYMORPH_REALTIME_ASR_BACKEND_INTEGRATION.md](/home/cory/Aether-Voice-Platform/Aether-Voice-X/POLYMORPH_REALTIME_ASR_BACKEND_INTEGRATION.md)
- [POLYMORPH_VOICE_INTEGRATION_NOTE-03-11-2026.md](/home/cory/Aether-Voice-Platform/Aether-Voice-X/POLYMORPH_VOICE_INTEGRATION_NOTE-03-11-2026.md)
- [services/gateway/app/routers/asr.py](/home/cory/Aether-Voice-Platform/Aether-Voice-X/services/gateway/app/routers/asr.py)
- [services/gateway/app/routers/tts.py](/home/cory/Aether-Voice-Platform/Aether-Voice-X/services/gateway/app/routers/tts.py)
- [services/gateway/app/routers/voice.py](/home/cory/Aether-Voice-Platform/Aether-Voice-X/services/gateway/app/routers/voice.py)
- [services/frontend/src/hooks/useASRStream.ts](/home/cory/Aether-Voice-Platform/Aether-Voice-X/services/frontend/src/hooks/useASRStream.ts)
- [services/frontend/src/hooks/useTTSStream.ts](/home/cory/Aether-Voice-Platform/Aether-Voice-X/services/frontend/src/hooks/useTTSStream.ts)

## One-Line Instruction For The VoiceOps Repo

Implement the external agent loop as:

`start ASR stream -> receive final transcript -> run VoiceOps agent/LLM -> start Kokoro TTS stream -> send reply text -> play audio chunks -> end stream`

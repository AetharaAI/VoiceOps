# Voice Substrate API Integration Runbook

## Purpose

This is the integration runbook for wiring another app into the current Aether voice substrate after MOSS decommission and Qwen Phase 1 integration.

Primary consumer examples:
- `Polymorph`
- telephony voice-agent app
- future public `studio.aetherpro.us`

## System Split

`AetherVoice-X` owns:
- gateway contracts
- ASR, TTS, and voice-turn orchestration
- studio voice registry and routing
- operator pages like `ASR Live` and `TTS Live`

`qwen-experiments` owns:
- the external `qwen-provider` service
- Qwen batch and streaming provider contracts
- Qwen load, warmup, and chunking behavior

`voxtream-experiments` owns:
- the external `voxtream2-provider` service
- Voxtream2 warmup and stream lifecycle behavior
- zero-shot reference-audio runtime proof

Rule:
- if another app needs platform behavior, integrate with `AetherVoice-X`
- if another app needs raw Qwen provider behavior, integrate with `qwen-provider`

## Network Topology

Shared Docker network:
- `aether-voice-mesh`

Current service roles:
- `gateway`: public/internal orchestration surface
- `tts`: internal TTS service behind gateway
- `asr`: internal ASR service behind gateway
- `qwen-provider`: external Qwen provider sidecar on shared mesh

## Integration Options

### 1. Recommended: Gateway-first integration

Use this when the external app wants the same platform behavior the operator UI uses.

Main benefits:
- one auth surface
- one routing surface
- voice registry aware
- session and artifact tracking
- future-proof against provider swaps

Key endpoints:
- `POST /v1/asr/transcribe`
- `POST /v1/asr/stream/start`
- `POST /v1/tts/synthesize`
- `POST /v1/tts/stream/start`
- `POST /v1/voice/turn`
- `GET /v1/tts/studio/overview`
- `GET /v1/tts/studio/voices`
- `POST /v1/tts/studio/routes/{route_name}/warmup`

### 2. Direct provider integration

Use this only when you explicitly want to test or own Qwen provider behavior outside the platform.

Key provider endpoints:
- `GET /health`
- `GET /v1/models`
- `GET /v1/voices`
- `POST /v1/warmup`
- `POST /v1/audio/speech`
- `POST /v1/stream/start`
- `POST /v1/stream/{session_id}/text`
- `POST /v1/stream/{session_id}/complete`
- `POST /v1/stream/{session_id}/end`

## Current TTS Lanes

### `kokoro_realtime`

- native live streaming lane
- best current low-latency route
- preferred telephony baseline

### `voxtream2_realtime`

- external provider-backed realtime lane (`voxtream2-provider`)
- requires a bound reference-audio asset
- exposes dynamic speaking-rate control through TTS Live and stream metadata
- first-run warmup is expected after container restarts or image refreshes

### `qwen_customvoice`

- stable provider-backed batch lane
- best current route for premium voice quality, asset generation, and quality evaluation
- also exposed on `TTS Live` as `batch-backed live`

### `qwen_customvoice_streaming`

- sibling streaming lane
- intended for first-chunk, chunk-cadence, and live-lane testing
- should be compared directly against both `kokoro_realtime` and `qwen_customvoice`

### `qwen_voice_design`

- prompt-driven batch lane for creating new voice assets
- intended for `TTS Studio -> Voice Design`
- should be used to generate reusable assets before any promotion into live telephony lanes

## Voice Inventory

Current seeded Qwen built-in voices:
- `qwen_ryan`
- `qwen_aiden`
- `qwen_serena`
- `qwen_vivian`
- `qwen_uncle_fu`
- `qwen_sohee`
- `qwen_dylan`
- `qwen_eric`
- `qwen_ono_anna`

Current practical grouping rule:
- `voice_id` starts with `qwen_` => Qwen preset
- `runtime_target === "kokoro_realtime"` => Kokoro preset
- `runtime_target === "qwen_voice_design"` => prompt-driven Qwen studio asset
- `runtime_target === "chatterbox"` => Chatterbox fallback

## Recommended Telephony Integration Path

For the telephony app, integrate against gateway first.

### Batch probe

Use:
- `POST /v1/tts/synthesize`

Example:

```json
{
  "model": "qwen_customvoice",
  "voice": "qwen_serena",
  "text": "Thanks for calling Aether. How can I help you today?",
  "format": "wav",
  "sample_rate": 24000,
  "stream": false,
  "style": {
    "speed": 1.0,
    "emotion": "calm",
    "speaker_hint": "Serena"
  },
  "metadata": {
    "source": "telephony",
    "lane": "batch_probe",
    "extra": {
      "qwen_instructions": "Speak in a calm, telephony-friendly style."
    }
  }
}
```

### Live stream probe

Use:
- `POST /v1/tts/stream/start`
- then the websocket returned by `ws_url`

Start payload:

```json
{
  "model": "qwen_customvoice_streaming",
  "voice": "qwen_serena",
  "sample_rate": 24000,
  "format": "wav",
  "context_mode": "conversation",
  "metadata": {
    "source": "telephony",
    "lane": "live_probe",
    "extra": {
      "qwen_instructions": "Speak in a calm, telephony-friendly style."
    }
  }
}
```

### Voice design probe

Use:
- `POST /v1/tts/synthesize`

Example:

```json
{
  "model": "qwen_voice_design",
  "voice": "qwen_serena",
  "text": "Thank you for calling Aether Voice. How may I assist you today?",
  "format": "wav",
  "sample_rate": 24000,
  "stream": false,
  "metadata": {
    "source": "studio",
    "lane": "voice_design_probe",
    "extra": {
      "generation_prompt": "Warm American female receptionist voice with clear diction, natural cadence, and polished phone presence."
    }
  }
}
```

WebSocket messages sent by client:

```json
{ "type": "text_chunk", "text": "Hello and thanks for calling Aether." }
```

```json
{ "type": "text_complete" }
```

```json
{ "type": "end_stream" }
```

WebSocket messages returned by platform:

```json
{
  "type": "audio_chunk",
  "session_id": "sess_tts_live_...",
  "sequence": 1,
  "audio_b64": "...",
  "format": "wav",
  "metadata": {
    "runtime": {
      "runtime_path_used": "qwen_customvoice_streaming"
    }
  }
}
```

```json
{
  "type": "final_audio",
  "session_id": "sess_tts_live_...",
  "audio_b64": "...",
  "format": "wav",
  "metadata": {
    "audio_url": "/api/v1/tts/artifacts/download?...",
    "runtime": {
      "runtime_path_used": "qwen_customvoice_streaming"
    }
  }
}
```

## What To Measure

For real telephony qualification, capture:
- request start time
- first LLM token time
- first TTS chunk time
- final audio ready time
- end-to-end turn latency
- audio duration
- interruption behavior
- quality vs Kokoro
- cadence control quality as `speaking_rate` changes

Do not promote the Qwen streaming lane into production telephony until it beats or justifies itself against `kokoro_realtime`.

## Voxtream2 Warmup And Speaking Rate

Warmup path from the platform:

```bash
curl -sS -X POST \
  http://127.0.0.1:8010/api/v1/tts/studio/routes/voxtream2_realtime/warmup \
  -H "X-Tenant-Id: default" \
  | jq '{route, warmup}'
```

Notes:
- Without `jq`, this endpoint also returns full studio overview payload by design.
- The warmup block is the signal to trust (`status`, `model`, `elapsed_ms`).
- TTS Live now exposes a `Warm up` button for Voxtream routes so operators do not need this curl during normal testing.

Provider-direct warmup (debug lane only):

```bash
curl -sS -X POST \
  http://127.0.0.1:8075/v1/warmup \
  -H "Content-Type: application/json" \
  -d '{"model":"voxtream2_realtime"}'
```

Speaking-rate control contract:
- set `realtime_profile.speaking_rate` or `realtime_tuning.speaking_rate` at stream start
- provider receives `speaking_rate` in `/v1/stream/start`
- current safe operator range is `0.5` to `5.0` with `2.0` as default

## Operator Verification

Main docs:
- `GET /v1/models`
- `GET /v1/tts/studio/overview`

Provider docs:
- `GET /v1/models`
- `GET /v1/voices`
- `GET /health`

Expected truths:
- `qwen_customvoice` present and ready
- `qwen_customvoice_streaming` present and ready
- `qwen_voice_design` present and ready
- `TTS Live` dropdown shows both Qwen lanes
- Qwen voices appear under both Qwen entries

## Narrow Rebuild Rules

If only provider runtime changed:

```bash
cd ~/aetherpro/voice-x/experiments/qwen-experiments
docker compose up -d --build qwen-provider
```

If only TTS backend changed:

```bash
cd ~/aetherpro/voice-x/AetherVoice-X
docker compose up -d --build --no-deps tts
```

If only frontend changed:

```bash
cd ~/aetherpro/voice-x/AetherVoice-X
docker compose up -d --build --no-deps frontend
```

If a wider stack pass is needed:

```bash
cd ~/aetherpro/voice-x/AetherVoice-X
COMPOSE_PROFILES=voxtral,kokoro docker compose up -d --build
```

## Current Recommendation

Short-term:
- keep `kokoro_realtime` as the production telephony baseline
- keep `qwen_customvoice` for premium batch quality and asset generation
- use `qwen_customvoice_streaming` as the live evaluation lane
- use `qwen_voice_design` in studio for creating reusable voice assets, not as an always-hot live lane

Promotion bar:
- only move telephony toward Qwen streaming after repeatable live probes show acceptable first-audio latency, chunk behavior, and quality.

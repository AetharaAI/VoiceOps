# VoiceOps Gateway Truth Snapshot — 2026-03-16

Purpose: canonical handoff doc for the VoiceOps repo so Codex can work from verified gateway behavior instead of terminal archaeology.

## What is verified right now

The unified LiteLLM gateway at `https://api.aetherpro.tech/v1` responds to `GET /models` and returns the current canonical model list. Verified working model calls through the gateway now include:

- `qwen3.5-122`
- `omnicoder`
- `minicpm-v`

Verified interaction modes from the test run:

- `qwen3.5-122`: streaming request reached the model and returned SSE output.
- `omnicoder`: non-streaming works.
- `omnicoder`: streaming works.
- `minicpm-v`: non-streaming works.
- `minicpm-v`: streaming works.

An earlier `minicpm-v` failure was auth/config related, not evidence of random routing. Passing the model-specific key as the external bearer token failed because the proxy expects a valid proxy token, not that upstream model key.

## Canonical model list from the gateway

Treat this as canonical until changed deliberately in the gateway:

- `qwen3.5-35b`
- `qwen3.5-122`
- `qwen3.5-9b`
- `omnicoder`
- `devstral-123b`
- `qwen3.5-4b`
- `qwen3.5-2b`
- `qwen3.5-9b-h`
- `jan-code-4b`
- `nanbeige4-3b-thinking`
- `minicpm-v`
- `redqwen-vl`
- `cisco-sec`
- `vulnllm-r-7b`
- `phi-4-instruct`

## Canonical API shape for VoiceOps

Base URL:

```bash
https://api.aetherpro.tech/v1
```

OpenAI-compatible endpoints in use:

```bash
GET /models
POST /chat/completions
```

Client pattern:

- Send one valid proxy bearer token in the `Authorization` header.
- Send the desired model name in the JSON body as `"model": "..."`.
- Do not use a model-specific upstream key as the external bearer token.

## Proven request patterns

### 1) List models

```bash
curl -sS "${API_BASE}/models" \
  -H "Authorization: Bearer ${API_KEY}"
```

### 2) Omnicoder non-streaming

```bash
curl -sS "${API_BASE}/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "omnicoder",
    "stream": false,
    "temperature": 0,
    "max_tokens": 24,
    "messages": [
      {"role": "system", "content": "You are a routing test. Reply with exactly: ROUTE_OK MODEL_2 NONSTREAM"},
      {"role": "user", "content": "trace=model2_nonstream"}
    ]
  }'
```

Expected behavior: normal JSON response with assistant message content `ROUTE_OK MODEL_2 NONSTREAM`.

### 3) Omnicoder streaming

```bash
curl -N -sS "${API_BASE}/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "omnicoder",
    "stream": true,
    "temperature": 0,
    "max_tokens": 24,
    "messages": [
      {"role": "system", "content": "You are a routing test. Reply with exactly: ROUTE_OK MODEL_2 STREAM"},
      {"role": "user", "content": "trace=model2_stream"}
    ]
  }'
```

Expected behavior: SSE chunks ending in `ROUTE_OK MODEL_2 STREAM` and `[DONE]`.

### 4) MiniCPM-V non-streaming

```bash
curl -sS "${API_BASE}/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "minicpm-v",
    "stream": false,
    "temperature": 0,
    "max_tokens": 24,
    "messages": [
      {"role": "system", "content": "You are a routing test. Reply with exactly: ROUTE_OK MODEL_3 NONSTREAM"},
      {"role": "user", "content": "trace=model3_nonstream"}
    ]
  }'
```

Expected behavior: normal JSON response with assistant message content `ROUTE_OK MODEL_3 NONSTREAM`.

### 5) MiniCPM-V streaming

```bash
curl -N -sS "${API_BASE}/chat/completions" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "minicpm-v",
    "stream": true,
    "temperature": 0,
    "max_tokens": 24,
    "messages": [
      {"role": "system", "content": "You are a routing test. Reply with exactly: ROUTE_OK MODEL_3 STREAM"},
      {"role": "user", "content": "trace=model3_stream"}
    ]
  }'
```

Expected behavior: SSE chunks ending in `ROUTE_OK MODEL_3 STREAM` and `[DONE]`.

## Important debugging truth

These are the conclusions Codex should assume unless new evidence disproves them:

1. The gateway is honoring explicit model names when auth/config is correct.
2. The working calls prove `omnicoder` and `minicpm-v` are callable through the unified gateway.
3. The earlier MiniCPM-V error was not proof of random routing. It was a proxy/upstream auth/config issue.
4. The VoiceOps UI can safely expose model selection using the canonical gateway model list.
5. The VoiceOps UI should also expose voice selection as a dropdown instead of hardcoding one voice path.

## What VoiceOps should implement next

Immediate UI/runtime targets:

1. Add a model dropdown sourced from a stable model list.
2. Add a voice dropdown sourced from the TTS voice list or current voice config.
3. Keep `omnicoder` and `minicpm-v` selectable now.
4. Preserve terminal visibility, but persist structured per-call logs automatically.
5. Prepare clean hooks for transcript/call events to publish to Redis Streams for future dual-model handling.

## Suggested repo placement

Put this document at:

```text
voice-agent/docs/runtime/VOICEOPS_GATEWAY_TRUTH_2026-03-16.md
```

If you also want an operator-facing duplicate, mirror it into your personal ops docs so the repo has one canonical in-repo copy and you have one sanity copy outside the repo.

## Files already attached / source of truth for this snapshot

- Curl log / verified gateway tests
- Codex implementation prompt for polish, streaming, and JSONL logging

This snapshot is meant to stop wheel-spinning. It is the verified baseline Codex should build against right now.


"""
Application settings — all configuration loaded from environment / .env file.

Grouped into logical sub-models. The top-level Settings class exposes flat
property aliases for backward-compatibility with all existing call sites.

Rules:
- All env access goes through this module. No os.getenv() anywhere else.
- extra='ignore': unknown .env variables are silently ignored.
- Every field has a sensible default. Only DATABASE_URL is truly required
  (derived from postgres_* fields, which have safe defaults for local dev).
- Secrets are redacted in the startup log (first 4 chars + ****).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_REDACT_FIELDS = {
    'secret_key',
    'platform_admin_key',
    'tenant_secret_key',
    'postgres_password',
    'redis_url',
    'twilio_auth_token',
    'aether_voice_api_key',
    'aether_voice_bearer_token',
    'llm_api_key',
}


def _redact(value: str | None) -> str:
    if not value:
        return '(not set)'
    if len(value) <= 4:
        return '****'
    return value[:4] + '****'


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    app_name: str = 'Aether VoiceOps API'
    environment: str = 'development'
    api_v1_prefix: str = '/api/v1'
    secret_key: str = 'change-me-in-production'
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = 720
    platform_admin_key: str = 'change-me-in-production'
    tenant_secret_key: str = 'change-me-in-production'
    public_base_url: str = 'https://voice.aetherpro.us'


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    postgres_user: str = 'voiceops'
    postgres_password: str = 'voiceops'
    postgres_db: str = 'voiceops'
    postgres_host: str = 'acp-postgres'
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return (
            f'postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}'
            f'@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}'
        )


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    redis_url: str = 'redis://localhost:6379/0'
    redis_streams_enabled: bool = True

    # Legacy global streams (observability / audit — kept for backward compat)
    redis_call_event_stream: str = 'voiceops:call_events'
    redis_call_transcript_stream: str = 'voiceops:call_transcripts'
    redis_call_extraction_stream: str = 'voiceops:call_extractions'
    redis_call_action_stream: str = 'voiceops:call_actions'

    # FSM per-call stream config
    redis_call_stream_prefix: str = 'voice:calls'
    redis_call_state_hash_prefix: str = 'voice:calls'  # appended: :{session_id}:state

    # FSM consumer group names
    redis_cg_state_controller: str = 'voice:ctrl'
    redis_cg_asr: str = 'voice:asr'
    redis_cg_tts: str = 'voice:tts'
    redis_cg_llm: str = 'voice:llm'
    redis_cg_audit: str = 'voice:audit'

    # Stream retention: approximate max entries per per-call stream
    redis_stream_maxlen: int = 10000


class TwilioSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None


class VoiceSettings(BaseSettings):
    """ASR and TTS via Aether Voice gateway."""

    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    aether_voice_http_base: str = 'https://asr.aetherpro.us/api'
    aether_voice_ws_base: str = 'wss://asr.aetherpro.us'
    aether_voice_api_key: str | None = None
    aether_voice_bearer_token: str | None = None

    # ASR defaults (overridable per-agent via agent.policy_config.runtime)
    aether_voice_asr_model: str = 'auto'
    aether_voice_asr_language: str = 'auto'

    # TTS defaults (overridable per-agent via agent.policy_config.runtime)
    aether_voice_tts_model: str = 'kokoro_realtime'
    aether_voice_tts_voice: str = 'af_bella'
    aether_voice_tts_format: str = 'wav'
    aether_voice_tts_sample_rate: int = 24000


class LLMSettings(BaseSettings):
    """LLM routing — OpenAI-compatible gateway."""

    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    llm_provider: str = 'openai'
    llm_endpoint: str | None = None
    llm_api_key: str | None = None
    llm_model: str = 'omnicoder'
    llm_timeout_seconds: int = 25


class TelemetrySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    call_log_root: str = 'logs/calls'
    enable_tracing: bool = False
    log_level: str = 'info'


# ---------------------------------------------------------------------------
# Top-level Settings — composes all sub-models and provides flat aliases
# so that every existing call site (settings.redis_url, settings.llm_model,
# settings.aether_voice_asr_model, ...) continues to work without change.
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    # --- App ---
    app_name: str = 'Aether VoiceOps API'
    environment: str = 'development'
    api_v1_prefix: str = '/api/v1'
    secret_key: str = 'change-me-in-production'
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = 720
    platform_admin_key: str = 'change-me-in-production'
    tenant_secret_key: str = 'change-me-in-production'
    public_base_url: str = 'https://voice.aetherpro.us'

    # --- Database ---
    postgres_user: str = 'voiceops'
    postgres_password: str = 'voiceops'
    postgres_db: str = 'voiceops'
    postgres_host: str = 'acp-postgres'
    postgres_port: int = 5432

    # --- Redis ---
    redis_url: str = 'redis://localhost:6379/0'
    redis_streams_enabled: bool = True

    # Legacy global observability streams
    redis_call_event_stream: str = 'voiceops:call_events'
    redis_call_transcript_stream: str = 'voiceops:call_transcripts'
    redis_call_extraction_stream: str = 'voiceops:call_extractions'
    redis_call_action_stream: str = 'voiceops:call_actions'

    # FSM per-call stream config
    redis_call_stream_prefix: str = 'voice:calls'
    redis_call_state_hash_prefix: str = 'voice:calls'
    redis_cg_state_controller: str = 'voice:ctrl'
    redis_cg_asr: str = 'voice:asr'
    redis_cg_tts: str = 'voice:tts'
    redis_cg_llm: str = 'voice:llm'
    redis_cg_audit: str = 'voice:audit'
    redis_stream_maxlen: int = 10000

    # --- Twilio ---
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None

    # --- Aether Voice (ASR + TTS) ---
    aether_voice_http_base: str = 'https://asr.aetherpro.us/api'
    aether_voice_ws_base: str = 'wss://asr.aetherpro.us'
    aether_voice_api_key: str | None = None
    aether_voice_bearer_token: str | None = None
    aether_voice_asr_model: str = 'auto'
    aether_voice_asr_language: str = 'auto'
    aether_voice_tts_model: str = 'kokoro_realtime'
    aether_voice_tts_voice: str = 'af_bella'
    aether_voice_tts_format: str = 'wav'
    aether_voice_tts_sample_rate: int = 24000

    # --- LLM ---
    llm_provider: str = 'openai'
    llm_endpoint: str | None = None
    llm_api_key: str | None = None
    llm_model: str = 'omnicoder'
    llm_timeout_seconds: int = 25

    # --- Telemetry ---
    call_log_root: str = 'logs/calls'
    enable_tracing: bool = False
    log_level: str = 'info'

    # --- FSM pipeline feature flag ---
    # Set FSM_PIPELINE_ENABLED=true to route new inbound calls through the
    # StreamIngester + State Controller instead of the legacy VoiceSessionManager.
    # Default is False — existing calls are unaffected during migration phases A-C.
    fsm_pipeline_enabled: bool = False

    @property
    def database_url(self) -> str:
        return (
            f'postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}'
            f'@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}'
        )

    def per_call_stream_key(self, session_id: str) -> str:
        """Redis Stream key for a single call's FSM event stream."""
        return f'{self.redis_call_stream_prefix}:{session_id}'

    def per_call_state_key(self, session_id: str) -> str:
        """Redis Hash key for a single call's live FSM state."""
        return f'{self.redis_call_state_hash_prefix}:{session_id}:state'

    def log_resolved(self) -> None:
        """Log all resolved settings at startup. Secrets are redacted."""
        lines = ['settings.resolved:']
        for field_name in self.model_fields:
            value = getattr(self, field_name)
            if field_name in _REDACT_FIELDS:
                display = _redact(str(value) if value is not None else '')
            else:
                display = str(value) if value is not None else '(not set)'
            lines.append(f'  {field_name}={display}')
        # Also log derived properties
        lines.append(f'  database_url=postgresql+asyncpg://{self.postgres_user}:****@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}')
        lines.append(f'  per_call_stream_prefix={self.redis_call_stream_prefix}:{{session_id}}')
        logger.info('\n'.join(lines), extra={'correlation_id': '', 'tenant_id': ''})


@lru_cache
def get_settings() -> Settings:
    return Settings()

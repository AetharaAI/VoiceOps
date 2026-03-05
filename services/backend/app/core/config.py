from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Aether VoiceOps API'
    environment: str = 'development'
    api_v1_prefix: str = '/api/v1'
    secret_key: str = 'change-me'
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = 720

    platform_admin_key: str = 'change-platform-key'
    tenant_secret_key: str = 'bWMzM3J5b25nYmFzZTY0c2VjcmV0a2V5MTIzNDU2Nzg5MA=='

    postgres_user: str = 'voiceops'
    postgres_password: str = 'voiceops'
    postgres_db: str = 'voiceops'
    postgres_host: str = 'localhost'
    postgres_port: int = 5432

    redis_url: str = 'redis://localhost:6379/0'

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    public_base_url: str = 'http://localhost:8000'

    asr_endpoint: str = 'http://asr:9000/transcribe'
    asr_streaming_endpoint: str | None = None
    tts_endpoint: str = 'https://tts.aetherpro.us/v1/tts'

    llm_provider: str = 'local'
    llm_endpoint: str | None = None
    llm_api_key: str | None = None

    enable_tracing: bool = False

    @property
    def database_url(self) -> str:
        return (
            f'postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}'
            f'@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}'
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

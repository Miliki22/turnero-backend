"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Kala Turnos"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "turnero"
    postgres_user: str = "turnero"
    postgres_password: str = "turnero"
    tz: str = "America/Argentina/Buenos_Aires"

    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_reset_token_expire_minutes: int = 30

    email_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    email_from: str = "Turnero Kala <no-reply@kala.local>"
    admin_notify_email: str = "admin@kala.local"
    frontend_url: str = "http://localhost:5173"
    google_oauth_client_secrets_file: str = "credentials/google_oauth/client_secret.json"
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/integrations/google/callback"
    google_calendar_id: str = "primary"
    google_sync_enabled: bool = False

    @property
    def database_url(self) -> str:
        """Build the SQLAlchemy database URL."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()

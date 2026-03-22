from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Kala Turnos"

    # Database
    postgres_user: str = "turnero"
    postgres_password: str = "turnero"
    postgres_db: str = "turnero"
    postgres_port: int = 5432
    postgres_host: str = "localhost"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

settings = Settings()
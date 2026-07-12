from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(validation_alias=AliasChoices("DATABASE_URL", "database_url"))
    secret_key: str = Field(validation_alias=AliasChoices("SECRET_KEY", "secret_key"))
    algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("ALGORITHM", "algorithm"),
    )
    access_token_expire_minutes: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "access_token_expire_minutes",
        ),
        ge=1,
    )
    password_reset_expire_minutes: int = Field(default=15, ge=5, le=60)
    upload_directory: str = Field(default="data/uploads")
    max_upload_bytes: int = Field(default=5_000_000, ge=1_000, le=20_000_000)
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

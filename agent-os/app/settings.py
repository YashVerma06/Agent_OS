from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Non-secret runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    google_cloud_project: str = Field(
        default="agent-os-506220", validation_alias="GOOGLE_CLOUD_PROJECT"
    )
    google_cloud_location: str = Field(
        default="us-central1", validation_alias="GOOGLE_CLOUD_LOCATION"
    )
    google_genai_use_vertexai: bool = Field(
        default=True, validation_alias="GOOGLE_GENAI_USE_VERTEXAI"
    )
    gemini_core_model: str = Field(default="gemini-3.6-flash", validation_alias="GEMINI_CORE_MODEL")
    demo_tenant_id: str = Field(default="agent-os-labs", validation_alias="DEMO_TENANT_ID")
    demo_project_id: str = Field(
        default="maintenance-request-portal", validation_alias="DEMO_PROJECT_ID"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

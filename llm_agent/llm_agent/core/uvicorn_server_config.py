from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UvicornServerConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    host: str = Field(default="0.0.0.0", validation_alias="UVICORN_HOST")
    port: int = Field(default=8080, validation_alias=AliasChoices("UVICORN_PORT", "PORT"))
    log_level: str = Field(default="info", validation_alias="UVICORN_LOG_LEVEL")
    reload: bool = Field(default=False, validation_alias="UVICORN_RELOAD")
    log_config_path: str = Field(
        default="./llm_agent/configuration/log_config_json.json",
        validation_alias="UVICORN_LOG_CONFIG_PATH",
    )

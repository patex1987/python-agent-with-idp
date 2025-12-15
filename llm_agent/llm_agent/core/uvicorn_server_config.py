from pydantic_settings import BaseSettings


class UvicornServerConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"
    reload: bool = False
    log_config_path: str = "./llm_agent/configuration/log_config_json.json"

    class Config:
        env_prefix = "uvicorn_"

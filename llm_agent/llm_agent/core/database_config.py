from pydantic_settings import BaseSettings, SettingsConfigDict


class PiccoloDBConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="piccolo_")

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_database: str = "postgres"
    db_run_migrations: bool = False

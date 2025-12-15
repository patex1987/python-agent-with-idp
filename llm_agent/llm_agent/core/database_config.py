from pydantic_settings import BaseSettings


class PiccoloDBConfig(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_database: str = "postgres"
    db_run_migrations: bool = False

    class Config:
        env_prefix = "piccolo_"

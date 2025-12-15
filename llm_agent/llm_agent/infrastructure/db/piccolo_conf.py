from piccolo.conf.apps import AppRegistry
from piccolo.engine import PostgresEngine

from llm_agent.core.database_config import PiccoloDBConfig

PICCOLO_DB_CONFIG = PiccoloDBConfig()


# TODO: create an environment specific config builder
POSTGRES_CONFIG = {
    "host": PICCOLO_DB_CONFIG.db_host,
    "port": PICCOLO_DB_CONFIG.db_port,
    "user": PICCOLO_DB_CONFIG.db_user,
    "password": PICCOLO_DB_CONFIG.db_password,
    "database": PICCOLO_DB_CONFIG.db_database,
    # asyncpg connect kwargs (applied to EACH new conn)
    "statement_cache_size": 0,  # PgBouncer/HA-friendly
    "command_timeout": 3.0,  # default per-command timeout (seconds)
    "timeout": 2.0,  # connect timeout (seconds)
    "server_settings": {
        "application_name": "llm-agent-fastapi",
        # TODO: works in aws only
        # "statement_timeout": "3000",                      # ms
        # TODO: works in aws only
        # "idle_in_transaction_session_timeout": "5000",    # ms; kill stuck txs
    },
}


def start_engine():
    engine = PostgresEngine(config=POSTGRES_CONFIG, extra_nodes=None)
    return engine


DB = start_engine()

APP_REGISTRY = AppRegistry(
    apps=["llm_agent.infrastructure.db.piccolo_llm_agent_app.piccolo_app"],
)

# from llm_agent.infrastructure.db.piccolo_llm_agent_app import piccolo_app

import structlog
import uvicorn

from llm_agent.core.log_config import configure_logging
from llm_agent.core.uvicorn_log_config import load_json_log_config
from llm_agent.core.uvicorn_server_config import UvicornServerConfig

logger = structlog.get_logger(__name__)


def main():
    uvicorn_server_config = UvicornServerConfig()
    log_config = load_json_log_config(uvicorn_server_config.log_config_path)
    if uvicorn_server_config.reload:
        # when in reload mode
        configure_logging()
        logger.info(f"Uvicorn server configuration: {uvicorn_server_config}")
    uvicorn.run(
        "llm_agent.di.fastapi_composition:compose_fastapi_app_with_registrars",
        host=uvicorn_server_config.host,
        port=uvicorn_server_config.port,
        log_level=uvicorn_server_config.log_level,
        log_config=log_config,
        reload=uvicorn_server_config.reload,
        factory=True,
    )


if __name__ == "__main__":
    main()

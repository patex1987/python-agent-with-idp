import structlog

from llm_agent.domain.infrastructure_setup import InfrastructureSetup

logger = structlog.get_logger(__name__)


class ProductionInfrastructureSetup(InfrastructureSetup):
    """
    Infrastructure setup implementation for production.

    Manages the lifecycle of Piccolo ORM with PostgreSQL db connection
    pools during application startup and shutdown.
    """

    async def setup(self) -> None:
        from llm_agent.infrastructure.db.piccolo_conf import DB
        from llm_agent.infrastructure.db.piccolo_llm_agent_app.pool_config import (
            get_db_pool_config,
        )

        db_pool_config = get_db_pool_config()
        await DB.start_connection_pool(**db_pool_config)

    async def shutdown(self) -> None:
        from llm_agent.infrastructure.db.piccolo_conf import DB

        logger.info("Shutting down db connection pool")

        await DB.close_connection_pool()

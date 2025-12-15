import os

import structlog

from llm_agent.core.database_config import PiccoloDBConfig

logger = structlog.get_logger(__name__)


def maybe_migrate():
    """
    TODO: this is dummy and stupid, do it differently
    """

    piccolo_db_config = PiccoloDBConfig()
    if piccolo_db_config.db_run_migrations:
        logger.info("Running migrations")
        os.system("piccolo migrations forwards all")

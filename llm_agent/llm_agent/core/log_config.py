import logging

import structlog
from structlog.typing import EventDict


def add_static_fields(logger: logging.Logger, name: str, event_dict: EventDict) -> EventDict:
    """
    structlog processor that adds the common fields to every log record

    TODO: define service level constants for these fields
    """
    event_dict.setdefault("service_name", "llm_agent_fastapi")
    event_dict.setdefault("version", "0.1")
    return event_dict


timestamper = structlog.processors.MaybeTimeStamper(fmt="iso")
SHARED_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    timestamper,
    add_static_fields,
    # structlog.stdlib.filter_by_level,
    structlog.stdlib.add_log_level,
    structlog.processors.format_exc_info,
]


def configure_structlog():
    structlog.configure(
        processors=SHARED_PROCESSORS
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def configure_python_logging():
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            # structlog.dev.ConsoleRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        # logger=logging.getLogger()
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


def configure_logging():
    configure_python_logging()
    configure_structlog()

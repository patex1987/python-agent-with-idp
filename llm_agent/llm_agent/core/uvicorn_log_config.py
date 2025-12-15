import json
from typing import Any


def load_json_log_config(path="./llm_agent/configuration/log_config_json.json"):
    with open(path) as config_file:
        logging_config = json.load(config_file)
    return logging_config


LOGGING_CONFIG: dict[str, Any] = load_json_log_config()

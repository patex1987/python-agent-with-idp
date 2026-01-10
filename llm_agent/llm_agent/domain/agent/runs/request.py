from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunRequest:
    """
    Api agent run request to work processor.
    """

    prompt: str
    history: list[str]
    user_id: str


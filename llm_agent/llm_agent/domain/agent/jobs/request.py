from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobRequest:
    """
    Api agent job request to work processor.
    """

    prompt: str
    history: list[str]
    user_id: str

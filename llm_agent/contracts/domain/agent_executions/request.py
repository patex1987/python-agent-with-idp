from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class AgentExecutionMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class AgentExecutionMessageSnapshot:
    """
    Dialogue message context captured for an agent execution.

    Snapshots keep the worker contract independent from full dialogue message
    entities while preserving the content and order needed to build a prompt.
    """

    role: AgentExecutionMessageRole
    content_text: str
    sequence_nr: int


@dataclass(frozen=True)
class AgentExecutionRequest:
    """
    Immutable input captured when an assistant response is prepared.

    The request links the execution back to the dialogue messages that caused it
    and carries the dialogue history snapshot available to the worker.
    """

    prompt: str
    history: list[AgentExecutionMessageSnapshot]
    user_id: str
    dialogue_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID

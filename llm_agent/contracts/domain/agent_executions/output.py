from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AgentExecutionOutputKind(StrEnum):
    MESSAGE = "message"


class AgentExecutionOutputPartType(StrEnum):
    TEXT = "text"


@dataclass(frozen=True)
class AgentExecutionReference:
    """
    External or internal object referenced by an agent execution output.

    References can represent citations, files, tool artifacts, or other objects
    that support the generated response.
    """

    reference_type: str
    reference_id: str
    label: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentExecutionOutputPart:
    """
    Ordered content fragment in an agent execution output.

    Parts allow the output contract to grow beyond plain text without changing
    the top-level event shape.
    """

    part_type: AgentExecutionOutputPartType
    text: str


@dataclass(frozen=True)
class AgentExecutionOutput:
    """
    Structured result produced by a completed agent execution.

    `content_parts` preserves response order. `references` carry optional
    supporting objects such as citations, files, or artifacts.
    """

    kind: AgentExecutionOutputKind
    content_parts: list[AgentExecutionOutputPart]
    references: list[AgentExecutionReference] = field(default_factory=list)

    @classmethod
    def from_text(cls, content_text: str) -> AgentExecutionOutput:
        return cls(
            kind=AgentExecutionOutputKind.MESSAGE,
            content_parts=[
                AgentExecutionOutputPart(
                    part_type=AgentExecutionOutputPartType.TEXT,
                    text=content_text,
                )
            ],
            references=[],
        )

    @property
    def content_text(self) -> str:
        return "".join(part.text for part in self.content_parts if part.part_type == AgentExecutionOutputPartType.TEXT)

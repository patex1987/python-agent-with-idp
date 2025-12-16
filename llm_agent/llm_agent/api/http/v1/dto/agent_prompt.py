from pydantic import BaseModel


class AgentPromptDto(BaseModel):
    prompt: str
    history: list[str]

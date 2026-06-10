from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DemoAgentSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    service_name: str = Field(default="movie-agent-worker", validation_alias="OTEL_SERVICE_NAME")
    movie_reservation_mcp_url: str = "http://movie-reservation-mcp:8091/mcp"
    axum_tools_mcp_url: str = "http://axum-tools-mcp:8092/mcp"
    demo_agent_max_steps: int = 8
    demo_mcp_timeout_seconds: float = 15.0
    demo_recommendation_limit: int = 5
    demo_llm_provider: str = "none"
    demo_llm_model: str = "openrouter/auto"
    demo_llm_timeout_seconds: float = 20.0
    demo_llm_max_tokens: int = 128
    demo_llm_temperature: float = 0.0
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_http_referer: str | None = None
    openrouter_app_title: str = "python-agent-with-idp"
    openrouter_allowed_models: str | None = None
    openrouter_auto_cost_quality_tradeoff: int | None = 7

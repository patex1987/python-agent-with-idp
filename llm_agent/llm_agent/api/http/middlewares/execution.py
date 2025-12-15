import fastapi
import starlette.types

from llm_agent.application.execution_context import ExecutionContextEnricher


class ExecutionContextMiddleware:
    def __init__(
        self,
        app: fastapi.FastAPI,
        execution_context_enricher: ExecutionContextEnricher,
    ):
        self.app = app
        self.execution_context_enricher = execution_context_enricher

    async def __call__(
        self, scope: starlette.types.Scope, receive: starlette.types.Receive, send: starlette.types.Send
    ):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        # raw_path = scope.get("path")
        # if str(raw_path).startswith("/health"):
        #     logger.debug("Auth validation skipped for health checks")
        #     return await self.app(scope, receive, send)

        with self.execution_context_enricher.enrich_from_scope(scope):
            instrumented_send = self.execution_context_enricher.get_instrumented_send(send, scope, custom_attributes={})
            instrumented_receive = self.execution_context_enricher.get_instrumented_receive(
                receive, scope, custom_attributes={}
            )

            await self.app(scope, instrumented_receive, instrumented_send)

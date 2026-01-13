import uuid

import svcs

from agent_run_worker.in_memory.consumer import InMemoryConsumer
from contracts.services.consumer import Consumer
from agent_run_worker.in_memory.run_executor import AgentRunExecutor, RandomSleepRunExecutor
from llm_agent.di.registrars.base import Registrar
from local_runtime.run_store.processing import InMemoryRunProcessingStore
from contracts.services.queue import RunSignalQueue
from agent_run_worker.services.runs.processing_store import RunProcessingStore
from llm_agent.services.agent.transition_policy import RunTransitionPolicy
from local_runtime.provider import InMemoryRuntime


class ConsumerRegistrar(Registrar):
    def __init__(self, shared_local_infrastructure: InMemoryRuntime):
        self._shared_local_infrastructure = shared_local_infrastructure

    def register(self, registry: svcs.Registry) -> None:
        registry.register_factory(AgentRunExecutor, self.get_run_executor)
        run_signal_queue = self.get_run_signal_queue()
        run_store = self.get_run_store()
        registry.register_value(RunSignalQueue, run_signal_queue)
        registry.register_value(RunProcessingStore, run_store)
        registry.register_factory(Consumer, self.get_consumer)

    def get_run_signal_queue(self) -> RunSignalQueue:
        return self._shared_local_infrastructure.run_signal_queue

    def get_run_store(self) -> RunProcessingStore:
        internal_run_storage = self._shared_local_infrastructure.internal_run_storage
        internal_event_logs = self._shared_local_infrastructure.internal_event_logs

        return InMemoryRunProcessingStore(
            internal_run_storage=internal_run_storage,
            internal_event_logs=internal_event_logs,
            run_transition_policy=RunTransitionPolicy(),
        )

    def get_run_executor(self) -> AgentRunExecutor:
        return RandomSleepRunExecutor()

    @classmethod
    def get_consumer(cls, svcs_container: svcs.Container) -> Consumer:
        worker_id = f"worker_{uuid.uuid4()}"
        return InMemoryConsumer(
            run_store=svcs_container.get(RunProcessingStore),
            run_signal_queue=svcs_container.get(RunSignalQueue),
            worker_id=worker_id,
            run_executor=svcs_container.get(AgentRunExecutor),
            heartbeat_interval_seconds=5,
        )

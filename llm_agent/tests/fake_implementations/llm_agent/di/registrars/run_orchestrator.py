import svcs

from llm_agent.di.registrars.base import Registrar

from llm_agent.services.agent.orchestrator import BackendRunOrchestrationService
from llm_agent.services.agent.queue import RunSignalQueue
from llm_agent.services.agent.store import RunIntakeStore
from llm_agent.services.agent.transition_policy import RunTransitionPolicy
from local_runtime.provider import InMemoryRuntime


class InMemoryRunOrchestrationRegistrar(Registrar):
    def __init__(self, shared_local_infrastructure: InMemoryRuntime):
        self._shared_local_infrastructure = shared_local_infrastructure

    def register(self, registry: svcs.Registry) -> None:
        run_store = self.create_run_store()
        run_signal_queue = self.create_run_signal_queue()

        registry.register_value(RunIntakeStore, run_store)
        registry.register_value(RunSignalQueue, run_signal_queue)

        run_orchestrator = BackendRunOrchestrationService(
            run_store=run_store,
            run_signal_queue=run_signal_queue,
        )
        registry.register_value(BackendRunOrchestrationService, run_orchestrator)

    def create_run_store(self) -> RunIntakeStore:
        """
        create a run store, with shared internal storage.

        So the worker can see inside the content in a single process setup.
        """
        from local_runtime.run_store.intake import InMemoryRunIntakeStore

        internal_run_storage = self._shared_local_infrastructure.internal_run_storage
        internal_event_logs = self._shared_local_infrastructure.internal_event_logs
        run_transition_policy = RunTransitionPolicy()

        in_memory_run_store = InMemoryRunIntakeStore(
            internal_run_storage=internal_run_storage,
            internal_event_logs=internal_event_logs,
            run_transition_policy=run_transition_policy,
        )
        return in_memory_run_store

    def create_run_signal_queue(self) -> RunSignalQueue:
        """
        Create an in-memory run queue with shared storage.

        So the worker can see inside the content in a single process setup.
        """
        in_memory_run_queue = self._shared_local_infrastructure.run_signal_queue
        return in_memory_run_queue


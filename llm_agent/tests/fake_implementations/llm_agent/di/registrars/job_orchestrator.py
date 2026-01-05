import svcs

from llm_agent.di.registrars.base import Registrar

from llm_agent.services.agent.orchestrator import BackendJobOrchestrationService
from llm_agent.services.agent.queue import JobSignalQueue
from llm_agent.services.agent.store import JobIntakeStore
from llm_agent.services.agent.transition_policy import JobTransitionPolicy
from local_runtime.provider import InMemoryRuntime


class InMemoryJobOrchestrationRegistrar(Registrar):
    def __init__(self, shared_local_infrastructure: InMemoryRuntime):
        self._shared_local_infrastructure = shared_local_infrastructure

    def register(self, registry: svcs.Registry) -> None:
        job_store = self.create_job_store()
        job_signal_queue = self.create_job_signal_queue()

        registry.register_value(JobIntakeStore, job_store)
        registry.register_value(JobSignalQueue, job_signal_queue)

        job_orchestrator = BackendJobOrchestrationService(
            job_store=job_store,
            job_signal_queue=job_signal_queue,
        )
        registry.register_value(BackendJobOrchestrationService, job_orchestrator)

    def create_job_store(self) -> JobIntakeStore:
        """
        create a job store, with shared internal storage.

        So the worker can see inside the content in a single process setup.
        """
        from local_runtime.job_store.intake import InMemoryJobIntakeStore

        internal_job_storage = self._shared_local_infrastructure.internal_job_storage
        internal_event_logs = self._shared_local_infrastructure.internal_event_logs
        job_transition_policy = JobTransitionPolicy()

        in_memory_job_store = InMemoryJobIntakeStore(
            internal_job_storage=internal_job_storage,
            internal_event_logs=internal_event_logs,
            job_transition_policy=job_transition_policy,
        )
        return in_memory_job_store

    def create_job_signal_queue(self) -> JobSignalQueue:
        """
        Create an in-memory job queue with shared storage.

        So the worker can see inside the content in a single process setup.
        """
        in_memory_job_queue = self._shared_local_infrastructure.job_signal_queue
        return in_memory_job_queue

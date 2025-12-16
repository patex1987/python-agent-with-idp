import svcs

from llm_agent.di.registrars.base import Registrar
from llm_agent.infrastructure.agent.in_memory.queue import InMemoryJobQueue

from llm_agent.services.agent.orchestrator import BackendJobOrchestrationService
from llm_agent.services.agent.queue import JobQueue
from llm_agent.services.agent.store import JobStore
from tests.fake_implementations.di.factories.job_related import InternalJobStorageProvider, InternalEventLogsProvider, \
    InternalJobQueueProvider


class InMemoryJobOrchestrationRegistrar(Registrar):
    def register(self, registry: svcs.Registry) -> None:
        job_store = self.__class__.create_job_store()
        job_queue = self.__class__.create_job_queue()

        registry.register_value(JobStore, job_store)
        registry.register_value(JobQueue, job_queue)

        job_orchestrator = BackendJobOrchestrationService(
            job_store=job_store,
            job_queue=job_queue,
        )
        registry.register_value(BackendJobOrchestrationService, job_orchestrator)

    @classmethod
    def create_job_store(cls) -> JobStore:
        """
        create a job store, with shared internal storage.

        So the worker can see inside the content in a single process setup.
        """
        from llm_agent.infrastructure.agent.in_memory.store import InMemoryApiJobStore

        internal_job_storage = InternalJobStorageProvider.get_instance()
        internal_event_logs = InternalEventLogsProvider.get_instance()

        in_memory_job_store = InMemoryApiJobStore(
            internal_job_storage=internal_job_storage,
            internal_event_logs=internal_event_logs,
        )
        return in_memory_job_store

    @classmethod
    def create_job_queue(cls) -> JobQueue:
        """
        Create an in-memory job queue with shared storage.

        So the worker can see inside the content in a single process setup.
        """
        internal_job_queue = InternalJobQueueProvider.get_instance()

        in_memory_job_queue = InMemoryJobQueue(internal_job_queue=internal_job_queue)
        return in_memory_job_queue

# svcs And Registrar Pattern

This package uses `svcs` for explicit dependency composition. The goal is to keep
framework, infrastructure, and test wiring at the edge of the application while
keeping domain and service code free of dependency-container knowledge.

## What Is svcs?

`svcs` is a Python dependency container. It has two core concepts:

- `svcs.Registry`: application-scoped registration of factories and values keyed
  by types or protocols.
- `svcs.Container`: context-scoped service acquisition from a registry. In this
  project, request containers usually come from FastAPI, while app and worker
  setup can create explicit containers.

Factories are lazy. A factory is called only when a container asks for the
registered type with `get()` or `aget()`. The created instance is cached inside
that container, so repeated acquisitions from the same container return the same
instance. If a factory returns a context manager, async context manager,
generator, or async generator, `svcs` owns the cleanup when the container closes.

In FastAPI, `svcs.fastapi.DepContainer` injects a request-scoped container into
route dependency functions. This repository wraps `di_lifespan()` with
`svcs.fastapi.lifespan(..., registry=registry)` in `llm_agent/llm_agent/app.py`
so the composition root provides one explicit registry for the app.

Primary upstream references:

- `svcs` core concepts: https://svcs.hynek.me/en/25.1.0/core-concepts.html
- `svcs` FastAPI integration: https://svcs.hynek.me/en/25.1.0/integrations/fastapi.html

## Repository Composition Flow

The main composition path is:

```text
DI_REGISTRAR_PROVIDER env var
  -> llm_agent.di.fastapi_composition.compose_fastapi_app_with_registrars()
  -> RegistrarProvider returns ApplicationDIConfig
  -> create_app_with_selected_di()
  -> app_lifetime_registrars are applied to the main registry
  -> middleware is created from a container over that registry
  -> fastapi_lifespan_registrars are applied inside di_lifespan()
  -> request handlers acquire services through svcs.fastapi.DepContainer
```

The core files are:

- `llm_agent/llm_agent/di/registrars/base.py`
- `llm_agent/llm_agent/di/app_wide_registrar.py`
- `llm_agent/llm_agent/di/app_registrar_providers.py`
- `llm_agent/llm_agent/di/registry_builder.py`
- `llm_agent/llm_agent/di/fastapi_composition.py`
- `llm_agent/llm_agent/di/fastapi_lifespan.py`
- `llm_agent/llm_agent/app.py`

## What Is A Registrar?

A registrar is a small object that knows how to add one coherent set of
dependencies to a `svcs.Registry`.

The protocol is intentionally tiny:

```python
from typing import Protocol

import svcs


class Registrar(Protocol):
    def register(self, registry: svcs.Registry) -> None: ...
```

Registrars are composition code, not business code. They should:

- Register values and factories.
- Connect abstractions or protocols to concrete implementations.
- Keep environment-specific choices at the composition boundary.
- Hold only wiring-time configuration or shared runtime objects passed into the
  registrar constructor.

Registrars should not:

- Contain business rules.
- Perform route-level request extraction.
- Hide network/database startup work inside arbitrary module-level globals.
- Import FastAPI route DTOs into domain or service layers.
- Become large "container modules" that know unrelated feature wiring.

## Registrar Lifecycles

`ApplicationDIConfig` groups registrars by lifecycle phase:

```python
@dataclass
class ApplicationDIConfig:
    app_lifetime_registrars: Sequence[Registrar]
    fastapi_lifespan_registrars: Sequence[Registrar]
    infrastructure_registrars: Sequence[Registrar]
```

Use `app_lifetime_registrars` for dependencies needed before middleware is
registered. Current examples include authentication and execution-context
dependencies used by middleware.

Use `fastapi_lifespan_registrars` for dependencies that should be available to
request handlers after the FastAPI lifespan starts. This is the normal place for
feature services, stores, repositories, queues, and other request-visible
application dependencies.

Use `infrastructure_registrars` for runtime infrastructure that is intentionally
outside the FastAPI request container, such as local workers or consumers. This
package currently builds a separate infrastructure registry/container so worker
runtime dependencies do not inflate the request container.

`apply_registrars()` applies registrars in sequence. If the same type is
registered multiple times, the later registration wins. Tests use this to append
override registrars without changing production code.

## Registering Values vs Factories

Use `registry.register_value(Type, value)` when the object already exists and
should be reused as-is:

```python
registry.register_value(GeneticConfiguration, GeneticConfiguration())
registry.register_value(AsyncAuthenticationManager, auth_manager)
```

Use `registry.register_factory(Type, factory)` when the object should be built
lazily, can depend on other registered services, or should be scoped to a
container:

```python
registry.register_factory(PathFinderStrategy, factory=cls.get_path_finder)
registry.register_factory(ThrottleStepsService, factory=cls.get_throttle_step_service)
```

A factory can ask for the current container by accepting a first argument named
`svcs_container` or annotated as `svcs.Container`:

```python
class ThrottleStepsServiceRegistrar(Registrar):
    def register(self, registry: svcs.Registry) -> None:
        registry.register_value(GeneticConfiguration, GeneticConfiguration())
        registry.register_factory(PathFinderStrategy, self.get_path_finder)
        registry.register_factory(ThrottleStepsService, self.get_throttle_step_service)

    @classmethod
    def get_path_finder(cls, svcs_container: svcs.Container) -> PathFinderStrategy:
        config = svcs_container.get(GeneticConfiguration)
        return GeneticPathFinderStrategy(genetic_configration=config)

    @classmethod
    def get_throttle_step_service(cls, svcs_container: svcs.Container) -> ThrottleStepsService:
        return ThrottleStepsService(
            path_finder=svcs_container.get(PathFinderStrategy),
        )
```

Use `container.get(Type)` for synchronous factories and values. Use
`await container.aget(Type)` when the registered factory or cleanup path is async.

## How To Add A Registrar

1. Add a focused file under `llm_agent/llm_agent/di/registrars/`.
2. Implement a class named after the feature or boundary, for example
   `AgentExecutionRegistrar`.
3. Implement `register(self, registry: svcs.Registry) -> None`.
4. Register interfaces, protocols, ports, or service types as keys. Prefer
   registering abstractions when a concrete implementation is swappable.
5. Use `register_value()` for prebuilt stable objects and `register_factory()`
   for lazy or container-scoped objects.
6. Put dependency construction helpers on the registrar as instance methods when
   they need registrar state, or `@classmethod`/`@staticmethod` when they do not.
7. Add the registrar to the right `ApplicationDIConfig` provider.
8. Add test/development alternatives under `llm_agent/tests/fake_implementations`
   when the dependency needs to be replaced in tests.

Template:

```python
import svcs

from llm_agent.di.registrars.base import Registrar
from llm_agent.services.some_feature import SomeFeatureService
from llm_agent.services.some_feature_store import SomeFeatureStore
from llm_agent.infrastructure.some_feature.memory_store import InMemorySomeFeatureStore


class SomeFeatureRegistrar(Registrar):
    def __init__(self, namespace: str) -> None:
        self._namespace = namespace

    def register(self, registry: svcs.Registry) -> None:
        registry.register_factory(SomeFeatureStore, self.get_store)
        registry.register_factory(SomeFeatureService, self.get_service)

    def get_store(self) -> SomeFeatureStore:
        return InMemorySomeFeatureStore(namespace=self._namespace)

    @staticmethod
    def get_service(svcs_container: svcs.Container) -> SomeFeatureService:
        return SomeFeatureService(
            store=svcs_container.get(SomeFeatureStore),
        )
```

If a factory creates a resource that must be closed, prefer returning a context
manager or async context manager so `svcs` can clean it up with the container. If
the resource is application-wide, register an `on_registry_close` cleanup or own
it through the infrastructure setup/lifespan path.

## FastAPI Route Usage

Route handlers should not construct broad dependency graphs directly. Use a
small FastAPI dependency function when a route needs to assemble a route-local
service from the request container:

```python
import fastapi
import svcs.fastapi
from uuid import UUID

from llm_agent.api.http.v1.dto.dialogue import DialogueDto
from llm_agent.api.http.v1.mappers.dialogue import DialogueV1Mapper
from llm_agent.services.dialogue import DialogueService


def get_dialogue_service(
    services: svcs.fastapi.DepContainer,
) -> DialogueService:
    return services.get(DialogueService)


@dialogue_router.get("/dialogues/{dialogue_id}", response_model=DialogueDto)
async def get_dialogue(
    dialogue_id: UUID,
    request: fastapi.Request,
    dialogue_service: DialogueService = fastapi.Depends(get_dialogue_service),
) -> DialogueDto:
    dialogue = await dialogue_service.get_dialogue(
        user_id=request.scope["state"]["user_id"],
        dialogue_id=dialogue_id,
    )
    return DialogueV1Mapper.dialogue_to_dto(dialogue)
```

Keep this route-level assembly small. If the service graph becomes reusable or
shared across routes, move it into a registrar factory.

## Non-FastAPI Usage

For CLI tools, workers, or tests that do not run through FastAPI, create an
explicit registry and container:

```python
import svcs

from llm_agent.di.registry_builder import apply_registrars


async def run_worker(registrars: list[Registrar]) -> None:
    registry = apply_registrars(registrars)

    async with svcs.Container(registry) as container:
        consumer = await container.aget(Consumer)
        await consumer.agent_execution()

    await registry.aclose()
```

Avoid process-global `_REGISTRY` and `_CONTAINER` singletons for application
logic. If a command framework needs to carry DI state, attach the registry or
container to that command context and close it explicitly.

## Testing Overrides

Tests should replace wiring through registrars instead of monkey-patching
production modules.

Useful local patterns:

- `tests.fake_implementations.llm_agent.di.app_registrar_providers.get_development_registrars`
- `tests.fake_implementations.di.ajustable_registrar.ComposableRegistrarProvider`
- `tests.fake_implementations.di.registrars.dependency_override.DependencyOverrideRegistrar`

Example:

```python
override_registrar = DependencyOverrideRegistrar(
    factory_overrides={AgentExecutionExecutor: DummyAgentExecutionExecutor},
    value_overrides={},
)

registrar_provider = ComposableRegistrarProvider(
    app_lifetime_registrars=[],
    fastapi_lifespan_registrars=[],
    infrastructure_registrars=[override_registrar],
)

app = create_app_with_selected_di(registrar_provider=registrar_provider)
```

Because later registrations overwrite earlier ones, apply override registrars
after the base registrars. If a container has already acquired the old service,
close/reset that container before expecting the new registration to be visible.

## Boundary Rules

- Domain code must not import `svcs`.
- Domain code must not import FastAPI, request DTOs, middleware, or Piccolo
  table classes.
- Services should receive dependencies through constructors or typed function
  parameters, not by calling the container.
- API route dependencies and DI registrars are the normal places to call
  `services.get(...)` or `container.get(...)`.
- Infrastructure adapters can be constructed by registrars, but adapters should
  not reach back into the container at runtime.
- Keep registrars small and feature-oriented. Split unrelated registrations into
  separate registrars.
- Keep lifecycle work explicit in FastAPI lifespan or infrastructure setup.

## Quick Checklist

Before adding or changing DI wiring:

- Is this dependency route-local? Use FastAPI `Depends`.
- Is this dependency shared or swappable? Register it with `svcs`.
- Does it need middleware before lifespan? Put it in `app_lifetime_registrars`.
- Is it request-visible after startup? Put it in `fastapi_lifespan_registrars`.
- Is it worker/runtime infrastructure? Put it in `infrastructure_registrars`.
- Does it have cleanup? Use a context manager factory, registry close callback,
  or explicit infrastructure setup/shutdown.
- Can tests swap it without touching production modules? Add a fake registrar or
  override registrar.

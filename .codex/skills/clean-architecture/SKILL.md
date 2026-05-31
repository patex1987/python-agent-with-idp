---
name: clean-architecture
description: Use when designing or modifying architecture boundaries in this Python FastAPI repository, including domain/application/service/infrastructure/API layering, DTO mapping, persistence adapters, worker/event-log boundaries, svcs registrars, and dependency direction.
---

# Clean Architecture

Use this skill when a change affects where code belongs, how dependencies flow, or how a feature crosses API, service, domain, infrastructure, and worker boundaries.

## Core Rule

Dependencies point inward.

- Domain code must not import FastAPI, Piccolo tables, `svcs`, middleware, HTTP DTOs, or concrete infrastructure adapters.
- Application/services may depend on domain objects and narrow ports/protocols.
- Infrastructure implements ports and owns database, auth provider, service discovery, filesystem, network, and runtime details.
- API routes own HTTP translation: request validation, identity extraction, DTO mapping, HTTP status codes, and domain-exception translation.
- DI registrars wire concrete implementations at the composition boundary.

## Current Repo Layers

- API: `llm_agent/llm_agent/api/http/`
- Application abstractions/context: `llm_agent/llm_agent/application/`
- Domain rules/entities: `llm_agent/llm_agent/domain/`
- Use-case services: `llm_agent/llm_agent/services/`
- Infrastructure adapters: `llm_agent/llm_agent/infrastructure/`
- DI and registrar composition: `llm_agent/llm_agent/di/`
- Worker/runtime contracts: `llm_agent/agent_run_worker/`, `llm_agent/contracts/`, `llm_agent/local_runtime/`
- Tests and fakes: `llm_agent/tests/`

## Placement Guide

- Put request and response schemas in `api/http/v1/dto/`.
- Put HTTP/domain mapping in `api/http/v1/mappers/`.
- Put route handlers in `api/http/v1/routes/`; keep them thin.
- Put business invariants, state machines, and transition rules in `domain/`.
- Put use-case orchestration in `services/` or the feature's existing service package.
- Put external implementations in `infrastructure/`, `repositories/`, `local_runtime/`, or worker-specific adapter packages.
- Put dependency wiring in a registrar under `di/registrars/` when the dependency is part of application composition.

## FastAPI And svcs

- For package-specific `svcs` and registrar conventions, read `docs/patterns/svcs_notes.md` before changing DI wiring.
- FastAPI `Depends` is appropriate for route-local extraction and request-scoped assembly.
- `svcs` is the project composition model for shared dependencies and swappable implementations.
- Registrar classes should register dependencies, not perform runtime business decisions.
- Middleware should enrich request/security/execution context and delegate business decisions inward.
- Lifespan owns startup/shutdown and infrastructure setup; avoid scattering lifecycle work.

## Service Design

- Prefer object-in/object-out APIs for non-trivial use cases: typed request objects in, typed result objects out.
- Use plain functions for utilities, mappers, dependency helpers, and pure transformations.
- Use classes when they express a real service boundary, hold injected dependencies, or match existing registrar/lifecycle patterns.
- Keep services focused on one use case or bounded feature area. Split broad services before they become dependency hubs.
- Do not pass powerful mutable stores deep into execution logic when a narrower port, event sink, or cancellation signal is enough.

## Domain And Persistence

- Domain objects should express behavior and invariants without knowing how they are stored.
- Piccolo tables and migrations belong to infrastructure.
- Repository or store adapters translate persistence details into domain/application concepts.
- Transaction boundaries must be explicit for multi-write consistency.
- Event-log behavior should preserve append-only semantics, ordering, idempotency, and deterministic replay where those invariants apply.

## Design Pressure Checks

- If a domain object imports a route, DTO, table, middleware, or FastAPI dependency, the boundary is leaking.
- If a route knows business policy, move that policy into a service or domain object.
- If an adapter decides business rules, move the rule inward and keep the adapter mechanical.
- If a service needs many unrelated stores, queues, clients, or config values, introduce narrower ports or split the use case.
- If tests require a real database for pure business behavior, the dependency boundary is probably too low-level.

## Testing Expectations

- For detailed fake-first pytest, fixture, conftest, async, and DI override conventions, use the `testing` skill.
- Test domain rules without FastAPI, `svcs`, or database dependencies.
- Test services with fake ports/stores/queues/event logs.
- Test adapters at the integration boundary they own.
- Test routes for validation, auth behavior, mapping, and HTTP error translation.
- For worker/event-log changes, test event sequences, folded state, cancellation races, and duplicate-processing behavior.

## Avoid

- Generic "clean architecture" abstractions that do not reduce coupling in this repo.
- Framework decorators or database objects in domain code.
- Business logic in DTO mappers, registrars, middleware, or persistence adapters.
- Hidden singleton state that bypasses the composition root.
- Broad rewrites just to make code match a diagram.

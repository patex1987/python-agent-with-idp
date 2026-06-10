# Development Guide

This document describes **how to work on the throttle sequencer service locally**, how DI works, 
and how to work with the multi-database failover setup.

---

# 1. Project Structure Overview

Key folders:

```
throttling_sequencer/
├── api/
│   ├── http/ (REST)
│   ├── graphql/ (GraphQL + subscriptions)
│   └── middlewares/
├── core/ (logging, uvicorn config, telemetry)
├── di/ (dependency injection setup)
├── domain/ (pure business logic)
├── infrastructure/
│   └── db/ (Piccolo setup, migrations, repo)
└── services/ (use cases)
└── navigation/ (path finders, throttle logic)
```


---

# 2. Running Locally (IDE)

Prerequisites:

- Python 3.12+
- A running Postgres instance - as **database dependency is baked in to the code atm**
  - there is an in-memory repository already available, which will be used fro local testing as a default in the future 
- (Optional) Keycloak instance for JWT authentication - see section 2.1
- Render the local environment file from the committed template:

```bash
mkdir -p configuration/env_files/local configuration/env_files/in-docker
cp configuration/env_files/templates/local/local-development.env.template configuration/env_files/local/local-development.env
cp configuration/env_files/templates/local/local-production.env.template configuration/env_files/local/local-production.env
cp configuration/env_files/templates/in-docker/local-production.env.template configuration/env_files/in-docker/local-production.env
cp configuration/env_files/templates/in-docker/local-development.env.template configuration/env_files/in-docker/local-development.env
```

Edit the rendered files under `configuration/env_files/` for local secrets such
as `OPENROUTER_API_KEY`. Rendered `.env` files are ignored by git; templates are
safe to commit.

## 2.1. Keycloak Setup (Optional)

For local development, Keycloak can be run via Docker Compose:

```bash
docker compose -f docker-compose.e2e.yml up keycloak
```

or bring up all your dependencies except for the main service:
```bash
docker compose -f docker-compose.e2e.yml -f docker-compose.multi-db.dev.yml --profile dependencies up
```

Keycloak will be available at `http://localhost:8082` with:
- Realm: `throttling-test`
- Admin console: `http://localhost:8082` (admin/admin)
- Test users: `test-user` / `test-password` and `admin-user` / `admin-password`

To retrieve tokens for API testing, see `testing_payloads/keycloak_token_retrieval.md` and use the Python script:

```bash
python testing_payloads/get_keycloak_token.py
```


Then:

```bash
uv run --env-file ../configuration/env_files/local/local-development.env python manage.py
```

ofc, you can execute it from your favorite IDE, with pointing to the right env file (e.g. pycharm)

The server starts with:

- auto-reload (if enabled via `uvicorn_reload=true`)
- JSON logs  
- DI-managed services  
- Automatic Piccolo DB connection pool setup
- Important refactor note: database dependency is baked in to the code atm, this must be refactored, otherwise the whole dependency injection doesn't make any sense 

---

# 3. Running in Docker

### 3.1. Build (Development Layer)

Development mode means that the service is executed with uvicorn's hot reload

```
docker build --target dev -t fastapi_graphql:local_dev -f Dockerfile .
```

### 3.2. Run in development mode

```shell
docker run -it -p 8080:8080 \
  --env-file configuration/env_files/in-docker/local-development.env \
  fastapi_graphql:local_dev
```

```shell
docker run -it -p 8080:8080 \
  --env-file configuration/env_files/in-docker/local-development.env \
  fastapi_graphql:local_dev
```

To enter a shell:

```

docker run -it --rm throttling_seq:local_dev /bin/bash

````

---

# 4. Dependency Injection

This project uses **svcs** to provide:

- clear separation of service implementations
- easy mocking / swapping deps in tests
- context-bound request scoping (FastAPI lifespan)

### DI lifecycle

Located in:  
`throttling_sequencer/di/fastapi_lifespan.py`

During startup:

**As mentioned earlier the hard dependency on db has to be removed**
```python
await DB.start_connection_pool(...)
adjust_registry(registry)
````

Example dependency registrations:

* `PathFinder` → `GeneticPathFinder` (or RandomDummy)
* `ThrottleStepsService`
* `BaseGameStateRetriever`
* `AsyncGqlRequestRepository` (Piccolo)
* `PostgresEngine`

GraphQL context is assembled via:

```
api/graphql/schema_entry/context_getter.py
```

Using:
* `GqlOperationContext` - This enables fine-grained control over resolver access.

---

# 5. Database Layer & Migrations

If you decide to use a database for your repositories, you can use piccolo ORM for connecting to the db.

### Connection

Config via:

```
piccolo_db_host
piccolo_db_user
piccolo_db_password
piccolo_db_port
piccolo_db_run_migrations
```

### Migrations

Stored under:

```
infrastructure/db/piccolo_throttling_sequencer_app/piccolo_migrations/
```

Run manually:

```
piccolo migrations forwards all
```

Or automatically if:

```
piccolo_db_run_migrations=true
```

---

# 6. Multi-Database Setup

This topic is completely independent on the main logic. Multi-database setup is here to create an article
about how to handle database failovers and to validate how the service behaves under such an event. 

## 6.1 Local HAProxy Failover (Simulated)

Script:

```
testing_payloads/multi_db_flip.sh
```

Requirements:

* Two Postgres instances
* HAProxy routing between them
* pgbouncer in front (optional)

Capabilities:

* Drain a DB (simulate reader)
* Promote the other DB (simulate writer)
* Force both DBs into maintenance
* Flip multiple times in a sequence

Useful for testing:

* asyncpg reconnects
* retry logic in repositories
* error handling during failover

---

## 6.2 AWS Aurora Failover (Realistic)

Script:

```
testing_payloads/aws_rds_port_forward_failover_sequence.sh
```

Features:

* Uses SSM Session Manager for port forwarding
* Automatically resolves the current writer instance
* Restarts tunnels after failover
* Supports multi-step failover testing
* Logs the tunnel PID and state transitions

Follow notes in:

```
testing_payloads/aws_failover_notes.md
```

---

# 7. GraphQL Development

Endpoint:
```
http://localhost:8080/graphql
```

graphiql IDE is exposed under that endpoint (useful for graphql introspection)

Features:

* Query + Mutation
* Subscriptions (WS + graphql-ws)
* Auth via custom Strawberry extensions: `HttpAuthExtension`, `WsHttpAuthExtension`
  * JWT tokens from Keycloak are validated using OpenID Connect discovery
  * Please note that these field extensions are still under development
* Request metadata collector (`RequestInfoCollectorExtension`)

Authentication:

* Bearer tokens (JWT) from Keycloak are supported
* Retrieve tokens using: `python testing_payloads/get_keycloak_token.py`
* See `testing_payloads/keycloak_token_retrieval.md` for details

Subscription example:

```
python testing_payloads/gql_websocket.py
```

---

# 8. REST Development

Example call with Basic auth (legacy):

```
curl -X POST -H "Authorization: Basic Z2Fib3I6eHl6" \
     -H "Content-Type: application/json" \
     -d @testing_payloads/game_state.json \
     http://localhost:8080/api/v1/throttle/calculate_throttle_steps
```

Example call with Keycloak JWT token:

```bash
# Get token
TOKEN=$(python testing_payloads/get_keycloak_token.py)

# Use token in API call
curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d @testing_payloads/game_state.json \
     http://localhost:8080/api/v1/throttle/calculate_throttle_steps
```

Mappers:

* HTTP layer → DTOs → Domain
* Domain → UnitGoal → DTO response

---

# 9. Logging & Telemetry

Logging setup:

* JSON logs via uvicorn log config
* structlog processors:

  * timestamp
  * contextvars merger
  * static fields (service, version)

Middlewares enrich each request with:

* request_id
* user_id
* (optional) trace_id if OTel enabled

Telemetry hook exists at:

```
core/telemetry.py
```

(ready for OpenTelemetry integration)

---

# 10. Useful Commands

### Check package installation:

```
./package_sanity_check.sh
```

### Run genetic algorithm test:

```
python throttling_sequencer/services/navigation/runner_for_steps_test_to_delete.py
```

---

# 11. Contributing

* Follow Python 3.12 best practices
* Keep domain layer pure
* Add new path-finders under `services/navigation/path_finders`
* Add new GraphQL operations under `api/graphql/operations`
* Use DI for all new services

---

# 12. Future Improvements

* Add fake auth providers for local dev (bypass Keycloak in development)
* Add extended docker compose profiles:

  * IDE mode
  * local E2E mode
  * containerized E2E
* Improve migration triggering mechanism
* Implement OpenTelemetry pipeline in `core/telemetry.py`

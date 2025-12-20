# TODO - Application Status and Missing Features

## Current State

The application is **not yet ready for production**. Currently, it contains:

### ✅ What's Implemented

- **FastAPI Boilerplate**: A FastAPI application with clean architecture and dependency injection using `svcs`
- **Token Verification Infrastructure**: 
  - JWT token validation system that supports multiple OIDC providers (Keycloak, Entra ID, or any other OIDC-compliant provider)
  - Token validation is wired through dependency injection, making it easy to swap providers
  - Authentication middleware that validates tokens on incoming requests
  - Support for both HTTP and WebSocket token extraction
- **Dependency Injection**: Full DI setup using `svcs` with registrars for different components (auth, services, repositories)
- **Database Layer**: Piccolo ORM integration with PostgreSQL (with in-memory alternatives for testing)
- **Structured Logging**: Using `structlog` with request context enrichment
- **Basic REST API**: Health check and throttle calculation endpoints

---

## ❌ Missing Features

### 1. Chainlit Integration

**Status**: Not implemented

Chainlit integration is completely missing. The application needs:

- Chainlit server setup and configuration
- Integration of Chainlit with the existing FastAPI application
- WebSocket support for Chainlit's real-time communication
- Chainlit UI components and chat interface
- Connection between Chainlit frontend and backend agent logic


---

### 2. PKCE Token Validation for Chainlit and Single Page App (SPA)

**Status**: Not implemented

The current token verification only supports standard JWT Bearer token validation. Missing:

- **PKCE (Proof Key for Code Exchange)** flow implementation
- OAuth2/OIDC authorization code flow with PKCE for SPAs
- Token refresh mechanism for SPAs
- Secure token storage and handling in browser context
- Integration with Chainlit's authentication requirements

---

### 3. Agent Logic

**Status**: Not implemented

The core agent functionality is missing. The application currently only has example throttle calculation logic, but no actual LLM agent implementation.


---

### 4. Background Worker System for Job Offloading

**Status**: Not implemented

Currently, all processing happens synchronously within the FastAPI request handlers. Missing:

- **Dedicated worker processes** running separately from the FastAPI app
- Job queue system
- Job scheduling and distribution
- Worker health monitoring
- Job status tracking and result retrieval
- Integration between FastAPI and worker processes



---

## Architecture Considerations

### Current Architecture
```
FastAPI App (asynchronous request handling)
  ├── Authentication Middleware (JWT validation)
  ├── REST API endpoints
  └── Direct service calls (no async offloading)
```

### Target Architecture
```
FastAPI App (API gateway)
  ├── Authentication (JWT + PKCE)
  ├── REST API endpoints
  ├── Chainlit Integration
  └── Job Queue Client
        │
        ▼
Worker Processes (separate processes/containers)
  ├── Agent Execution Engine
  ├── LLM Integration
  └── Job Result Storage
```

---

## Notes

- The existing DI infrastructure makes it straightforward to add new components (workers, agent services, etc.)
- Token validation can be extended to support PKCE without major refactoring
- The current architecture follows clean architecture principles, which should be maintained when adding new features
- Consider using async task queues (e.g., `arq`, `dramatiq`) for better integration with FastAPI's async nature




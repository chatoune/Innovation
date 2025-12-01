# Research: Client/Server Application Platform

**Branch**: `001-architecture-docs` | **Date**: 2025-12-01

## Technology Decisions

### Backend Framework

**Decision**: FastAPI with Uvicorn ASGI server

**Rationale**:
- Native async support for handling concurrent requests
- Automatic OpenAPI documentation generation
- Pydantic integration for request/response validation
- Excellent performance benchmarks for Python web frameworks
- Strong typing support with Python type hints

**Alternatives Considered**:
- Django REST Framework: More batteries-included but heavier, less performant for async
- Flask: Simpler but lacks native async and automatic validation

### ORM / Database Access

**Decision**: SQLAlchemy 2.0 with async support

**Rationale**:
- Industry standard for Python database access
- SQLAlchemy 2.0 provides native async session support
- Excellent PostgreSQL dialect with full feature support
- Alembic integration for database migrations
- Type hints support for better IDE experience

**Alternatives Considered**:
- Tortoise ORM: Django-style ORM, async-first but smaller ecosystem
- Raw asyncpg: Maximum performance but no ORM benefits

### Authentication - Password Hashing

**Decision**: Argon2id via `argon2-cffi` library

**Rationale**:
- Winner of Password Hashing Competition (PHC)
- Memory-hard algorithm resistant to GPU attacks
- Recommended by OWASP for new applications
- Configurable parameters for future-proofing

**Alternatives Considered**:
- bcrypt: Proven and widely used, but Argon2 is newer standard
- scrypt: Good but less tooling support than Argon2

### Authentication - Session/Token Management

**Decision**: JWT tokens with HTTPOnly cookies for session storage

**Rationale**:
- Stateless authentication reduces server load
- HTTPOnly cookies prevent XSS token theft
- Refresh token pattern for extended sessions
- Compatible with FIDO2 authentication flow

**Alternatives Considered**:
- Server-side sessions with Redis: More control but adds infrastructure complexity
- JWT in localStorage: Vulnerable to XSS attacks

### FIDO2/WebAuthn Implementation

**Decision**: `py_webauthn` library for backend

**Rationale**:
- Well-maintained Python WebAuthn implementation
- Handles challenge generation, credential verification
- Supports both registration and authentication flows
- Compatible with YubiKey, SoloKey, and platform authenticators

**Alternatives Considered**:
- `webauthn`: Less active maintenance
- Custom implementation: Too complex and error-prone for security-critical code

### Frontend Framework

**Decision**: React with TypeScript (recommendation, alternatives acceptable)

**Rationale**:
- Large ecosystem and community support
- Strong TypeScript integration for type safety
- Excellent tooling (Vite, React Query, React Router)
- Component-based architecture fits modular requirements

**Alternatives Considered**:
- Vue.js: Also excellent choice, slightly smaller ecosystem
- Svelte: Newer, smaller community but simpler reactivity model

### UI Component Library

**Decision**: Tailwind CSS with shadcn/ui components (recommendation)

**Rationale**:
- Utility-first approach enables rapid UI development
- shadcn/ui provides accessible, customizable components
- No runtime CSS-in-JS overhead
- Easy to customize without fighting framework defaults

**Alternatives Considered**:
- Material UI: Full-featured but opinionated styling, larger bundle
- Bootstrap: Established but dated appearance

### Excel Processing

**Decision**: pandas + openpyxl

**Rationale**:
- pandas provides powerful data manipulation for validation
- openpyxl reads .xlsx files with full format support
- Memory-efficient chunked reading for large files
- Industry standard for Python data processing

**Alternatives Considered**:
- xlrd: Only supports older .xls format
- polars: Faster but less ecosystem integration

## Best Practices Research

### RBAC Implementation Pattern

**Pattern**: Permission-based authorization with role composition

```
User -> [Roles] -> [Permissions] -> Protected Resources
```

- Permissions are atomic (e.g., `users:read`, `users:write`, `roles:manage`)
- Roles aggregate permissions (e.g., `Admin` = all permissions)
- Users can have multiple roles; effective permissions = union
- Middleware checks permissions, not roles, for flexibility

### API Security Best Practices

1. **Rate limiting**: Use `slowapi` or `fastapi-limiter` to prevent brute force
2. **CORS**: Strict origin validation, no wildcards in production
3. **Input validation**: Pydantic models for all request bodies
4. **SQL injection**: SQLAlchemy parameterized queries (automatic)
5. **CSRF**: Not needed for JWT API, but SameSite cookies help

### Excel Import Architecture

**Pattern**: Background task queue with progress tracking

1. Upload endpoint accepts file, returns job ID immediately
2. Background worker (via `asyncio` or Celery for scale) processes file
3. Progress stored in database or Redis, polled by frontend
4. Validation errors collected per row, returned in summary
5. Transactional import: all-or-nothing with rollback on failure

### Audit Logging Pattern

**Pattern**: Append-only audit table with structured events

```
audit_log:
  - id: UUID
  - timestamp: datetime (UTC)
  - user_id: FK (nullable for system events)
  - action: enum (LOGIN, LOGOUT, CREATE, UPDATE, DELETE, PERMISSION_DENIED)
  - resource_type: string
  - resource_id: string (nullable)
  - details: JSONB (before/after for changes)
  - ip_address: string
```

- Immutable records (no UPDATE/DELETE on audit table)
- Query by user, resource, time range, action type

## Resolved Unknowns

| Unknown | Resolution | Source |
|---------|------------|--------|
| ORM choice | SQLAlchemy 2.0 | architecture.md mentions "SQLAlchemy ou Tortoise ORM" |
| Password hashing | Argon2id | OWASP recommendation, architecture.md mentions bcrypt/argon2 |
| Session mechanism | JWT with HTTPOnly cookies | architecture.md mentions "JWT ou session HTTPOnly" |
| Frontend framework | React/TypeScript | architecture.md mentions "React ou Vue.js" - React selected for ecosystem |
| Import queue strategy | Async background tasks | Derived from performance requirements |

## Open Questions for Implementation

1. **Database migrations**: Use Alembic with autogenerate for initial schema
2. **Environment config**: Use Pydantic Settings with `.env` file support
3. **Logging**: Structured JSON logging with `structlog` for production
4. **Docker**: Containerize backend and frontend for consistent deployment

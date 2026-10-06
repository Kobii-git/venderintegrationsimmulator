# Contributing

Coding standards and conventions for the Integration Simulator.

## General principles

- **Vendor-neutral core** — no product-specific branching in `backend/app/` outside `products/` loading.
- **Minimal scope** — implement only what the current phase requires.
- **Boring engineering** — prefer readable code over clever abstractions.
- **Document decisions** — architectural changes go in `docs/DECISIONS.md`.

## Python (backend)

### Style

- Python 3.12+
- Format with **Ruff** (`ruff format`)
- Lint with **Ruff** (`ruff check`)
- Type hints on all public functions and methods
- Use `from __future__ import annotations` where helpful for forward refs

### Structure

| Package | Purpose |
|---------|---------|
| `app/api/` | Routes and API-specific Pydantic schemas |
| `app/services/` | Business logic orchestration |
| `app/domain/` | Enums, protocols, shared domain types |
| `app/models/` | SQLAlchemy ORM models |
| `app/core/` | Config, DB, cross-cutting utilities |
| `app/products/` | Product registry (code) |
| `app/transports/` | Transport implementations |
| `app/auth_strategies/` | Auth strategy implementations |

**Rule:** API routes are thin — delegate to services.

### Naming

- Modules: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- API paths: `kebab-case` segments, e.g. `/api/v1/event-instances`

### SQLAlchemy

- SQLAlchemy 2.x declarative style with `Mapped` / `mapped_column`
- Migrations via Alembic only — no manual schema edits in production

### Pydantic

- Pydantic v2 models for settings, manifests, API I/O
- Use `model_config = ConfigDict(...)` not class-based `Config`

### Testing

- **pytest** with `pytest-asyncio` where async code exists
- Tests in `backend/tests/`
- Name tests `test_<behaviour>`
- Prefer unit tests for domain logic; integration tests for API + DB

### Secrets in code

- Never log credentials
- Use `SecretStr` in settings for env vars
- See `docs/SECURITY.md`

## TypeScript (frontend)

### Style

- **ESLint** + **Prettier** (via project config)
- Strict TypeScript (`strict: true`)
- Functional React components with hooks
- No default exports except `main.tsx` and lazy routes if added later

### Structure

```text
src/
  api/          # API client and types
  components/   # Reusable UI sections and controls
  pages/        # Route-level views
  types/        # Shared TS types mirroring API
```

### API client

- Centralise fetch in `api/client.ts`
- Mirror backend `/api/v1` paths
- Type responses; handle errors consistently

## Git

- Meaningful commit messages (imperative mood, e.g. "Add health endpoint")
- One logical change per commit when possible
- Do not commit `.env`, secrets, or `/data` contents

## Docker

- Single production image (backend + built frontend)
- `/data` volume for SQLite and persistent config
- Set `SECRET_KEY` or retain the generated `/data/.secret_key` with the persistent volume

## Adding a product module

See [docs/PRODUCT_MODULE_SPEC.md](docs/PRODUCT_MODULE_SPEC.md). Do not modify core code unless adding a new transport or auth method.

## Scope discipline

Check the capability and deferred-work ledger in [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md). New scope requires acceptance criteria and an update to the decision log.

# Architecture — Backend (FastAPI)

## Stack
- FastAPI
- PostgreSQL (Docker)
- SQLAlchemy 2.0 + Alembic
- JWT Auth (access + refresh)
- Pydantic
- pytest

## Estructura (propuesta)
app/
  api/            # routers (sin lógica de negocio)
  core/           # settings, security, config
  db/             # session, base, init
  models/         # SQLAlchemy models
  schemas/        # Pydantic schemas (request/response)
  services/       # lógica de negocio
  utils/          # helpers
tests/            # pytest (puede ir /tests en raíz o dentro de app)

## Reglas
- Routes → llaman services
- Services → usan DB session y encapsulan reglas
- Models → solo DB
- Schemas → validación/serialización

## Feature checklist
Cada feature debe incluir:
- router/endpoint
- service (lógica)
- schema(s) Pydantic
- tests
- docs (si aplica)
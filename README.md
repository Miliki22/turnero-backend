# Turnero Backend (Kala Turnos)

Backend del sistema Turnero (marca actual: **Kala Turnos**).

## Stack
- FastAPI
- PostgreSQL (Docker)
- SQLAlchemy 2.0 + Alembic
- JWT (próximo paso)
- pytest

## Requisitos
- Python 3.12+ (o 3.11+)
- Docker Desktop
- (Opcional) DBeaver

## Setup (macOS / Linux)
### 1) Levantar PostgreSQL
```bash
docker compose up -d
docker ps
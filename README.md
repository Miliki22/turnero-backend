# Turnero Backend (Kala Turnos)

Backend del sistema Turnero (marca actual: **Kala Turnos**).

## Stack
- FastAPI
- PostgreSQL (Docker)
- SQLAlchemy 2.0 + Alembic
- JWT (access + refresh)
- pytest

## Requisitos
- Python 3.11+
- Docker Desktop

## Setup (macOS / Linux)
### 1) Levantar PostgreSQL
```bash
docker compose up -d
```

### 2) Instalar dependencias
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Configurar variables de entorno
```bash
cp .env.example .env
```

### 4) Aplicar migraciones
```bash
./scripts/alembic.sh upgrade head
```

## Auth admin-only (Etapa 1)
### Crear primer admin
```bash
python scripts/create_admin.py --email admin@kala.com --password 'TuPasswordSegura123'
```

### Login
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@kala.com","password":"TuPasswordSegura123"}'
```

### Perfil autenticado (/auth/me)
```bash
curl http://127.0.0.1:8000/api/v1/auth/me \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## Ejecutar tests
```bash
pytest -q
```

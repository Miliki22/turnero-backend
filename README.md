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

## CRUD Clientes (MVP, admin-only)
### Crear cliente
```bash
curl -X POST http://127.0.0.1:8000/api/v1/clients \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Juan Perez",
    "phone": "+5491112345678",
    "email": "juan@example.com",
    "notes": "Cliente frecuente"
  }'
```

### Listar clientes activos (default)
```bash
curl http://127.0.0.1:8000/api/v1/clients \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Listar incluyendo inactivos
```bash
curl "http://127.0.0.1:8000/api/v1/clients?include_inactive=true" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Obtener cliente por ID
```bash
curl http://127.0.0.1:8000/api/v1/clients/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Actualizar cliente (PATCH)
```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/clients/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"notes":"Actualizar observaciones","phone":"+5491199998888"}'
```

### Borrado lógico (soft delete)
```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/clients/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -i
```

## Ejecutar tests
```bash
pytest -q
```

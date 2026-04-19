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

Incluye MailHog para emails en desarrollo:
- SMTP: `localhost:1025`
- UI: `http://localhost:8025`

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

Variables de email DEV (MailHog):
- `EMAIL_ENABLED=true`
- `SMTP_HOST=localhost`
- `SMTP_PORT=1025`
- `EMAIL_FROM="Turnero Kala <no-reply@kala.local>"`
- `ADMIN_NOTIFY_EMAIL=admin@kala.local`

### 4) Aplicar migraciones
```bash
./scripts/alembic.sh upgrade head
```

## Reset DB (borrar volumen y recrear)
```bash
docker compose down -v
docker compose up -d
./scripts/alembic.sh upgrade head
```

Opcional (crear admin):
```bash
PYTHONPATH=. .venv/bin/python scripts/create_admin.py --email admin@kala.com --password "TuPasswordSegura123"
```

## Comandos Windows (PowerShell)
### Levantar PostgreSQL
```powershell
docker compose up -d
```

### Aplicar migraciones (equivalente)
```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### Crear admin
```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe scripts\create_admin.py --email admin@kala.com --password "TuPasswordSegura123"
```

## Endpoints útiles
- Health: `GET /health`
- Swagger: `/docs`

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


## CRUD Servicios (MVP, admin-only)
### Crear servicio
```bash
curl -X POST http://127.0.0.1:8000/api/v1/services \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Corte de pelo",
    "description": "Corte clásico",
    "duration_minutes": 45,
    "price": "12000.50"
  }'
```

### Listar servicios activos (default)
```bash
curl http://127.0.0.1:8000/api/v1/services \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Listar incluyendo inactivos
```bash
curl "http://127.0.0.1:8000/api/v1/services?include_inactive=true" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Obtener servicio por ID
```bash
curl http://127.0.0.1:8000/api/v1/services/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Actualizar servicio (PATCH)
```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/services/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"duration_minutes":60,"price":"15000.00"}'
```

### Borrado lógico (soft delete)
```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/services/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -i
```

## CRUD Turnos (MVP, admin-only)
`POST /appointments`: si no enviás `end_at`, se calcula con `service.duration_minutes`.

### Login (obtener token)
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@kala.com","password":"TuPasswordSegura123"}'
```

### Crear turno
```bash
curl -X POST http://127.0.0.1:8000/api/v1/appointments \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 1,
    "service_id": 1,
    "start_at": "2026-04-10T14:00:00+00:00",
    "notes": "Turno de prueba"
  }'
```

### Listar turnos activos
```bash
curl http://127.0.0.1:8000/api/v1/appointments \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Listar con filtros
```bash
curl "http://127.0.0.1:8000/api/v1/appointments?client_id=1&date_from=2026-04-10T00:00:00+00:00&date_to=2026-04-11T00:00:00+00:00" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## Ejecutar tests
```bash
pytest -q
```

## Validación manual MailHog
1. Levantar servicios:
```bash
docker compose up -d
```
2. Levantar backend y crear un turno con usuario `client`.
3. Abrir `http://localhost:8025` y verificar 2 emails:
- 1 al cliente autenticado
- 1 a `ADMIN_NOTIFY_EMAIL`

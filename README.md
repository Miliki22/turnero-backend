# Turnero Backend (FastAPI)

Backend del sistema **Turnero** (white-label).  

Incluye autenticación (admin + client), CRUD (clientes/servicios/turnos), disponibilidad para clientes y sincronización opcional con Google Calendar.

> El branding visual (ej. **Experiencia Kala**) vive en el **frontend** (presets). Este repo es API + DB.

## Stack
- FastAPI
- PostgreSQL (Docker)
- SQLAlchemy 2.0 + Alembic
- JWT (access + refresh)
- pytest
- MailHog (emails en dev)

---

## Requisitos
- Python 3.11+
- Docker Desktop

---

## Quick start (macOS / Linux)
### 1) Levantar PostgreSQL + MailHog
```bash
docker compose up -d
```

## MailHog (dev):
- SMTP: `localhost:1025`
- UI: `http://localhost:8025`

### 2) Instalar dependencias
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3) Variables de entorno
```bash
cp .env.example .env
```

## Variables de email DEV (MailHog):
- `EMAIL_ENABLED=true`
- `SMTP_HOST=localhost`
- `SMTP_PORT=1025`
- `EMAIL_FROM="Turnero Kala <no-reply@kala.local>"`
- `ADMIN_NOTIFY_EMAIL=admin@kala.local`

### 4) Migraciones
```bash
./scripts/alembic.sh upgrade head
```

## Reset DB (borrar volumen y recrear)
```bash
docker compose down -v
docker compose up -d
./scripts/alembic.sh upgrade head
```

### 5)Opcional (crear admin):
```bash
PYTHONPATH=. .venv/bin/python scripts/create_admin.py \ 
    --email admin@kala.com 
    --password "TuPasswordSegura123"
```

### 6) Correr API (módulo de arranque: main.py)
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Reset DB (borrar volumen y recrear)
```bash
docker compose down -v
docker compose up -d
./scripts/alembic.sh upgrade head
```

## Windows (PowerShell)
### Levantar PostgreSQL
```powershell
docker compose up -d
```

### Migraciones (equivalente)
```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### Crear admin
```powershell
$env:PYTHONPATH="."
.\.venv\Scripts\python.exe scripts\create_admin.py --email admin@kala.com --password "TuPasswordSegura123"
```

### Correr API
```bash
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Endpoints útiles
- Health: `GET /health`
- Swagger: `/docs`

## Auth (admin)
### Login
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@kala.com","password":"TuPasswordSegura123"}'
  ```

## Perfil Autenticado
```bash
 curl http://127.0.0.1:8000/api/v1/auth/me \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
---
## CRUD (admin-only)

## Clientes
### Crear:
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

### Listar:
```bash
curl http://127.0.0.1:8000/api/v1/clients \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
  ```

### Listar incluyendo inactivos:
```bash
curl "http://127.0.0.1:8000/api/v1/clients?include_inactive=true" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Obtener por ID:
```bash
curl http://127.0.0.1:8000/api/v1/clients/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Actualizar (PATCH):
```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/clients/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"notes":"Actualizar observaciones","phone":"+5491199998888"}'
```

### Soft delete:
```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/clients/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>" -i
```
---

## Servicios
### Crear:
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

### Listar activos:
```bash
curl http://127.0.0.1:8000/api/v1/services \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Listar incluyendo inactivos:
```bash
curl "http://127.0.0.1:8000/api/v1/services?include_inactive=true" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Obtener por ID:
```bash
curl http://127.0.0.1:8000/api/v1/services/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### Actualizad (PATCH):
```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/services/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"duration_minutes":60,"price":"15000.00"}'
  ```

### Soft delete:
```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/services/1 \
  -H "Authorization: Bearer <ACCESS_TOKEN>" -i
  ```
---

## Turnos
### Crear (si no envias end_at, se calcula con service.duration_minutes):
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

### Listar:
```bash
curl http://127.0.0.1:8000/api/v1/appointments \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
  ```

### Listar con filtros:
```bash
curl "http://127.0.0.1:8000/api/v1/appointments?client_id=1&date_from=2026-04-10T00:00:00+00:00&date_to=2026-04-11T00:00:00+00:00" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```
---

## Flujo Cliente (reserva)
### Servicios disponibles (client)
```bash
curl http://127.0.0.1:8000/api/v1/client/services \
  -H "Authorization: Bearer <ACCESS_TOKEN_CLIENT>"
```

### Disponibilidad por servicio
```bash
curl "http://127.0.0.1:8000/api/v1/client/availability?service_id=1&range=week&start_date=2026-04-27" \
  -H "Authorization: Bearer <ACCESS_TOKEN_CLIENT>"
```
* range: week o fortnight (default week)
* strat_date: YYY-MM-DD (opcional)

### Reservar turno
```bash
curl -X POST http://127.0.0.1:8000/api/v1/client/appointments \
  -H "Authorization: Bearer <ACCESS_TOKEN_CLIENT>" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": 1,
    "start_at": "2026-04-27T10:00:00-03:00"
  }'
```

### Mis turnos
```bash
curl "http://127.0.0.1:8000/api/v1/client/appointments?limit=50&offset=0" \
  -H "Authorization: Bearer <ACCESS_TOKEN_CLIENT>"
```

## Google Calendar Sync (admin) - opcional
1. Crear credenciales OAuth 2.0 (Web application) en Google Cloud Console.
2. Guardar el archivo en `credentials/google_oauth/client_secret.json`.
3. Configurar variables:
```bash
GOOGLE_OAUTH_CLIENT_SECRETS_FILE=credentials/google_oauth/client_secret.json
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/integrations/google/callback
GOOGLE_CALENDAR_ID=primary
GOOGLE_SYNC_ENABLED=true
```
4. Conectar desde API:
- `GET /api/v1/integrations/google/connect`
- `GET /api/v1/integrations/google/callback`
- `GET /api/v1/integrations/google/status`
- `POST /api/v1/integrations/google/disconnect`
- `POST /api/v1/integrations/google/sync?days_ahead=90&include_past_days=0`
- `POST /api/v1/integrations/google/cleanup?days_ahead=365&include_past_days=30&dry_run=true`

## Ejemplo (obtener token OAuth2 estilo Swagger-compatible, form-urlencoded):
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@kala.com&password=TuPassSegura123!"
```

## Ejecutar sync/backfill:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/integrations/google/sync?days_ahead=90&include_past_days=0" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## Limpieza de eventos creados en calendario equivocado (legacy `primary`):
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/integrations/google/cleanup?days_ahead=365&include_past_days=30&dry_run=true" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## Notas:
- No commitear secretos OAuth.
- `.gitignore` debe exluir `credentials/google_oauth/*.json`.

## Tests
```bash
pytest -q
```

## Validación MailHog (manual)
1. Levantar servicios:
```bash
docker compose up -d
```
2. Levantar backend y crear un turno con usuario `client`.
3. Abrir `http://localhost:8025` y verificar 2 emails:
- 1 al cliente autenticado
- 1 a `ADMIN_NOTIFY_EMAIL`

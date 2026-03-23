# Decisions Log

## 2026-03-23
- Auth etapa 1 implementada como admin-only (`/api/v1/auth/login` y `/api/v1/auth/me`).
- JWT con claim explícito `token_type` (`access` / `refresh`).
- `get_current_user` acepta solo `token_type=access`.
- Bootstrap inicial de admin vía script `scripts/create_admin.py`.

## 2026-03-20
- Producto: "Kala Turnos"
- Repos: turnero-backend / turnero-frontend (plantilla reusable)
- Backend: FastAPI + PostgreSQL + SQLAlchemy 2.0 + Alembic
- Auth: JWT access + refresh
- Roles: admin (panel) + client (autogestión turnos)
- Frontend: React + Vite + Tailwind (se crea mañana)
- Idioma: Español
- Estilo: spa (beige/arena)
- Turnos: 60/90/120
- Horario base: Lun–Vie 09:00–19:00
- Timezone: America/Argentina/Buenos_Aires
- DB Client: DBeaver
- Recordatorios por email: Etapa 2
- Commits manuales del usuario, ramas por feature/área

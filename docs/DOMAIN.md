# Dominio (MVP)

## Roles
- **admin**: panel total (clientes/servicios/turnos + métricas)
- **client**: ver servicios y autogestionar turnos (crear/cancelar) + ver sus turnos

## Entidades (campos mínimos)

### User
- id
- email (único)
- password_hash
- role: admin | client
- is_active
- created_at

### Client (perfil del cliente)
- id
- user_id (opcional al inicio; ideal: 1-1 con User role=client)
- full_name
- phone (opcional)
- notes (opcional)
- created_at

### Service
- id
- name
- description (opcional)
- duration_minutes (permitidas: 60/90/120) *(si se maneja por servicio)*
- price (opcional, etapa 2 si querés)
- is_active
- created_at

### Appointment (Turno)
- id
- client_id
- service_id
- start_at (datetime con tz)
- duration_minutes (60/90/120)
- status: scheduled | cancelled
- notes (opcional)
- created_at

## Reglas MVP
- No se permiten turnos solapados (por agenda / profesional)
- Solo Lun–Vie 09:00–19:00
- duration_minutes ∈ {60, 90, 120}
- Timezone: America/Argentina/Buenos_Aires
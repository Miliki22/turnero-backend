# Turnero — Project Rules

## Objetivo
Sistema de gestión de turnos para profesionales independientes.
Marca actual: **"Kala Turnos"** (branding configurable).

## MVP (alcance)
- Auth (JWT access + refresh)
- Roles: **admin** (panel) y **client** (autogestión turnos)
- CRUD: Clientes, Servicios, Turnos
- Reglas: no solapamiento, horario Lun–Vie 09–19, duraciones 60/90/120
- UI: Tailwind (frontend en repo separado, se crea mañana)

## Principios
- Código limpio y modular
- Separación clara de responsabilidades
- Validación server-side obligatoria
- Seguridad por defecto
- Cambios chicos, testeables y documentados

## Regla: Código simple y mantenible (anti-mega-archivos)
- Priorizar soluciones simples y reutilizables.
- Evitar archivos gigantes: si un archivo crece demasiado, refactorizar.
- Extraer lógica repetida a funciones/helpers o servicios.
- Usar librerías/frameworks cuando corresponda en vez de “reinventar la rueda”.
- Mantener funciones pequeñas y con una sola responsabilidad.
- Preferir composición (helpers/services) antes que “todo en una ruta”.

## Límites recomendados (guías, no dogma)
- Funciones: ideal < 40 líneas
- Archivos: ideal < 300 líneas (si crece, dividir por módulo/responsabilidad)

## Reglas del trabajo con Codex
- Leer `/docs` antes de actuar
- Proponer cambios y esperar confirmación
- No commitear (commits manuales del usuario)
- Tests obligatorios en cada feature
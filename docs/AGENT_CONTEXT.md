# Agent Context — Turnero (Codex / VS Code)

Este proyecto se desarrolla con Codex en modo agente.

## Regla #1: Proponer antes de aplicar
Antes de modificar archivos, el agente DEBE:
1) Leer la carpeta `/docs`
2) Proponer el cambio: lista de archivos + resumen + impacto + cómo probarlo
3) Esperar confirmación del usuario (Miliki) para aplicar cambios

## Regla #2: No commitear
El agente NO debe hacer commits. Los commits los hace el usuario.

## Regla #3: Respetar arquitectura
- No cambiar estructura de carpetas sin justificarlo.
- No poner lógica de negocio en rutas/controladores.
- Toda lógica va en `services/`.
- Modelos DB en `models/`.

## Regla #4: Calidad, simplicidad y refactor
- Priorizar buenas prácticas y código mantenible.
- Evitar archivos gigantes: si un archivo crece demasiado, refactorizar/dividir.
- Extraer lógica repetida a helpers/services.
- Usar librerías cuando corresponda en vez de reinventar la rueda.
- Mantener funciones pequeñas y con una sola responsabilidad.

## Regla #5: Testing y estándares
- Cada feature debe incluir tests (pytest).
- PEP8 + type hints + docstrings.
- No dejar prints/debug.

## Regla #6: Documentación mínima
Cuando se agregue funcionalidad:
- Actualizar `/docs/DECISIONS.md` si hubo decisión nueva
- Actualizar README si cambia setup/comandos
- Documentar endpoints en `/docs/API.md` (cuando exista)
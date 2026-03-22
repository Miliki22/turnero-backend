# Security Rules

- Hash passwords con bcrypt
- JWT access + refresh
- Secrets en `.env` (nunca hardcode)
- Validación server-side obligatoria (Pydantic + reglas)
- No exponer stack traces en producción
- Manejo de errores consistente (mensajes claros)
- CORS configurado explícitamente
- Timezone fija: America/Argentina/Buenos_Aires
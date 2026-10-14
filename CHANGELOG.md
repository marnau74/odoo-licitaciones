# Cambios

Formato de [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versiones con el esquema de Odoo
(`19.0.x.y.z`).

## [19.0.1.0.0] - 2026-10-14

Primera versión.

### Añadido

- Perfiles de búsqueda (CPV, provincias, importes, palabras) con su comercial.
- Importación diaria desde la API del radar, por lotes y sin duplicados, con los órganos de contratación como
  contactos.
- Licitaciones con kanban por etapa, lista, búsqueda, gráfico, tabla dinámica e informe PDF.
- Conversión en oportunidad del CRM con el órgano como cliente (reutilizado por NIF) y una tarea antes del fin del
  plazo.
- Grupos Usuario y Responsable, reglas multiempresa y traducción al español.
- Pruebas con respuestas reales grabadas del radar y un recorrido de la interfaz; CI con Odoo en Docker.

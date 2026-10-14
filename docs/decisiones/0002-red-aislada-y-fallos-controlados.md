# 2. La red, aislada en un modelo y con los fallos controlados

## Contexto

El módulo depende de un servicio externo, el radar. Una llamada HTTP sin tiempo de espera puede dejar colgado un
trabajador de Odoo; un fallo a mitad de la importación puede dejar la mitad de las licitaciones; y una acción
programada que lanza una excepción se reintenta y llena el registro.

## Decisión

- **Todo el acceso a la red está en `radar.cliente`** (modelo abstracto): tiempo de espera de conexión y de lectura,
  tres intentos con espera creciente para los fallos de red y los 5xx, y ningún reintento para los 4xx, que son un
  error de la petición. Cualquier fallo sale como `RadarError`, con un mensaje traducible.
- **La importación es todo o nada por perfil**: primero se traen todas las páginas y después se guarda. En la acción
  programada, cada perfil va en su propio *savepoint*: si el radar falla, ese perfil se deshace, el error se guarda
  en el perfil (la ficha lo enseña en rojo) y los demás perfiles siguen. La acción no lanza nunca.
- **Desde la interfaz**, el mismo error se enseña al usuario (`UserError`) y no se crea nada.
- **Las pruebas no tocan la red**: se sustituye `requests.get` por un radar falso que sirve respuestas reales
  grabadas (`tests/datos`) y deja pasar el resto de peticiones, que en las pruebas de interfaz son las del propio
  navegador de las pruebas.

## Alternativas descartadas

- **Hacer la conversión sin pedir la ficha al radar**: más rápido, pero el listado no trae el NIF del órgano y sin él
  no se puede reconocer a un cliente que ya existía.
- **Encolar la importación** (`queue_job` de la OCA): útil con muchos perfiles, pero añade una dependencia que no
  hace falta para una importación diaria de unos cientos de registros.

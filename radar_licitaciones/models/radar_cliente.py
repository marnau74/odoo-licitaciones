import logging
import time

import requests

from odoo import api, models

_logger = logging.getLogger(__name__)

# Conexión y lectura: una caída del radar no puede dejar colgado un trabajador de Odoo.
TIEMPO_DE_ESPERA = (5, 30)
INTENTOS = 3


class RadarError(Exception):
    """El radar no ha respondido o ha respondido con un error."""


class RadarCliente(models.AbstractModel):
    """Cliente HTTP de la API pública del radar de licitaciones.

    Todo el acceso a la red pasa por aquí, con tiempo de espera: en las pruebas se sustituye la llamada HTTP por las
    respuestas grabadas del radar. Reintenta los fallos de red y los 5xx; un 4xx es un error de la petición y no se
    repite.
    """

    _name = "radar.cliente"
    _description = "Tender radar API client"

    @api.model
    def _url_base(self):
        # El parámetro solo lo puede leer un administrador; el resto de usuarios necesita la URL para el enlace.
        url = self.env["ir.config_parameter"].sudo().get_param("radar_licitaciones.url") or ""
        if not url:
            raise RadarError(self.env._("The tender radar URL is not configured (Settings → Tender radar)."))
        return url.rstrip("/")

    @api.model
    def buscar(self, parametros):
        """Una página de la búsqueda (``/api/v1/licitaciones``): ``{"elementos": [...], "total": n, "paginas": n}``."""
        return self._get("/api/v1/licitaciones", parametros)

    @api.model
    def detalle(self, radar_id):
        """La ficha de una licitación, con el órgano de contratación completo (NIF, ciudad, web)."""
        return self._get(f"/api/v1/licitaciones/{int(radar_id)}")

    @api.model
    def _get(self, ruta, parametros=None):
        url = self._url_base() + ruta
        for intento in range(1, INTENTOS + 1):
            try:
                respuesta = requests.get(
                    url,
                    params=parametros,
                    timeout=TIEMPO_DE_ESPERA,
                    headers={"Accept": "application/json", "User-Agent": "odoo-radar-licitaciones/19.0"},
                )
            except requests.RequestException as error:
                motivo = str(error)
            else:
                if respuesta.ok:
                    return respuesta.json()
                if respuesta.status_code < 500:
                    raise RadarError(
                        self.env._(
                            "The tender radar rejected the request (%(status)s): %(url)s",
                            status=respuesta.status_code,
                            url=respuesta.url,
                        )
                    )
                motivo = f"HTTP {respuesta.status_code}"
            _logger.warning("Radar: intento %s de %s fallido en %s: %s", intento, INTENTOS, url, motivo)
            if intento < INTENTOS:
                time.sleep(2**intento)
        raise RadarError(self.env._("The tender radar is not responding (%(reason)s).", reason=motivo))

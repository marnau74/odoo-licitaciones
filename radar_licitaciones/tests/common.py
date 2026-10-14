import copy
import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import requests

from odoo.tests import TransactionCase

DATOS = Path(__file__).parent / "datos"
URL = "http://radar.test"
# El parche cambia requests.get para todo el proceso: lo que no va al radar (el navegador de las pruebas de la
# interfaz, por ejemplo) sigue yendo a la red de verdad.
_GET_DE_VERDAD = requests.get


def leer(nombre):
    return json.loads((DATOS / nombre).read_text(encoding="utf-8"))


class RespuestaFalsa:
    def __init__(self, cuerpo=None, status_code=200, url=""):
        self._cuerpo = cuerpo
        self.status_code = status_code
        self.url = url

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return copy.deepcopy(self._cuerpo)


class RadarFalso:
    """Hace de radar con respuestas reales grabadas (tests/datos): la búsqueda de servicios TI (CPV 72) en Murcia y
    Valencia y tres fichas. Guarda las peticiones para comprobar qué se ha pedido."""

    def __init__(self):
        self.busqueda = leer("busqueda.json")
        self.peticiones = []
        self.caido = False
        self.estado_forzado = None

    def get(self, url, params=None, timeout=None, headers=None, **kwargs):
        if not url.startswith(URL):
            return _GET_DE_VERDAD(url, params=params, timeout=timeout, headers=headers, **kwargs)
        self.peticiones.append({"url": url, "params": params, "timeout": timeout})
        if self.caido:
            raise requests.ConnectionError("Connection refused")
        if self.estado_forzado:
            return RespuestaFalsa({"title": "Error"}, status_code=self.estado_forzado, url=url)
        ruta = urlparse(url).path
        if ruta == "/api/v1/licitaciones":
            return RespuestaFalsa(self._pagina(int((params or {}).get("pagina", 1))), url=url)
        radar_id = ruta.rsplit("/", 1)[-1]
        fichero = DATOS / f"detalle-{radar_id}.json"
        if fichero.exists():
            return RespuestaFalsa(leer(fichero.name), url=url)
        return RespuestaFalsa({"title": "No encontrada"}, status_code=404, url=url)

    def _pagina(self, pagina):
        return self.busqueda if pagina == 1 else dict(self.busqueda, elementos=[])

    def busquedas(self):
        return [p for p in self.peticiones if urlparse(p["url"]).path == "/api/v1/licitaciones"]


class RadarCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("radar_licitaciones.url", URL)
        cls.env.user.tz = "Europe/Madrid"
        cls.murcia = cls.env.ref("base.state_es_mu")
        cls.valencia = cls.env.ref("base.state_es_v")
        cls.perfil = cls.env["radar.perfil"].create(
            {
                "name": "Servicios TI en Murcia y Valencia",
                "cpv": "72",
                "state_ids": [(6, 0, (cls.murcia | cls.valencia).ids)],
                "importe_minimo": 15000,
            }
        )

    def setUp(self):
        super().setUp()
        self.radar = RadarFalso()
        parche = patch("odoo.addons.radar_licitaciones.models.radar_cliente.requests.get", side_effect=self.radar.get)
        self.startPatcher(parche)
        # Los reintentos esperan unos segundos entre intento e intento; en las pruebas, no.
        self.startPatcher(patch("odoo.addons.radar_licitaciones.models.radar_cliente.time.sleep"))

    def importar(self, perfil=None):
        return (perfil or self.perfil)._importar()

    def licitacion(self, radar_id):
        return self.env["radar.licitacion"].search([("radar_id", "=", radar_id)])

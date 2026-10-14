from datetime import date, datetime

from odoo.tests import freeze_time, tagged
from odoo.tools import mute_logger

from ..models.radar_cliente import RadarError
from .common import RadarCase


@tagged("post_install", "-at_install")
class TestImportacion(RadarCase):
    def test_parametros_de_la_busqueda(self):
        parametros = self.perfil._parametros_de_busqueda(date(2026, 9, 1))
        self.assertEqual(
            {**parametros, "nuts": sorted(parametros["nuts"])},
            {
                "cpv": ["72"],
                "nuts": ["ES523", "ES620"],
                "importeMin": 15000,
                "abiertas": "true",
                "publicadaDesde": "2026-09-01",
                "orden": "publicacion",
                "tamano": 100,
            },
        )

    def test_una_provincia_con_varias_regiones_nuts(self):
        self.perfil.state_ids = self.env.ref("base.state_es_pm")
        self.assertEqual(self.perfil._parametros_de_busqueda(date(2026, 9, 1))["nuts"], ["ES531", "ES532", "ES533"])

    def test_importa_las_licitaciones_con_sus_datos(self):
        nuevas, actualizadas = self.importar()

        self.assertEqual(len(nuevas), 37)
        self.assertFalse(actualizadas)
        soc = self.licitacion(20480431)
        self.assertRecordValues(
            soc,
            [
                {
                    "name": "Servicio de SOC/MDR y Herramientas de Ciberseguridad para el Ayuntamiento de Cartagena.",
                    "expediente": "SE2026/44",
                    "importe": 585000.0,
                    # 23:59 en Madrid es 21:59 en UTC, que es como lo guarda Odoo.
                    "plazo": datetime(2026, 10, 20, 21, 59),
                    "fecha_publicacion": date(2026, 9, 20),
                    "estado": "PUB",
                    "tipo_contrato": "2",
                    "cpv": "72250000, 72514300, 48730000",
                    "cpv_division": "72",
                    "nuts": "ES620",
                    "state_id": self.murcia.id,
                    "lugar": "Murcia",
                    "etapa": "nueva",
                    "perfil_id": self.perfil.id,
                    "company_id": self.env.company.id,
                }
            ],
        )
        self.assertEqual(soc.organo_id.name, "Junta de Gobierno Local del Ayuntamiento de Cartagena")
        self.assertEqual(soc.organo_id.radar_organo_id, 850)
        self.assertEqual(soc.url, "http://radar.test/licitaciones/20480431")
        self.assertEqual(self.perfil.licitacion_count, 37)
        self.assertTrue(self.perfil.ultima_importacion)

    def test_repetir_la_importacion_no_duplica_nada(self):
        self.importar()
        organos = self.env["res.partner"].search_count([("radar_organo_id", "!=", False)])

        nuevas, actualizadas = self.importar()

        self.assertFalse(nuevas)
        self.assertFalse(actualizadas)
        self.assertEqual(self.env["radar.licitacion"].search_count([]), 37)
        self.assertEqual(self.env["res.partner"].search_count([("radar_organo_id", "!=", False)]), organos)
        self.assertEqual(organos, 29)

    def test_los_cambios_del_radar_se_actualizan_y_quedan_en_el_historial(self):
        self.importar()
        # Como si la importación de ayer ya estuviera confirmada: Odoo no sigue los cambios de un registro creado en la
        # misma transacción, y el seguimiento se escribe al confirmar.
        self.env.flush_all()
        self.env.cr.precommit.run()
        soc = self.licitacion(20480431)
        elemento = next(e for e in self.radar.busqueda["elementos"] if e["id"] == 20480431)
        elemento.update(estado="ADJ", importeSinIva=560000.0)

        nuevas, actualizadas = self.importar()

        self.assertFalse(nuevas)
        self.assertEqual(actualizadas, soc)
        self.assertEqual((soc.estado, soc.importe), ("ADJ", 560000.0))
        self.env.flush_all()
        self.env.cr.precommit.run()
        seguimiento = self.env["mail.tracking.value"].search([("mail_message_id", "in", soc.message_ids.ids)])
        self.assertEqual(seguimiento.field_id.mapped("name"), ["estado"])

    def test_trae_todas_las_paginas(self):
        elementos = self.radar.busqueda["elementos"]
        paginas = {1: elementos[:20], 2: elementos[20:]}
        self.radar._pagina = lambda n: dict(self.radar.busqueda, elementos=paginas.get(n, []), paginas=2)

        nuevas, _actualizadas = self.importar()

        self.assertEqual(len(nuevas), 37)
        self.assertEqual([p["params"]["pagina"] for p in self.radar.busquedas()], [1, 2])

    def test_la_primera_importacion_mira_atras_y_las_siguientes_desde_la_ultima(self):
        with freeze_time("2026-10-14 06:00:00"):
            self.importar()
            self.assertEqual(self.radar.busquedas()[-1]["params"]["publicadaDesde"], "2026-09-14")
        with freeze_time("2026-10-15 06:00:00"):
            self.importar()
            # Desde el día antes de la última importación, por si el radar cargó tarde las de ese día.
            self.assertEqual(self.radar.busquedas()[-1]["params"]["publicadaDesde"], "2026-10-13")

    def test_cada_peticion_lleva_tiempo_de_espera(self):
        self.importar()
        self.assertTrue(all(p["timeout"] for p in self.radar.peticiones))

    @mute_logger(
        "odoo.addons.radar_licitaciones.models.radar_cliente", "odoo.addons.radar_licitaciones.models.radar_perfil"
    )
    def test_si_el_radar_falla_la_accion_programada_lo_apunta_y_sigue(self):
        otro = self.perfil.copy({"name": "Otro perfil"})
        self.radar.caido = True

        self.env["radar.perfil"]._cron_importar()

        self.assertIn("not responding", self.perfil.ultimo_error)
        self.assertIn("not responding", otro.ultimo_error)
        self.assertFalse(self.perfil.ultima_importacion)
        self.assertFalse(self.env["radar.licitacion"].search_count([]))
        # Tres intentos por perfil.
        self.assertEqual(len(self.radar.peticiones), 6)

    @mute_logger("odoo.addons.radar_licitaciones.models.radar_perfil")
    def test_sin_direccion_del_radar_no_importa_y_lo_dice(self):
        self.env["ir.config_parameter"].sudo().set_param("radar_licitaciones.url", "")

        self.env["radar.perfil"]._cron_importar()

        self.assertIn("not configured", self.perfil.ultimo_error)
        self.assertFalse(self.radar.peticiones)

    def test_un_error_de_la_peticion_no_se_reintenta_y_uno_del_servidor_si(self):
        self.radar.estado_forzado = 400
        with self.assertRaisesRegex(RadarError, "rejected the request"):
            self.importar()
        self.assertEqual(len(self.radar.peticiones), 1)

        self.radar.estado_forzado = 503
        with (
            mute_logger("odoo.addons.radar_licitaciones.models.radar_cliente"),
            self.assertRaisesRegex(RadarError, "HTTP 503"),
        ):
            self.importar()
        self.assertEqual(len(self.radar.peticiones), 4)

    def test_una_importacion_correcta_borra_el_error_anterior(self):
        self.perfil.ultimo_error = "El radar no responde"
        self.importar()
        self.assertFalse(self.perfil.ultimo_error)

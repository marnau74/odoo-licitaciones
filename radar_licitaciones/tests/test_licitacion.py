from datetime import date, datetime

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import freeze_time, tagged
from odoo.tools import mute_logger

from .common import RadarCase


@tagged("post_install", "-at_install")
class TestLicitacion(RadarCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comercial = cls.env["res.users"].create(
            {
                "name": "Laura Comercial",
                "login": "laura",
                "tz": "Europe/Madrid",
                "group_ids": [(6, 0, [cls.env.ref("radar_licitaciones.group_radar_usuario").id])],
            }
        )
        cls.perfil.user_id = cls.comercial

    def setUp(self):
        super().setUp()
        self.importar()
        self.soc = self.licitacion(20480431)

    # Validaciones

    def test_los_cpv_tienen_de_dos_a_ocho_cifras(self):
        self.perfil.cpv = "72, 4873"
        with self.assertRaisesRegex(ValidationError, "7"):
            self.perfil.cpv = "72, 7"
        with self.assertRaises(ValidationError):
            self.perfil.cpv = "72a"
        with self.assertRaises(ValidationError):
            self.perfil.cpv = "123456789"

    def test_el_importe_minimo_no_pasa_del_maximo(self):
        with self.assertRaises(ValidationError):
            self.perfil.write({"importe_minimo": 50000, "importe_maximo": 10000})

    @mute_logger("odoo.sql_db")
    def test_importes_negativos_no(self):
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.perfil.importe_minimo = -1
            self.perfil.flush_recordset()

    @mute_logger("odoo.sql_db")
    def test_la_misma_licitacion_no_se_importa_dos_veces_en_una_compania(self):
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.soc.copy()
            self.env.flush_all()

    # Plazo

    def test_dias_para_el_plazo_y_cierra_pronto(self):
        # Plazo: 20/10/2026 a las 21:59 UTC.
        with freeze_time("2026-10-14 10:00:00"):
            self.soc.invalidate_recordset(["dias_para_el_plazo", "cierra_pronto"])
            self.assertEqual(self.soc.dias_para_el_plazo, 6)
            self.assertFalse(self.soc.cierra_pronto)
        with freeze_time("2026-10-18 10:00:00"):
            self.soc.invalidate_recordset(["dias_para_el_plazo", "cierra_pronto"])
            self.assertEqual(self.soc.dias_para_el_plazo, 2)
            self.assertTrue(self.soc.cierra_pronto)
            self.assertIn(self.soc, self.env["radar.licitacion"].search([("cierra_pronto", "=", True)]))
            self.assertNotIn(self.soc, self.env["radar.licitacion"].search([("cierra_pronto", "=", False)]))
        with freeze_time("2026-10-21 10:00:00"):
            self.soc.invalidate_recordset(["dias_para_el_plazo", "cierra_pronto"])
            self.assertEqual(self.soc.dias_para_el_plazo, -1)
            self.assertFalse(self.soc.cierra_pronto)

    # Etapas

    def test_interesa_y_descartar(self):
        self.soc.action_interesa()
        self.assertEqual(self.soc.etapa, "interesa")
        self.soc.action_descartar()
        self.assertEqual(self.soc.etapa, "descartada")
        self.soc.action_interesa()
        self.assertEqual(self.soc.etapa, "interesa")

    # Conversión en oportunidad

    @freeze_time("2026-10-14 10:00:00")
    def test_convertir_crea_la_oportunidad_con_el_organo_como_cliente(self):
        self.soc.with_user(self.comercial).action_convertir()

        oportunidad = self.soc.lead_id
        self.assertRecordValues(
            oportunidad,
            [
                {
                    "name": self.soc.name,
                    "type": "opportunity",
                    "expected_revenue": 585000.0,
                    # El plazo acaba el 20 a las 23:59 en Madrid aunque en UTC sean las 21:59.
                    "date_deadline": date(2026, 10, 20),
                    "user_id": self.comercial.id,
                    "licitacion_id": self.soc.id,
                }
            ],
        )
        self.assertIn("SE2026/44", oportunidad.description)
        self.assertIn("http://radar.test/licitaciones/20480431", oportunidad.description)
        cliente = oportunidad.partner_id
        self.assertRecordValues(
            cliente,
            [
                {
                    "name": "Junta de Gobierno Local del Ayuntamiento de Cartagena",
                    "vat": "ESP3001600J",
                    "city": "Cartagena",
                    "zip": "30201",
                    "country_id": self.env.ref("base.es").id,
                }
            ],
        )
        self.assertEqual(self.soc.etapa, "convertida")
        self.assertIn("Converted into the opportunity", self.soc.message_ids[0].body)

    @freeze_time("2026-10-14 10:00:00")
    def test_convertir_programa_una_tarea_tres_dias_antes_del_plazo(self):
        self.soc.with_user(self.comercial).action_convertir()

        actividad = self.soc.lead_id.activity_ids
        self.assertEqual(len(actividad), 1)
        self.assertEqual(actividad.user_id, self.comercial)
        self.assertEqual(actividad.date_deadline, date(2026, 10, 17))
        self.assertEqual(actividad.summary, "Prepare the bid")

    @freeze_time("2026-10-19 10:00:00")
    def test_si_quedan_menos_de_tres_dias_la_tarea_es_para_hoy(self):
        self.soc.with_user(self.comercial).action_convertir()
        self.assertEqual(self.soc.lead_id.activity_ids.date_deadline, date(2026, 10, 19))

    def test_un_cliente_que_ya_existia_con_el_mismo_nif_se_reutiliza(self):
        de_siempre = self.env["res.partner"].create(
            {"name": "Ayuntamiento de Cartagena", "is_company": True, "vat": "ESP3001600J"}
        )
        importado = self.soc.organo_id
        otra = self.licitacion(20571268)
        self.assertEqual(otra.organo_id, importado)

        self.soc.action_convertir()

        self.assertEqual(self.soc.lead_id.partner_id, de_siempre)
        self.assertEqual(de_siempre.radar_organo_id, 850)
        # Las demás licitaciones del órgano pasan al cliente de siempre y el contacto importado se archiva.
        self.assertEqual(otra.organo_id, de_siempre)
        self.assertFalse(importado.active)
        # Y en la siguiente importación no se vuelve a crear.
        self.importar()
        self.assertEqual(self.env["res.partner"].search_count([("radar_organo_id", "=", 850)]), 1)

    def test_dos_licitaciones_del_mismo_organo_dan_un_solo_cliente(self):
        (self.soc | self.licitacion(20571268)).action_convertir()
        self.assertEqual(len(self.soc.lead_id | self.licitacion(20571268).lead_id), 2)
        self.assertEqual(self.soc.lead_id.partner_id, self.licitacion(20571268).lead_id.partner_id)

    def test_no_se_convierte_dos_veces(self):
        self.soc.action_convertir()
        with self.assertRaisesRegex(UserError, "already opportunities"):
            self.soc.action_convertir()

    @mute_logger("odoo.addons.radar_licitaciones.models.radar_cliente")
    def test_si_el_radar_no_responde_no_se_crea_nada(self):
        self.radar.caido = True
        oportunidades = self.env["crm.lead"].search_count([])
        with self.assertRaisesRegex(UserError, "not responding"):
            self.soc.action_convertir()
        self.assertEqual(self.env["crm.lead"].search_count([]), oportunidades)
        self.assertFalse(self.soc.lead_id)

    def test_desde_la_oportunidad_se_vuelve_a_la_licitacion(self):
        self.soc.action_convertir()
        accion = self.soc.lead_id.action_ver_licitacion()
        self.assertEqual((accion["res_model"], accion["res_id"]), ("radar.licitacion", self.soc.id))

    # Informe

    def test_el_informe_lleva_los_datos_de_la_licitacion(self):
        html, _tipo = self.env["ir.actions.report"]._render_qweb_html(
            "radar_licitaciones.report_licitacion", self.soc.ids
        )
        html = html.decode()
        self.assertIn("Servicio de SOC/MDR", html)
        self.assertIn("SE2026/44", html)
        self.assertIn("Junta de Gobierno Local del Ayuntamiento de Cartagena", html)
        self.assertIn("http://radar.test/licitaciones/20480431", html)

    def test_el_dia_del_plazo_es_el_de_la_zona_del_usuario(self):
        # 00:30 del 21 en Madrid (horario de verano, +02:00) son las 22:30 del 20 en UTC.
        self.soc.plazo = datetime(2026, 10, 20, 22, 30)
        self.assertEqual(self.soc.with_user(self.comercial)._dia_local(self.soc.plazo), date(2026, 10, 21))
        valores = self.soc.with_user(self.comercial)._valores_de_oportunidad(self.soc.organo_id)
        self.assertEqual(valores["date_deadline"], date(2026, 10, 21))

    def test_el_plazo_viene_en_utc(self):
        # Un plazo con desfase horario (+02:00) se guarda también en UTC.
        valores = self.env["radar.licitacion"]._valores_del_radar(
            {"id": 1, "titulo": "X", "plazoPresentacion": "2026-10-20T23:59:00+02:00"}
        )
        self.assertEqual(valores["plazo"], datetime(2026, 10, 20, 21, 59))

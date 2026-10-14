from unittest.mock import patch

from odoo.tests import HttpCase, tagged

from .common import URL, RadarFalso


@tagged("post_install", "-at_install")
class TestInterfaz(HttpCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("radar_licitaciones.url", URL)
        radar = RadarFalso()
        self.startPatcher(
            patch("odoo.addons.radar_licitaciones.models.radar_cliente.requests.get", side_effect=radar.get)
        )
        comercial = self.env["res.users"].create(
            {
                "name": "Laura Comercial",
                "login": "laura",
                "password": "laura",
                "group_ids": [(6, 0, [self.env.ref("radar_licitaciones.group_radar_usuario").id])],
            }
        )
        perfil = self.env["radar.perfil"].create({"name": "Servicios TI", "cpv": "72", "user_id": comercial.id})
        perfil._importar()

    def test_convertir_desde_el_kanban(self):
        self.start_tour(
            "/odoo/action-radar_licitaciones.radar_licitacion_action", "radar_licitaciones_convertir", login="laura"
        )

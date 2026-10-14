from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import RadarCase


@tagged("post_install", "-at_install")
class TestSeguridad(RadarCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usuarios = cls.env["res.users"].with_context(no_reset_password=True)
        cls.sin_grupo = usuarios.create(
            {"name": "Sin grupo", "login": "sin_grupo", "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])]}
        )
        cls.usuario = usuarios.create(
            {
                "name": "Usuario",
                "login": "usuario",
                "group_ids": [(6, 0, [cls.env.ref("radar_licitaciones.group_radar_usuario").id])],
            }
        )
        cls.responsable = usuarios.create(
            {
                "name": "Responsable",
                "login": "responsable",
                "group_ids": [(6, 0, [cls.env.ref("radar_licitaciones.group_radar_responsable").id])],
            }
        )

    def setUp(self):
        super().setUp()
        self.importar()
        self.soc = self.licitacion(20480431)

    def test_sin_el_grupo_no_se_ve_nada(self):
        with self.assertRaises(AccessError):
            self.env["radar.licitacion"].with_user(self.sin_grupo).search([])
        with self.assertRaises(AccessError):
            self.env["radar.perfil"].with_user(self.sin_grupo).search([])

    def test_el_usuario_trabaja_las_licitaciones_pero_no_configura_perfiles(self):
        licitacion = self.soc.with_user(self.usuario)
        licitacion.action_interesa()
        self.assertEqual(licitacion.etapa, "interesa")
        self.assertTrue(self.perfil.with_user(self.usuario).name)
        with self.assertRaises(AccessError):
            self.perfil.with_user(self.usuario).name = "Otro nombre"
        with self.assertRaises(AccessError):
            self.env["radar.perfil"].with_user(self.usuario).create({"name": "Nuevo"})
        with self.assertRaises(AccessError):
            licitacion.unlink()

    def test_el_responsable_configura_perfiles(self):
        perfil = self.env["radar.perfil"].with_user(self.responsable).create({"name": "Obras en Madrid", "cpv": "45"})
        self.assertEqual(perfil.company_id, self.env.company)

    def test_cada_compania_ve_solo_sus_licitaciones(self):
        otra = self.env["res.company"].create({"name": "Otra empresa"})
        perfil_otra = self.env["radar.perfil"].create({"name": "Perfil de la otra", "company_id": otra.id, "cpv": "72"})
        self.importar(perfil_otra)
        # La misma licitación del radar existe una vez en cada compañía.
        self.assertEqual(self.env["radar.licitacion"].search_count([("radar_id", "=", 20480431)]), 2)

        self.usuario.write({"company_ids": [(4, otra.id)]})
        en_la_mia = (
            self.env["radar.licitacion"].with_user(self.usuario).with_context(allowed_company_ids=[self.env.company.id])
        )
        self.assertEqual(en_la_mia.search_count([]), 37)
        self.assertEqual(set(en_la_mia.search([]).company_id.ids), {self.env.company.id})
        self.assertFalse(en_la_mia.env["radar.perfil"].search([("company_id", "=", otra.id)]))

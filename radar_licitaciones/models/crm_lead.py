from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    licitacion_id = fields.Many2one(
        "radar.licitacion", string="Public tender", readonly=True, copy=False, index="btree_not_null"
    )

    def action_ver_licitacion(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "radar.licitacion",
            "res_id": self.licitacion_id.id,
            "view_mode": "form",
        }

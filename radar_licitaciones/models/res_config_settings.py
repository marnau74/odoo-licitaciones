from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    radar_licitaciones_url = fields.Char(
        string="Tender radar URL",
        config_parameter="radar_licitaciones.url",
        help="Address of the tender radar, for example https://radar.example.com. Its public API is used.",
    )

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    radar_organo_id = fields.Integer(
        string="Radar contracting body",
        index="btree_not_null",
        copy=False,
        help="Identifier of the contracting body in the tender radar.",
    )

    @api.model
    def _radar_organos(self, organos):
        """Los contactos de los órganos de contratación, creando de una vez los que falten.

        :param organos: ``{id del órgano en el radar: nombre}``
        :return: ``{id del órgano: res.partner}``
        """
        if not organos:
            return {}
        existentes = self.with_context(active_test=False).search([("radar_organo_id", "in", list(organos))])
        por_id = {p.radar_organo_id: p for p in existentes}
        faltan = [i for i in organos if i not in por_id]
        nuevos = self.create([{"name": organos[i], "is_company": True, "radar_organo_id": i} for i in faltan])
        por_id.update({p.radar_organo_id: p for p in nuevos})
        return por_id

    def _radar_completar_organo(self, organo):
        """Completa el contacto con la ficha del órgano del radar, o lo cambia por el que ya tenga ese NIF.

        Si en Odoo ya existe un contacto con el mismo NIF (un cliente de siempre, creado a mano), ese es el bueno: pasa
        a ser el del órgano, se le llevan sus licitaciones y el creado al importar se archiva.
        """
        self.ensure_one()
        nif = (organo.get("nif") or "").strip().upper()
        vat = nif if not nif or nif.startswith("ES") else f"ES{nif}"
        if vat:
            otro = self.search([("vat", "in", [vat, nif]), ("id", "!=", self.id), ("is_company", "=", True)], limit=1)
            if otro:
                radar_organo_id = self.radar_organo_id
                # Las de todas las compañías: el contacto archivado no puede quedarse con ninguna.
                self.env["radar.licitacion"].sudo().search([("organo_id", "=", self.id)]).organo_id = otro
                self.write({"radar_organo_id": False, "active": False})
                otro.radar_organo_id = radar_organo_id
                return otro
        valores = {
            "vat": self.vat or vat or False,
            "city": self.city or organo.get("ciudad") or False,
            "zip": self.zip or organo.get("codigoPostal") or False,
            "website": self.website or organo.get("web") or False,
        }
        if not self.country_id:
            valores["country_id"] = self.env.ref("base.es").id
        self.write(valores)
        return self

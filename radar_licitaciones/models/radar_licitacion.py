from datetime import UTC, datetime, timedelta

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

from .provincias import xmlid_de_provincia
from .radar_cliente import RadarError

ESTADOS = [
    ("PRE", "Prior notice"),
    ("PUB", "Published"),
    ("EV", "Pending award"),
    ("ADJ", "Awarded"),
    ("RES", "Resolved"),
    ("ANUL", "Cancelled"),
]
TIPOS_DE_CONTRATO = [
    ("1", "Supplies"),
    ("2", "Services"),
    ("3", "Works"),
    ("7", "Special administrative"),
    ("8", "Private"),
    ("21", "Public service management"),
    ("22", "Services concession"),
    ("31", "Public works concession"),
    ("32", "Works concession"),
    ("40", "Public-private partnership"),
    ("50", "Property"),
]
# Lo que se compara al volver a importar una licitación: si nada ha cambiado, no se escribe.
CAMPOS_SINCRONIZADOS = ["name", "expediente", "estado", "importe", "plazo", "cpv", "nuts", "lugar", "anulada"]
# Días antes del cierre del plazo en que vence la actividad del comercial y la licitación «cierra pronto».
DIAS_DE_MARGEN = 3


class RadarLicitacion(models.Model):
    """Una licitación del radar que encaja con algún perfil de la empresa."""

    _name = "radar.licitacion"
    _description = "Public tender"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "fecha_publicacion desc, id desc"
    _check_company_auto = True

    radar_id = fields.Integer(string="Radar ID", required=True, readonly=True, index=True)
    name = fields.Char(string="Title", required=True, readonly=True)
    expediente = fields.Char(string="File number", readonly=True)
    organo_id = fields.Many2one("res.partner", string="Contracting body", readonly=True, index=True)
    company_id = fields.Many2one("res.company", required=True, readonly=True, index=True)
    perfil_id = fields.Many2one(
        "radar.perfil", string="Profile", readonly=True, index=True, ondelete="set null", check_company=True
    )
    user_id = fields.Many2one(related="perfil_id.user_id", string="Salesperson")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.ref("base.EUR"), readonly=True)
    importe = fields.Monetary(string="Budget (without VAT)", readonly=True)
    plazo = fields.Datetime(string="Bid deadline", readonly=True, help="Last moment to submit a bid.")
    fecha_publicacion = fields.Date(string="Published on", readonly=True)
    estado = fields.Selection(ESTADOS, string="Status", readonly=True, tracking=True)
    tipo_contrato = fields.Selection(TIPOS_DE_CONTRATO, string="Contract type", readonly=True)
    anulada = fields.Boolean(string="Cancelled", readonly=True)
    cpv = fields.Char(string="CPV codes", readonly=True)
    cpv_division = fields.Char(
        string="CPV division", compute="_compute_cpv_division", store=True, help="First two digits of the main CPV."
    )
    nuts = fields.Char(string="NUTS region", readonly=True)
    state_id = fields.Many2one("res.country.state", string="Province", readonly=True)
    lugar = fields.Char(string="Place", readonly=True)
    etapa = fields.Selection(
        [("nueva", "New"), ("interesa", "Interesting"), ("convertida", "Opportunity"), ("descartada", "Discarded")],
        string="Stage",
        default="nueva",
        required=True,
        tracking=True,
        group_expand="_expand_etapas",
    )
    lead_id = fields.Many2one("crm.lead", string="Opportunity", readonly=True, copy=False, check_company=True)
    url = fields.Char(string="Radar link", compute="_compute_url")
    # Sin guardar: dependen de la hora actual y guardados se quedarían viejos al día siguiente.
    dias_para_el_plazo = fields.Integer(string="Days left", compute="_compute_plazo")
    cierra_pronto = fields.Boolean(string="Closing soon", compute="_compute_plazo", search="_search_cierra_pronto")

    _radar_id_por_compania = models.Constraint(
        "UNIQUE(radar_id, company_id)", "This tender has already been imported for this company."
    )

    @api.depends("cpv")
    def _compute_cpv_division(self):
        for licitacion in self:
            licitacion.cpv_division = (licitacion.cpv or "")[:2] or False

    @api.depends("radar_id")
    def _compute_url(self):
        try:
            base = self.env["radar.cliente"]._url_base()
        except RadarError:
            base = None
        for licitacion in self:
            licitacion.url = f"{base}/licitaciones/{licitacion.radar_id}" if base else False

    @api.depends("plazo")
    def _compute_plazo(self):
        ahora = fields.Datetime.now()
        for licitacion in self:
            if not licitacion.plazo:
                licitacion.dias_para_el_plazo = 0
                licitacion.cierra_pronto = False
                continue
            restante = licitacion.plazo - ahora
            licitacion.dias_para_el_plazo = restante.days if restante.total_seconds() >= 0 else -1
            licitacion.cierra_pronto = timedelta(0) <= restante <= timedelta(days=DIAS_DE_MARGEN)

    def _search_cierra_pronto(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(self.env._("Unsupported search on “Closing soon”."))
        ahora = fields.Datetime.now()
        dominio = [("plazo", ">=", ahora), ("plazo", "<=", ahora + timedelta(days=DIAS_DE_MARGEN))]
        return dominio if (operator == "=") == value else ["!", "&", *dominio]

    @api.model
    def _expand_etapas(self, etapas, domain):
        return [clave for clave, _etiqueta in self._fields["etapa"].selection]

    # Importación

    @api.model
    def _valores_del_radar(self, elemento):
        """Los campos de una licitación a partir de un elemento de la búsqueda del radar."""
        plazo = elemento.get("plazoPresentacion")
        xmlid = xmlid_de_provincia(elemento.get("nuts"))
        cpv = elemento.get("cpv") or []
        tipo = elemento.get("tipoContrato")
        return {
            "name": (elemento.get("titulo") or "").strip() or self.env._("(untitled)"),
            "expediente": elemento.get("expediente") or False,
            "estado": elemento.get("estado") if elemento.get("estado") in dict(ESTADOS) else False,
            "tipo_contrato": tipo if tipo in dict(TIPOS_DE_CONTRATO) else False,
            "importe": elemento.get("importeSinIva") or 0.0,
            "plazo": _a_utc(plazo) if plazo else False,
            "fecha_publicacion": elemento.get("fechaPublicacion") or False,
            "cpv": ", ".join(cpv) or False,
            "nuts": elemento.get("nuts") or False,
            "state_id": self.env.ref(xmlid).id if xmlid else False,
            "lugar": elemento.get("lugar") or False,
            "anulada": bool(elemento.get("anulada")),
        }

    @api.model
    def _sincronizar(self, elementos, perfil):
        """Crea las licitaciones nuevas y actualiza las que han cambiado, de una vez y sin duplicar.

        :return: ``(nuevas, actualizadas)`` como conjuntos de registros
        """
        compania = perfil.company_id
        por_radar_id = {e["id"]: e for e in elementos}  # una licitación puede venir dos veces si cambia de página
        existentes = self.search([("radar_id", "in", list(por_radar_id)), ("company_id", "=", compania.id)])
        ya_estan = {licitacion.radar_id: licitacion for licitacion in existentes}
        organos = self.env["res.partner"]._radar_organos(
            {
                e["organoId"]: e.get("organo") or self.env._("Contracting body %s", e["organoId"])
                for e in elementos
                if e.get("organoId")
            }
        )

        actualizadas = self.browse()
        nuevas_valores = []
        for radar_id, elemento in por_radar_id.items():
            valores = self._valores_del_radar(elemento)
            licitacion = ya_estan.get(radar_id)
            if licitacion:
                cambios = {
                    c: valores[c] for c in CAMPOS_SINCRONIZADOS if licitacion._valor_para_comparar(c) != valores[c]
                }
                if cambios:
                    licitacion.write(cambios)
                    actualizadas |= licitacion
            else:
                organo = organos.get(elemento.get("organoId"))
                nuevas_valores.append(
                    dict(
                        valores,
                        radar_id=radar_id,
                        company_id=compania.id,
                        perfil_id=perfil.id,
                        organo_id=organo.id if organo else False,
                    )
                )
        nuevas = self.create(nuevas_valores)
        return nuevas, actualizadas

    def _valor_para_comparar(self, campo):
        valor = self[campo]
        if self._fields[campo].type == "date":
            return fields.Date.to_string(valor) if valor else False
        return valor if valor or valor == 0 else False

    # Acciones

    def action_interesa(self):
        self.filtered(lambda licitacion: licitacion.etapa in ("nueva", "descartada")).etapa = "interesa"

    def action_descartar(self):
        self.filtered(lambda licitacion: licitacion.etapa != "convertida").etapa = "descartada"

    def action_abrir_en_radar(self):
        self.ensure_one()
        if not self.url:
            raise UserError(self.env._("The tender radar URL is not configured (Settings → Tender radar)."))
        return {"type": "ir.actions.act_url", "url": self.url, "target": "new"}

    def action_ver_oportunidad(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "res_id": self.lead_id.id,
            "view_mode": "form",
        }

    def action_convertir(self):
        """Convierte cada licitación en una oportunidad del CRM, con el órgano como cliente.

        Antes se pide al radar la ficha completa del órgano (NIF, ciudad, web) para no duplicar clientes: si ya hay un
        contacto con ese NIF, la oportunidad es suya.
        """
        if any(licitacion.lead_id for licitacion in self):
            raise UserError(self.env._("Some of these tenders are already opportunities."))
        cliente = self.env["radar.cliente"]
        oportunidades = self.env["crm.lead"]
        for licitacion in self:
            try:
                ficha = cliente.detalle(licitacion.radar_id)
            except RadarError as error:
                raise UserError(str(error)) from error
            organo = licitacion.organo_id
            if organo and ficha.get("organo"):
                organo = organo._radar_completar_organo(ficha["organo"])
            oportunidad = self.env["crm.lead"].create(licitacion._valores_de_oportunidad(organo))
            licitacion.write({"lead_id": oportunidad.id, "etapa": "convertida", "organo_id": organo.id or False})
            licitacion._programar_actividad(oportunidad)
            licitacion.message_post(
                body=Markup(self.env._("Converted into the opportunity %s.")) % oportunidad._get_html_link()
            )
            oportunidades |= oportunidad
        if len(oportunidades) == 1:
            return self.action_ver_oportunidad()
        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "domain": [("id", "in", oportunidades.ids)],
            "view_mode": "list,form",
            "name": self.env._("Opportunities"),
        }

    def _valores_de_oportunidad(self, organo):
        self.ensure_one()
        lineas = [
            self.env._("File number: %s", self.expediente or "—"),
            self.env._("CPV: %s", self.cpv or "—"),
            self.env._("Place: %s", self.lugar or "—"),
        ]
        descripcion = Markup("<p>%s</p>") % Markup("<br/>").join(lineas)
        if self.url:
            descripcion += Markup('<p><a href="%s" target="_blank">%s</a></p>') % (
                self.url,
                self.env._("See it in the radar"),
            )
        return {
            "name": self.name,
            "type": "opportunity",
            "partner_id": organo.id or False,
            "expected_revenue": self.importe,
            "date_deadline": self._dia_local(self.plazo) if self.plazo else False,
            "user_id": self.user_id.id or self.env.user.id,
            "company_id": self.company_id.id,
            "description": descripcion,
            "licitacion_id": self.id,
        }

    def _programar_actividad(self, oportunidad):
        """Una tarea para el comercial unos días antes de que cierre el plazo (o hoy, si ya queda menos)."""
        self.ensure_one()
        hoy = fields.Date.context_today(self)
        vence = hoy
        if self.plazo:
            vence = max(hoy, self._dia_local(self.plazo) - timedelta(days=DIAS_DE_MARGEN))
        oportunidad.activity_schedule(
            "mail.mail_activity_data_todo",
            date_deadline=vence,
            summary=self.env._("Prepare the bid"),
            note=self.env._(
                "The deadline to submit the bid is %s.",
                format_date(self.env, self._dia_local(self.plazo)) if self.plazo else "—",
            ),
            user_id=oportunidad.user_id.id or self.env.user.id,
        )

    def _dia_local(self, momento):
        """El día de un momento en UTC según la zona horaria del usuario: un plazo a las 00:30 del 21 en Madrid se
        guarda como el 20 a las 22:30 (UTC), y el día que cuenta para el usuario es el 21."""
        return fields.Datetime.context_timestamp(
            self.with_context(tz=self.env.user.tz or "Europe/Madrid"), momento
        ).date()


def _a_utc(texto):
    """``2026-10-15T21:59:00Z`` (o con desfase) → datetime sin zona en UTC, que es como lo guarda Odoo."""
    momento = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    if momento.tzinfo is None:
        return momento
    return momento.astimezone(UTC).replace(tzinfo=None)

import logging
import re
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .provincias import nuts_de_provincia
from .radar_cliente import RadarError

_logger = logging.getLogger(__name__)

CPV = re.compile(r"^\d{2,8}$")
# 100 por página (el máximo de la API) y 20 páginas: 2.000 licitaciones por perfil y día sobran; si hay más, el perfil
# es demasiado amplio y se avisa.
TAMANO_DE_PAGINA = 100
MAXIMO_DE_PAGINAS = 20


class RadarPerfil(models.Model):
    """Lo que busca la empresa en el radar: qué CPV, dónde, entre qué importes y con qué palabras."""

    _name = "radar.perfil"
    _description = "Tender search profile"
    _inherit = ["mail.thread"]
    _order = "name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        default=lambda self: self.env.user,
        domain=[("share", "=", False)],
        tracking=True,
        check_company=True,
        help="Gets the opportunities and activities of the tenders found by this profile.",
    )
    cpv = fields.Char(
        string="CPV codes",
        help="Comma-separated CPV codes or prefixes (2 to 8 digits). 72 covers all IT services.",
        tracking=True,
    )
    state_ids = fields.Many2many(
        "res.country.state",
        string="Provinces",
        domain="[('country_id.code', '=', 'ES')]",
        help="Where the contract is carried out. Empty: all of Spain.",
    )
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.ref("base.EUR"), readonly=True)
    importe_minimo = fields.Monetary(string="Minimum amount", help="Budget without VAT.")
    importe_maximo = fields.Monetary(string="Maximum amount", help="Budget without VAT. Zero: no limit.")
    palabras = fields.Char(
        string="Keywords", help='Words to look for in the title. Accepts "exact phrases" and -exclusions.'
    )
    solo_abiertas = fields.Boolean(string="Only open for bids", default=True)
    dias_primera_importacion = fields.Integer(
        string="Days back on the first import", default=30, help="How far back the first import looks."
    )
    ultima_importacion = fields.Datetime(string="Last import", readonly=True, copy=False)
    ultimo_error = fields.Text(string="Last error", readonly=True, copy=False)
    licitacion_ids = fields.One2many("radar.licitacion", "perfil_id", string="Tenders")
    licitacion_count = fields.Integer(compute="_compute_licitacion_count", string="Tender count")

    _importes_positivos = models.Constraint(
        "CHECK(importe_minimo >= 0 AND importe_maximo >= 0)", "Amounts cannot be negative."
    )

    @api.depends("licitacion_ids")
    def _compute_licitacion_count(self):
        datos = self.env["radar.licitacion"]._read_group([("perfil_id", "in", self.ids)], ["perfil_id"], ["__count"])
        cuentas = {perfil.id: n for perfil, n in datos}
        for perfil in self:
            perfil.licitacion_count = cuentas.get(perfil.id, 0)

    @api.constrains("cpv")
    def _check_cpv(self):
        for perfil in self:
            malos = [c for c in perfil._lista_de_cpv() if not CPV.match(c)]
            if malos:
                raise ValidationError(
                    self.env._("CPV codes must have between 2 and 8 digits: %(codes)s", codes=", ".join(malos))
                )

    @api.constrains("importe_minimo", "importe_maximo")
    def _check_importes(self):
        for perfil in self:
            if perfil.importe_maximo and perfil.importe_minimo > perfil.importe_maximo:
                raise ValidationError(self.env._("The minimum amount cannot be greater than the maximum amount."))

    def _lista_de_cpv(self):
        self.ensure_one()
        return [c.strip() for c in (self.cpv or "").split(",") if c.strip()]

    def _parametros_de_busqueda(self, desde):
        """Los parámetros de la API del radar para este perfil, con las publicadas desde ``desde``."""
        self.ensure_one()
        nuts = []
        for xmlid in self.state_ids.get_external_id().values():
            nuts += nuts_de_provincia(xmlid)
        parametros = {
            "cpv": self._lista_de_cpv(),
            "nuts": nuts,
            "q": self.palabras or None,
            "importeMin": self.importe_minimo or None,
            "importeMax": self.importe_maximo or None,
            "abiertas": "true" if self.solo_abiertas else None,
            "publicadaDesde": desde.isoformat(),
            "orden": "publicacion",
            "tamano": TAMANO_DE_PAGINA,
        }
        return {clave: valor for clave, valor in parametros.items() if valor not in (None, [])}

    def _desde(self):
        """Desde qué día se piden las publicadas: el día antes de la última importación (por si el radar cargó tarde
        las de ese día) o, la primera vez, los días que diga el perfil."""
        self.ensure_one()
        if self.ultima_importacion:
            return (self.ultima_importacion - timedelta(days=1)).date()
        return fields.Date.context_today(self) - timedelta(days=self.dias_primera_importacion or 30)

    def _importar(self):
        """Trae del radar las licitaciones del perfil y las guarda. Devuelve ``(nuevas, actualizadas)``.

        Lanza ``RadarError`` si el radar falla: la transacción se deshace y no queda media importación.
        """
        self.ensure_one()
        cliente = self.env["radar.cliente"]
        parametros = self._parametros_de_busqueda(self._desde())
        elementos = []
        for pagina in range(1, MAXIMO_DE_PAGINAS + 1):
            respuesta = cliente.buscar(dict(parametros, pagina=pagina))
            elementos += respuesta.get("elementos", [])
            if pagina >= respuesta.get("paginas", 0):
                break
        else:
            _logger.warning(
                "Radar: el perfil %s pasa de %s licitaciones; se han traído las primeras.", self.name, len(elementos)
            )
        nuevas, actualizadas = self.env["radar.licitacion"]._sincronizar(elementos, self)
        self.write({"ultima_importacion": fields.Datetime.now(), "ultimo_error": False})
        if nuevas:
            self.message_post(body=self.env._("%(count)s new tenders imported from the radar.", count=len(nuevas)))
        return nuevas, actualizadas

    def action_importar(self):
        """Botón «Importar ahora»: los errores se enseñan al usuario."""
        nuevas = actualizadas = self.env["radar.licitacion"]
        for perfil in self:
            try:
                n, a = perfil._importar()
            except RadarError as error:
                raise UserError(str(error)) from error
            nuevas |= n
            actualizadas |= a
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": self.env._(
                    "%(new)s new and %(updated)s updated tenders.", new=len(nuevas), updated=len(actualizadas)
                ),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    @api.model
    def _cron_importar(self):
        """Acción programada diaria. Un perfil que falla no para a los demás ni hace fallar la acción: el error se
        registra y se guarda en el perfil para enseñarlo en su ficha."""
        for perfil in self.search([]):
            try:
                with self.env.cr.savepoint():
                    perfil._importar()
            except RadarError as error:
                _logger.warning("Radar: no se ha podido importar el perfil %s: %s", perfil.name, error)
                perfil.ultimo_error = str(error)

    def action_ver_licitaciones(self):
        self.ensure_one()
        accion = self.env["ir.actions.act_window"]._for_xml_id("radar_licitaciones.radar_licitacion_action")
        accion["domain"] = [("perfil_id", "=", self.id)]
        accion["context"] = {"default_perfil_id": self.id}
        return accion

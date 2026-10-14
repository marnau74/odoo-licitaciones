"""Base de demostración: dos perfiles de búsqueda y la importación desde el radar.

    docker compose run --rm odoo odoo shell -d demo --no-http < scripts/demo.py

Necesita el radar en marcha (por defecto en http://host.docker.internal:8088, el puerto del compose del radar).
Las licitaciones son las reales del radar; las etapas y la oportunidad convertida son de ejemplo.
"""

# pylint: disable=print-used
import os

from odoo import fields

url = os.environ.get("RADAR_URL", "http://host.docker.internal:8088")
env["ir.config_parameter"].set_param("radar_licitaciones.url", url)  # noqa: F821

admin = env.ref("base.user_admin")  # noqa: F821
admin.write({"lang": "es_ES", "tz": "Europe/Madrid"})
euro = env.ref("base.EUR")  # noqa: F821
euro.active = True
env.company.write({"name": "Empresa de demostración", "country_id": env.ref("base.es").id, "currency_id": euro.id})  # noqa: F821

Perfil = env["radar.perfil"].with_user(admin)  # noqa: F821
perfiles = Perfil.search([])
if not perfiles:
    provincia = lambda codigo: env.ref(f"base.state_es_{codigo}")  # noqa: E731, F821
    perfiles = Perfil.create(
        [
            {
                "name": "Servicios informáticos en Murcia, Alicante y Valencia",
                "cpv": "72, 48",
                "state_ids": [(6, 0, (provincia("mu") | provincia("a") | provincia("v")).ids)],
                "importe_minimo": 15000,
                "dias_primera_importacion": 60,
            },
            {
                "name": "Obras en la Región de Murcia",
                "cpv": "45",
                "state_ids": [(6, 0, provincia("mu").ids)],
                "importe_minimo": 50000,
                "dias_primera_importacion": 60,
            },
        ]
    )
for perfil in perfiles:
    nuevas, actualizadas = perfil._importar()
    print(f"{perfil.name}: {len(nuevas)} nuevas, {len(actualizadas)} actualizadas")

Licitacion = env["radar.licitacion"].with_user(admin)  # noqa: F821
if not Licitacion.search_count([("lead_id", "!=", False)]):
    abiertas = Licitacion.search([("estado", "=", "PUB"), ("plazo", ">", fields.Datetime.now())], order="importe desc")
    if abiertas:
        abiertas[0].action_convertir()
        abiertas[1:4].action_interesa()
        abiertas[-2:].action_descartar()
env.cr.commit()  # noqa: F821

"""Correspondencia entre las regiones NUTS 3 (2021) que usa el radar y las provincias de Odoo.

El radar guarda el lugar de ejecución como código NUTS: ES620 es la Región de Murcia, ES523 Valencia. Odoo tiene las
provincias españolas como ``res.country.state`` (``base.state_es_mu``, ``base.state_es_v``). Baleares y Canarias se
dividen en islas en NUTS 3: varias islas van a la misma provincia.
"""

NUTS_A_PROVINCIA = {
    "ES111": "c",
    "ES112": "lu",
    "ES113": "or",
    "ES114": "po",
    "ES120": "o",
    "ES130": "s",
    "ES211": "vi",
    "ES212": "ss",
    "ES213": "bi",
    "ES220": "na",
    "ES230": "lo",
    "ES241": "hu",
    "ES242": "te",
    "ES243": "z",
    "ES300": "m",
    "ES411": "av",
    "ES412": "bu",
    "ES413": "le",
    "ES414": "p",
    "ES415": "sa",
    "ES416": "sg",
    "ES417": "so",
    "ES418": "va",
    "ES419": "za",
    "ES421": "ab",
    "ES422": "cr",
    "ES423": "cu",
    "ES424": "gu",
    "ES425": "to",
    "ES431": "ba",
    "ES432": "cc",
    "ES511": "b",
    "ES512": "gi",
    "ES513": "l",
    "ES514": "t",
    "ES521": "a",
    "ES522": "cs",
    "ES523": "v",
    "ES531": "pm",  # Eivissa y Formentera
    "ES532": "pm",  # Mallorca
    "ES533": "pm",  # Menorca
    "ES611": "al",
    "ES612": "ca",
    "ES613": "co",
    "ES614": "gr",
    "ES615": "h",
    "ES616": "j",
    "ES617": "ma",
    "ES618": "se",
    "ES620": "mu",
    "ES630": "ce",
    "ES640": "ml",
    "ES703": "tf",  # El Hierro
    "ES704": "gc",  # Fuerteventura
    "ES705": "gc",  # Gran Canaria
    "ES706": "tf",  # La Gomera
    "ES707": "tf",  # La Palma
    "ES708": "gc",  # Lanzarote
    "ES709": "tf",  # Tenerife
}


def xmlid_de_provincia(nuts):
    """El identificador XML de la provincia de Odoo para un código NUTS 3, o ``None`` si no es una provincia."""
    sufijo = NUTS_A_PROVINCIA.get((nuts or "").upper())
    return f"base.state_es_{sufijo}" if sufijo else None


def nuts_de_provincia(xmlid):
    """Los códigos NUTS 3 que forman una provincia de Odoo (``base.state_es_pm`` → las tres zonas de Baleares)."""
    sufijo = xmlid.removeprefix("base.state_es_")
    return sorted(nuts for nuts, provincia in NUTS_A_PROVINCIA.items() if provincia == sufijo)

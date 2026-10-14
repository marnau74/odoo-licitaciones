# 1. Las licitaciones, un modelo propio y no oportunidades directamente

## Contexto

Lo más corto sería crear una oportunidad del CRM por cada licitación importada. Pero un perfil de búsqueda razonable
trae decenas de licitaciones a la semana y la mayoría no interesan: el CRM se llenaría de oportunidades que nadie va
a trabajar, y las estadísticas de ventas (tasa de éxito, previsión) dejarían de valer.

## Decisión

- Las licitaciones importadas son registros de `radar.licitacion`, con su propio kanban por etapa (*Nueva*,
  *Interesa*, *Oportunidad*, *Descartada*). Solo las que alguien decide convertir pasan al CRM.
- La oportunidad queda enlazada a su licitación (`crm.lead.licitacion_id`) y la licitación a su oportunidad
  (`lead_id`): desde cualquiera de las dos se llega a la otra.
- La etapa es de la empresa; el estado (*Publicada*, *Adjudicada*...) es del radar y se actualiza en cada
  importación. Son campos distintos para que una actualización del radar no deshaga el trabajo del comercial.
- Una licitación se importa una vez por compañía (restricción única `radar_id` + `company_id`): dos empresas del
  mismo Odoo pueden trabajar la misma licitación por separado.

## Alternativas descartadas

- **Oportunidades directamente**, con una etiqueta: llena el CRM de ruido y mezcla dos embudos distintos.
- **Leads (pistas) del CRM**: existen para esto en teoría, pero obligan a activar las pistas en toda la empresa y no
  tienen sitio para el expediente, el CPV o el plazo sin añadir campos al modelo de otro.

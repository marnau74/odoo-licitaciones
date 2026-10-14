======================
Radar de licitaciones
======================

.. |badge1| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1|

Importa en Odoo las licitaciones públicas del `radar de licitaciones
<https://github.com/marnau74/radar-licitaciones>`_ que encajan con lo que busca la empresa y las convierte, con un
botón, en oportunidades del CRM.

**Índice**

.. contents::
   :local:

Uso
===

#. En *Licitaciones → Configuración → Ajustes*, escribe la dirección del radar.
#. En *Licitaciones → Configuración → Perfiles de búsqueda*, crea un perfil: códigos CPV (o prefijos, como 72 para
   los servicios informáticos), provincias, importes y palabras. El comercial del perfil recibe las oportunidades.
#. Cada día, la acción programada *Radar de licitaciones: importar licitaciones* trae las publicadas desde la última
   importación. También se puede importar a mano desde el perfil.
#. En *Licitaciones*, el kanban reparte las licitaciones por etapa (*Nueva*, *Interesa*, *Oportunidad*,
   *Descartada*). *Convertir en oportunidad* crea la oportunidad con el presupuesto como ingreso previsto, el fin del
   plazo como cierre previsto y el órgano de contratación como cliente (con su NIF, sin duplicarlo si ya existía), y
   programa una tarea para el comercial tres días antes de que cierre el plazo.

Configuración
=============

* Grupos: *Licitaciones / Usuario* ve las licitaciones, las clasifica y las convierte; *Licitaciones / Responsable*
  además configura los perfiles e importa.
* Multiempresa: cada perfil y cada licitación pertenecen a una compañía. La misma licitación del radar puede estar
  una vez en cada compañía.

Problemas conocidos
===================

* El radar solo tiene las licitaciones de la Plataforma de Contratación del Sector Público y de lo que agrega; las
  de las plataformas autonómicas que no publican allí no aparecen.
* Una licitación cuyo lugar de ejecución es una comunidad entera (NUTS 2) no tiene provincia.

Créditos
========

Autores
-------

* Mario Arnau

Datos
-----

* Plataforma de Contratación del Sector Público, a través del radar de licitaciones.

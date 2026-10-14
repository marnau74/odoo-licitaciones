import { registry } from "@web/core/registry";

// Del kanban de licitaciones a la oportunidad del CRM y vuelta.
registry.category("web_tour.tours").add("radar_licitaciones_convertir", {
    url: "/odoo/action-radar_licitaciones.radar_licitacion_action",
    steps: () => [
        {
            content: "Las licitaciones salen en el kanban por etapas",
            trigger: ".o_kanban_group:has(.o_column_title:contains('New')) .o_kanban_record:contains('Servicio de SOC/MDR')",
            run: "click",
        },
        {
            content: "Convertir en oportunidad",
            trigger: ".o_form_view button[name='action_convertir']",
            run: "click",
        },
        {
            content: "Se abre la oportunidad con el presupuesto como ingreso previsto",
            trigger: ".o_form_view .o_field_widget[name='expected_revenue']:contains('585,000')",
        },
        {
            content: "Y el cliente es el órgano de contratación",
            trigger: ".o_form_view .o_field_widget[name='partner_id'] input:value('Junta de Gobierno Local del Ayuntamiento de Cartagena')",
        },
        {
            content: "Desde la oportunidad se vuelve a la licitación",
            trigger: ".o_form_view button[name='action_ver_licitacion']",
            run: "click",
        },
        {
            content: "Que ya está en la etapa de oportunidad",
            trigger: ".o_form_view .o_statusbar_status button.o_arrow_button_current:contains('Opportunity')",
        },
    ],
});

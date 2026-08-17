"""Semeia os planos de manutenção padrão no catálogo."""

from django.db import migrations

DEFAULT_PLANS = [
    {
        "plan_type": "mensal",
        "name": "Manutenção mensal",
        "value": "79.90",
        "description": "Uma visita por mês, com acompanhamento contínuo.",
        "ordering": 1,
    },
    {
        "plan_type": "trimestral",
        "name": "Manutenção trimestral",
        "value": "219.90",
        "description": "Uma visita a cada 3 meses. Melhor custo-benefício.",
        "ordering": 2,
    },
    {
        "plan_type": "anual",
        "name": "Manutenção anual",
        "value": "799.90",
        "description": "Visitas para o ano inteiro, com desconto no ciclo.",
        "ordering": 3,
    },
]


def seed_plans(apps, schema_editor):
    MaintenancePlanTemplate = apps.get_model("services", "MaintenancePlanTemplate")
    for plan in DEFAULT_PLANS:
        MaintenancePlanTemplate.objects.get_or_create(
            plan_type=plan["plan_type"],
            defaults={
                "name": plan["name"],
                "value": plan["value"],
                "description": plan["description"],
                "ordering": plan["ordering"],
            },
        )


def remove_plans(apps, schema_editor):
    MaintenancePlanTemplate = apps.get_model("services", "MaintenancePlanTemplate")
    MaintenancePlanTemplate.objects.filter(
        plan_type__in=[plan["plan_type"] for plan in DEFAULT_PLANS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("services", "0008_maintenanceplantemplate"),
    ]

    operations = [
        migrations.RunPython(seed_plans, remove_plans),
    ]

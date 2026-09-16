"""Remove resquícios da loja em bancos já migrados.

Histórico: o antigo `checkout.0001_initial` criava FKs em `OrderItem` para
`shop.Product`/`shop.ProductVariant` e o app `shop` tinha migrations próprias.
Em bancos novos o 0001 reescrito já não cria essas colunas; aqui apagamos as
colunas/tabelas restantes em bancos existentes (produção) e limpamos o registro
de migrations do app `shop`. O RunPython é idempotente (no-op em bancos novos).
"""

from django.db import migrations, models


def drop_shop_legacy(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        if "checkout_orderitem" in tables:
            columns = {
                col.name
                for col in connection.introspection.get_table_description(
                    cursor, "checkout_orderitem"
                )
            }
            to_drop = [col for col in ("product_id", "variant_id") if col in columns]
            if to_drop and connection.vendor == "sqlite":
                # SQLite não remove índices dependentes no DROP COLUMN
                # (Postgres remove automaticamente). Dropa-os antes.
                constraints = connection.introspection.get_constraints(
                    cursor, "checkout_orderitem"
                )
                for name, info in constraints.items():
                    if info.get("index") and set(info.get("columns") or []) & set(to_drop):
                        cursor.execute(f'DROP INDEX IF EXISTS "{name}"')
            for column in to_drop:
                cursor.execute(
                    f'ALTER TABLE "checkout_orderitem" DROP COLUMN "{column}"'
                )
        for table in ("shop_productimage", "shop_productvariant", "shop_product", "shop_category"):
            if table in tables:
                cursor.execute(f'DROP TABLE "{table}"')
        cursor.execute("DELETE FROM django_migrations WHERE app = 'shop'")


class Migration(migrations.Migration):

    dependencies = [
        ("checkout", "0003_alter_order_kind"),
    ]

    operations = [
        migrations.RunPython(drop_shop_legacy, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="kind",
            field=models.CharField(
                choices=[("service", "Serviço"), ("subscription", "Assinatura")],
                default="service",
                max_length=20,
            ),
        ),
    ]
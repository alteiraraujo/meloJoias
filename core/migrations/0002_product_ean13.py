from django.db import migrations, models
import core.labels


def populate_ean(apps, schema_editor):
    Product = apps.get_model('core', 'Product')
    alias = schema_editor.connection.alias
    products = Product.objects.using(alias)
    # Keep leading zeroes, avoid existing SKUs, and generate unique internal codes.
    used = set(products.values_list('sku', flat=True))
    sequence = 1
    for product in products.order_by('pk').iterator():
        while True:
            base = f'20{sequence:010d}'
            sequence += 1
            check = (-sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base))) % 10
            code = base + str(check)
            if code not in used:
                break
        used.add(code)
        products.filter(pk=product.pk).update(ean13=code)


class Migration(migrations.Migration):
    dependencies = [('core', '0001_initial')]
    operations = [
        migrations.AddField(model_name='product', name='ean13', field=models.CharField(
            max_length=13, null=True, editable=False, verbose_name='EAN-13 interno')),
        migrations.RunPython(populate_ean, migrations.RunPython.noop),
        migrations.AlterField(model_name='product', name='ean13', field=models.CharField(
            max_length=13, unique=True, editable=False, verbose_name='EAN-13 interno',
            validators=[core.labels.validate_ean13])),
    ]

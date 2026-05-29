from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_product_images'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_offer',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='product',
            name='offer_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]

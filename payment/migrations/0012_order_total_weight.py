# Generated by Django 5.0.4 on 2024-10-31 10:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0011_courierguy'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='total_weight',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=7),
        ),
    ]
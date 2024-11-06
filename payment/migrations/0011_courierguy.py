# Generated by Django 5.0.4 on 2024-10-31 08:41

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0010_alter_payfastpayment_phone'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourierGuy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tracking_number', models.CharField(blank=True, max_length=100, null=True)),
                ('courier_service', models.CharField(default='Courier Guy', max_length=100)),
                ('shipping_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('estimated_delivery', models.DateField(blank=True, null=True)),
                ('status', models.CharField(default='Pending', max_length=50)),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='payment.order')),
            ],
        ),
    ]
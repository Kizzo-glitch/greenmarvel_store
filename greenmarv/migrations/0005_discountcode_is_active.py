# Generated by Django 5.0.4 on 2024-09-22 11:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('greenmarv', '0004_remove_influencer_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='discountcode',
            name='is_active',
            field=models.BooleanField(default=False),
        ),
    ]
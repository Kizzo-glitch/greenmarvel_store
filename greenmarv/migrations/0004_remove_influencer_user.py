# Generated by Django 5.0.4 on 2024-09-19 14:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('greenmarv', '0003_influencer_discountcode'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='influencer',
            name='user',
        ),
    ]

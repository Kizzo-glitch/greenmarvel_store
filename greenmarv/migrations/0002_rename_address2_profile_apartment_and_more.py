# Generated by Django 5.0.4 on 2024-05-22 07:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('greenmarv', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='profile',
            old_name='address2',
            new_name='apartment',
        ),
        migrations.RenameField(
            model_name='profile',
            old_name='state',
            new_name='province',
        ),
    ]

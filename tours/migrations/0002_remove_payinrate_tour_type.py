# Generated by Django 4.1 on 2025-03-06 20:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tours', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='payinrate',
            name='tour_type',
        ),
    ]

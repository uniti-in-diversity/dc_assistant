# Generated by Django 3.0.3 on 2020-08-06 20:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organisation', '0005_remove_platform_version'),
    ]

    operations = [
        migrations.RenameField(
            model_name='device',
            old_name='device_type',
            new_name='device_model',
        ),
        migrations.AlterField(
            model_name='device',
            name='face_position',
            field=models.PositiveSmallIntegerField(blank=True, choices=[(1, 'Размещено на лицевой стороне стойки'), (0, 'Размещено на обратной стороне стойки')], default=1, null=True),
        ),
    ]
# Generated by Django 3.0.3 on 2020-09-16 19:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organisation', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rack',
            name='desc_units',
            field=models.BooleanField(choices=[(0, 'Top to buttom'), (1, 'Buttom to top')], default=1, help_text='Default buttom to top', verbose_name='Orientation'),
        ),
        migrations.AlterField(
            model_name='rack',
            name='racktype',
            field=models.CharField(choices=[('1-frame', 'One Frame rack'), ('2-frame', 'Two Frame rack'), ('wall-cabinet', 'Wall-mounted cabinet'), ('floor-cabinet', 'Floor-mounted cabinet')], default='floor-cabinet', max_length=50),
        ),
    ]

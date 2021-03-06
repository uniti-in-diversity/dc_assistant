# Generated by Django 3.0.3 on 2020-09-14 18:07

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import taggit.managers


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('extend', '0001_initial'),
        ('auth', '0011_update_proxy_permissions'),
        ('organisation', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserKey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateField(auto_now_add=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('public_key', models.TextField(verbose_name='RSA public key')),
                ('master_key_cipher', models.BinaryField(blank=True, max_length=512, null=True)),
                ('user', models.OneToOneField(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='user_key', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['user__username'],
            },
        ),
        migrations.CreateModel(
            name='SessionKey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cipher', models.BinaryField(max_length=512)),
                ('hash', models.CharField(editable=False, max_length=128)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('userkey', models.OneToOneField(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='session_key', to='secret.UserKey')),
            ],
            options={
                'ordering': ['userkey__user__username'],
            },
        ),
        migrations.CreateModel(
            name='SecretRole',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('name', models.CharField(max_length=50, unique=True)),
                ('slug', models.SlugField(unique=True)),
                ('description', models.CharField(blank=True, max_length=100)),
                ('groups', models.ManyToManyField(blank=True, related_name='secretroles', to='auth.Group')),
                ('users', models.ManyToManyField(blank=True, related_name='secretroles', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Secret',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('name', models.CharField(blank=True, max_length=100)),
                ('ciphertext', models.BinaryField(max_length=65568)),
                ('hash', models.CharField(editable=False, max_length=128)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='secrets', to='organisation.Device')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='secrets', to='secret.SecretRole')),
                ('tag', taggit.managers.TaggableManager(help_text='A comma-separated list of tags.', through='extend.TaggedItem', to='extend.Tag', verbose_name='Tags')),
            ],
            options={
                'ordering': ['device', 'role', 'name'],
                'unique_together': {('device', 'role', 'name')},
            },
        ),
    ]

# Generated by Django 4.1.1 on 2022-09-28 16:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('file_mgr', '0006_alter_item_path'),
    ]

    operations = [
        migrations.AlterField(
            model_name='item',
            name='type',
            field=models.CharField(choices=[('dir', 'Dir'), ('file', 'File')], default='dir', max_length=4),
        ),
    ]
# Generated by Django 4.1.1 on 2022-09-28 19:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('file_mgr', '0008_alter_item_path'),
    ]

    operations = [
        migrations.AlterField(
            model_name='item',
            name='path',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
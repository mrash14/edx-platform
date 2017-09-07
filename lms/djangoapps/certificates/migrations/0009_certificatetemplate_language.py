# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0008_schema__remove_badges'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificatetemplate',
            name='language',
            field=models.CharField(blank=True, max_length=2, null=True, help_text='Optional. Only certificates for courses in the selected language will be rendered using this template.<br />Add more language options in certificates/settings.py <br />*Note* Course languages are determined by the first two letters of the language code.', choices=[(b'en', 'English'), (b'es', 'Espa\xf1ol')]),
        ),
    ]

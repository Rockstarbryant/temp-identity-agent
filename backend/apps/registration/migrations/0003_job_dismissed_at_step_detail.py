from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrationjob',
            name='dismissed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='registrationstep',
            name='detail',
            field=models.CharField(blank=True, max_length=300),
        ),
    ]

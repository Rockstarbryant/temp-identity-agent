from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("profiles", "0002_connectedaccount")]

    operations = [
        migrations.AddField(
            model_name="emailconnection",
            name="muted",
            field=models.BooleanField(default=False),
        ),
    ]

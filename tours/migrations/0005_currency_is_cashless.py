from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tours', '0004_food_tour_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='currency',
            name='is_cashless',
            field=models.BooleanField(
                default=False,
                help_text='Cashless/card payments (e.g. SUM). These go to the account, not the cash box.',
            ),
        ),
        migrations.AlterField(
            model_name='currency',
            name='code',
            field=models.CharField(max_length=10, unique=True),
        ),
    ]

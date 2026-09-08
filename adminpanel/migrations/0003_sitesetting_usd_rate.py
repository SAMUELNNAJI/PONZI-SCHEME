from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0002_sitesetting_usdt_bep20_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesetting',
            name='usd_rate',
            field=models.DecimalField(
                decimal_places=2,
                default=1600,
                help_text='NGN per 1 USD. Used to convert displayed balances for users who choose USD currency.',
                max_digits=12,
            ),
        ),
    ]

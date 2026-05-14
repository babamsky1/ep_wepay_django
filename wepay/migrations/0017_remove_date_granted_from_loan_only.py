from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wepay', '0016_remove_blocking_trigger'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='loandetail',
            name='date_granted',
        ),
    ]

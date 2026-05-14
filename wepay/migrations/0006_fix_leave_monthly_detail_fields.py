# Generated migration to fix LeaveMonthlyDetail field issues

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('wepay', '0005_lastpayrecord_emp_type_overtimedetail_ot_type_and_more'),
    ]

    operations = [
        # Drop the old cut_off_date field if it exists
        migrations.RemoveField(
            model_name='leavemonthlydetail',
            name='cut_off_date',
        ),
        # Add the new start_cut_off_date field
        migrations.AddField(
            model_name='leavemonthlydetail',
            name='start_cut_off_date',
            field=models.DateTimeField(default='2026-01-01T00:00:00Z'),
        ),
        # Add the new end_cut_off_date field
        migrations.AddField(
            model_name='leavemonthlydetail',
            name='end_cut_off_date',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]

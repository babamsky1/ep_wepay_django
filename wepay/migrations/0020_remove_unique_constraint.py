# Generated to remove the unique constraint that's causing duplicate entry errors

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wepay', '0019_convert_month13_to_monthly'),
    ]

    operations = [
        # Remove the unique constraint that prevents duplicate months
        migrations.RunSQL(
            "ALTER TABLE lp_month13_salary_details DROP INDEX unique_month_per_employee;",
            reverse_sql="ALTER TABLE lp_month13_salary_details ADD CONSTRAINT unique_month_per_employee UNIQUE (last_pay_record_id, coverage_month);"
        ),
    ]

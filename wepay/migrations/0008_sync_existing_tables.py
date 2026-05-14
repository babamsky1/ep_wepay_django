# Generated migration to sync with existing database tables

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wepay', '0007_lastpayrecord_emp_type_and_more'),
    ]

    operations = [
        # This is a no-op migration to mark existing tables as managed
        migrations.RunSQL(
            "-- Tables already exist with lp_ prefix",
            reverse_sql="-- No reverse operation needed"
        ),
    ]

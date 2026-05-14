# Generated migration for unified logging system

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('wepay', '0031_add_confidential_fields'),
    ]

    operations = [
        # Step 1: Drop old log tables
        migrations.RunSQL(
            """
            DROP TABLE IF EXISTS lp_audit_logs;
            DROP TABLE IF EXISTS lp_status_logs;
            """,
            reverse_sql=""
        ),

        # Step 2: Create the new GeneralLog model
        migrations.CreateModel(
            name='GeneralLog',
            fields=[
                ('log_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('table_id', models.CharField(max_length=255)),
                ('table_name', models.CharField(max_length=100)),
                ('action', models.CharField(max_length=50)),
                ('details', models.JSONField(default=dict)),
                ('performed_by', models.CharField(blank=True, max_length=255, null=True)),
                ('performed_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'general_logs',
                'ordering': ['-performed_at'],
            },
        ),

        # Step 3: Create indexes for the new table
        migrations.RunSQL(
            """
            CREATE INDEX idx_general_logs_table_name_id ON general_logs(table_name, table_id);
            CREATE INDEX idx_general_logs_action ON general_logs(action);
            CREATE INDEX idx_general_logs_performed_at ON general_logs(performed_at);
            """,
            reverse_sql=""
        ),

    ]

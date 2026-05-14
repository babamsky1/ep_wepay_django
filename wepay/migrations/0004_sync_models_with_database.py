# Generated manually to fix remaining model-field mismatches

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wepay', '0003_update_decimal_field_limits'),
    ]

    operations = [
        # Fix OvertimeDetail foreign key field name from emp_id to last_pay_record_id
        migrations.RenameField(
            model_name='overtimedetail',
            old_name='emp_id',
            new_name='last_pay_record_id',
        ),
        
        # Update remaining decimal fields that weren't covered in 0003
        migrations.AlterField(
            model_name='overtimedetail',
            name='rate',
            field=models.DecimalField(decimal_places=2, max_digits=15),
        ),
        migrations.AlterField(
            model_name='overtimedetail',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=15),
        ),
    ]

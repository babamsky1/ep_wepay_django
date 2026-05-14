# Generated manually to convert 13th month from date ranges to monthly periods

from django.db import migrations, models


def convert_dates_to_month(apps, schema_editor):
    """Convert existing tm_start_date to coverage_month format."""
    Month13SalaryDetail = apps.get_model('wepay', 'Month13SalaryDetail')
    
    for record in Month13SalaryDetail.objects.all():
        if record.tm_start_date:
            # Convert datetime to "Month YYYY" format
            month_name = record.tm_start_date.strftime('%B')
            year = record.tm_start_date.year
            record.coverage_month = f"{month_name} {year}"
            record.save()


def reverse_convert_month_to_dates(apps, schema_editor):
    """Reverse: convert coverage_month back to tm_start_date/tm_end_date."""
    Month13SalaryDetail = apps.get_model('wepay', 'Month13SalaryDetail')
    
    for record in Month13SalaryDetail.objects.all():
        if record.coverage_month:
            # Parse "Month YYYY" back to datetime
            try:
                month_name, year = record.coverage_month.split(' ')
                # Convert month name to number
                month_map = {
                    'January': 1, 'February': 2, 'March': 3, 'April': 4,
                    'May': 5, 'June': 6, 'July': 7, 'August': 8,
                    'September': 9, 'October': 10, 'November': 11, 'December': 12
                }
                month_num = month_map.get(month_name, 1)
                
                # Set start_date to first day of month
                record.tm_start_date = f"{year}-{month_num:02d}-01 00:00:00"
                # Set end_date to last day of month (simplified)
                if month_num == 12:
                    record.tm_end_date = f"{year}-12-31 23:59:59"
                else:
                    next_month = month_num + 1
                    record.tm_end_date = f"{year}-{next_month:02d}-01 00:00:00"
                record.save()
            except:
                pass


class Migration(migrations.Migration):

    dependencies = [
        ('wepay', '0018_remove_lastpayrecord_generated_at_and_more'),
    ]

    operations = [
        # Add new coverage_month field
        migrations.AddField(
            model_name='month13salarydetail',
            name='coverage_month',
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
        
        # Migrate data from tm_start_date to coverage_month
        migrations.RunPython(convert_dates_to_month, reverse_convert_month_to_dates),
        
        # Remove old date fields
        migrations.RemoveField(
            model_name='month13salarydetail',
            name='tm_start_date',
        ),
        migrations.RemoveField(
            model_name='month13salarydetail',
            name='tm_end_date',
        ),
        
        # Make coverage_month required after migration
        migrations.AlterField(
            model_name='month13salarydetail',
            name='coverage_month',
            field=models.CharField(max_length=20),
        ),
    ]

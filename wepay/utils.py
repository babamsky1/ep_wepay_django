from django.db.models import Q
from django.db import connection
from .models import LastPayRecord


def get_record_by_identifier(identifier):
    """Helper function to find LastPayRecord by last_pay_record_id or ref_no."""
    return LastPayRecord.objects.filter(
        Q(last_pay_record_id=identifier) | Q(ref_no=identifier)
    ).first()


class SQLLookupMixin:
    # Helper methods para kumuha company / department name / position

    @staticmethod
    def get_company_name(comp_id):
        # Get company name gamit comp_id

        if not comp_id:
            return "Unknown Company"

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT comp_name FROM company WHERE id = %s",
                    [comp_id]
                )

                result = cursor.fetchone()

                return result[0] if result else "Unknown Company"

        except Exception:
            return "Unknown Company"

    @staticmethod
    def get_department_name(dept_id, use_id_field=True):
        # Get department name gamit dept_id
        # use_id_field=True means id column gamitin (default since department table uses id)

        if not dept_id:
            return "Unknown Department"

        try:
            with connection.cursor() as cursor:

                field = 'id' if use_id_field else 'dept_id'

                cursor.execute(
                    f"SELECT dept_name FROM department WHERE {field} = %s",
                    [dept_id]
                )

                result = cursor.fetchone()

                return result[0] if result else "Unknown Department"

        except Exception:
            return "Unknown Department"

    @staticmethod
    def get_position(emp_id):
        # Get position gamit emp_id from employee_record table

        if not emp_id:
            return None

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT position FROM employee_record WHERE emp_id = %s",
                    [emp_id]
                )

                result = cursor.fetchone()

                return result[0] if result else None

        except Exception:
            return None

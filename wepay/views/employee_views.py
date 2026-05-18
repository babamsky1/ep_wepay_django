from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import connection, DatabaseError
from wepay.models import Employee, GeneralLog
from wepay.serializers import EmployeeSerializer, EmployeeListSerializer
import logging
from django.db.models import Q


# Pang logs sa terminal / server
logger = logging.getLogger(__name__)


# Mapping ng role name papuntang role_id sa database
# ROLE_MAP = {"superadmin": 1, "finance": 2, "hr": 3, "manager": 4}


def handle_database_error(operation_name):
    # Reusable decorator para i-handle database errors para di paulit-ulit try/except sa bawat API

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)

            # Kapag database issue
            except DatabaseError:
                return Response(
                    {
                        "result": "error",
                        "message": f"Database error during {operation_name}. Please try again later.",
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            # Kapag unexpected issue
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {str(e)}")

                return Response(
                    {
                        "result": "error",
                        "message": f"{operation_name} failed. Please contact support.",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return wrapper

    return decorator


@api_view(["GET"])
@handle_database_error("loading employees")
def employees_list(request):
    # pang search sa quit claim generation
    # Kunin lahat ng employees, optional search by ID or name with pagination

    employee_id = request.GET.get("employee_id", "").strip()
    employee_name = request.GET.get("employee_name", "").strip()
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 25))

    # Validate pagination params
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 25

    offset = (page - 1) * page_size

    employees = Employee.objects.filter()

    # Search by employee id
    if employee_id:
        employees = employees.filter(emp_id__icontains=employee_id)

    # Search by first name or last name - use Q objects for better performance
    if employee_name:
        employees = employees.filter(
            Q(first_name__icontains=employee_name)
            | Q(last_name__icontains=employee_name)
        )

    # Count total records after filters are applied
    total_count = employees.count()

    # Use select_related to optimize foreign key queries and sort with pagination
    employees = employees.select_related().order_by("last_name", "first_name")[
        offset : offset + page_size
    ]

    serializer = EmployeeListSerializer(employees, many=True)

    return Response(
        {
            "result": "success",
            "data": serializer.data,
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "message": "OK",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@handle_database_error("employee creation")
def employee_create(request):
    # for new employee account

    data = request.data

    # Default role = hr
    role_str = data.get("role", "hr")
    # role_id = ROLE_MAP.get(role_str, 3)

    # Inputs from frontend
    first_name = data.get("firstName")
    last_name = data.get("lastName")
    email_address = data.get("email")
    system_password = data.get("password")
    birth_date = data.get("birthDate")
    sex = data.get("sex")
    marital_stat = data.get("maritalStatus")

    # Required fields validation
    if not email_address or not system_password or not first_name or not last_name:
        return Response(
            {
                "result": "error",
                "message": "Email, password, first name, and last name are required",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    with connection.cursor() as cursor:

        # Kunin latest employee number
        cursor.execute(
            """
            SELECT emp_id
            FROM employee
            WHERE emp_id LIKE 'EMP-%'
            ORDER BY emp_id DESC
            LIMIT 1
        """
        )

        last_employee = cursor.fetchone()

        # Generate next employee number
        if last_employee:
            last_num = int(last_employee[0].split("-")[1])
            next_num = last_num + 1
        else:
            next_num = 1

        emp_id = f"EMP-{next_num:04d}"

        # Insert bagong employee
        cursor.execute(
            """
            INSERT INTO employee (
                emp_id,
                first_name,
                last_name,
                email_address,
                system_password,
                role_id,
                system_access,
                register_date,
                birth_date,
                sex,
                marital_stat
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,CURRENT_DATE,%s,%s,%s)
            """,
            [
                emp_id,
                first_name,
                last_name,
                email_address,
                system_password,
                role_id,
                "Y",
                birth_date or None,
                sex or None,
                marital_stat or None,
            ],
        )

    # Save audit log
    performed_by = data.get("performed_by", "system")

    GeneralLog.objects.create(
        table_id=emp_id,
        table_name="Employee",
        action="CREATE",
        details={
            "first_name": first_name,
            "last_name": last_name,
            "email": email_address,
            "role": role_str,
        },
        performed_by=performed_by,
    )

    return Response(
        {
            "result": "success",
            "message": "Employee created successfully",
            "emp_id": emp_id,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PUT"])
@handle_database_error("employee update")
def employee_update(request):
    # Update employee info

    data = request.data

    emp_id = data.get("emp_id")

    if not emp_id:
        return Response(
            {"result": "error", "message": "Employee ID is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    role_str = data.get("role")
    # role_id = ROLE_MAP.get(role_str) if role_str else None

    # New values from frontend
    first_name = data.get("firstName")
    last_name = data.get("lastName")
    email_address = data.get("email")
    system_password = data.get("password")
    birth_date = data.get("birthDate")
    sex = data.get("sex")
    marital_stat = data.get("maritalStatus")

    with connection.cursor() as cursor:

        # Kunin old values muna
        cursor.execute(
            """
            SELECT first_name, last_name, email_address,
                   role_id, birth_date, sex, marital_stat
            FROM employee
            WHERE emp_id = %s
        """,
            [emp_id],
        )

        employee_data = cursor.fetchone()

        if not employee_data:
            return Response(
                {"result": "error", "message": "Employee not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        (
            old_first_name,
            old_last_name,
            old_email,
            old_role_id,
            old_birth_date,
            old_sex,
            old_marital_stat,
        ) = employee_data

        # Compare old vs new values
        field_mappings = [
            ("first_name", first_name, old_first_name),
            ("last_name", last_name, old_last_name),
            ("email_address", email_address, old_email),
            ("birth_date", birth_date, old_birth_date),
            ("sex", sex, old_sex),
            ("marital_stat", marital_stat, old_marital_stat),
        ]

        update_fields = []
        params = []
        old_values = {}

        # Build dynamic update query
        for field, new_value, old_value in field_mappings:
            if new_value and new_value != old_value:
                update_fields.append(f"{field} = %s")
                params.append(new_value)
                old_values[field] = old_value

        # Update password if provided
        if system_password:
            update_fields.append("system_password = %s")
            params.append(system_password)

        # Update role if changed
        if role_id is not None and role_id != old_role_id:
            update_fields.append("role_id = %s")
            params.append(role_id)
            old_values["role"] = old_role_id

        # Execute update only if may changes
        if update_fields:
            params.append(emp_id)

            query = f"""
                UPDATE employee
                SET {', '.join(update_fields)}
                WHERE emp_id = %s
            """

            cursor.execute(query, params)

    # Save logs
    log_details = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email_address,
        "role": role_str,
        "old_values": old_values,
    }

    # Mark if password changed (only if actually updated)
    if "system_password" in update_fields:
        log_details["password_changed"] = True

    performed_by = data.get("performed_by", "system")

    GeneralLog.objects.create(
        table_id=emp_id,
        table_name="Employee",
        action="UPDATE",
        details=log_details,
        performed_by=performed_by,
    )

    return Response(
        {"result": "success", "message": "Employee updated successfully"},
        status=status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@handle_database_error("employee deletion")
def employee_delete(request):
    # Hard delete - physically remove employee from database

    emp_id = request.data.get("emp_id")

    if not emp_id:
        return Response(
            {"result": "error", "message": "Employee ID is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with connection.cursor() as cursor:

        # Get employee data for logging before deletion
        cursor.execute(
            """
            SELECT first_name, last_name, email_address,
                   role_id, system_access
            FROM employee
            WHERE emp_id = %s
        """,
            [emp_id],
        )

        employee_data = cursor.fetchone()

        if not employee_data:
            return Response(
                {"result": "error", "message": "Employee not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        first_name, last_name, email_address, role_id, system_access = employee_data

        # Delete related records first (manual cascade)
        cursor.execute("DELETE FROM employee_record WHERE emp_id = %s", [emp_id])
        cursor.execute("DELETE FROM lp_timesheet WHERE emp_id = %s", [emp_id])
        cursor.execute("DELETE FROM payroll_data WHERE emp_id = %s", [emp_id])

        # Hard delete the employee
        cursor.execute("DELETE FROM employee WHERE emp_id = %s", [emp_id])

    # Save logs
    performed_by = request.data.get("performed_by", "system")

    GeneralLog.objects.create(
        table_id=emp_id,
        table_name="Employee",
        action="DELETE",
        details={
            "message": f"Deleted employee: {first_name} {last_name} ({email_address})",
            "first_name": first_name,
            "last_name": last_name,
            "email": email_address,
            "role": role_id,
        },
        performed_by=performed_by,
    )

    return Response(
        {"result": "success", "message": "Employee deleted successfully"},
        status=status.HTTP_200_OK,
    )
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction, connection, DatabaseError, IntegrityError
from ..models import LastPayRecord, GeneralLog
from ..serializers import LastPayRecordSerializer, LastPayRecordListSerializer
from ..services import persist_totals
from ..utils import get_record_by_identifier
import logging

# Logger para sa errors sa backend
logger = logging.getLogger(__name__)

@api_view(["GET"])
def last_pay_records_list(request):
    # Kunin lahat ng last pay records with pagination
    # Optional filter gamit emp_id
    emp_id = request.GET.get("emp_id")
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 25))

    # Validate pagination params
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 25

    offset = (page - 1) * page_size

    try:
        with connection.cursor() as cursor:
            # Count query for total records
            count_query = """
                SELECT COUNT(*)
                FROM lp_last_pay_records lpr
            """
            count_params = []

            if emp_id:
                count_query += " WHERE lpr.emp_id = %s"
                count_params.append(emp_id)

            cursor.execute(count_query, count_params)
            total_count = cursor.fetchone()[0]

            # Main query with joins para kumpleto info
            query = """
                SELECT
                    lpr.last_pay_record_id,
                    lpr.ref_no,
                    lpr.emp_id,
                    COALESCE(
                        CONCAT(e.first_name, ' ', e.last_name),
                        lpr.emp_name
                    ) as emp_name,
                    lpr.position,
                    lpr.department_id,
                    lpr.emp_status,
                    lpr.comp_id,
                    COALESCE(
                        c.comp_name,
                        'Unknown Company'
                    ) as comp_name,
                    lpr.lp_status,
                    lpr.created_at,
                    lpr.updated_at,
                    lpr.update_by,
                    lpr.net_pay,
                    COALESCE(
                        er.bank_id,
                        lpr.bank_id
                    ) as bank_id,
                    COALESCE(
                        d.dept_name,
                        'Unknown Department'
                    ) as dept_name
                FROM lp_last_pay_records lpr
                LEFT JOIN employee e
                    ON lpr.emp_id = e.emp_id
                LEFT JOIN employee_record er
                    ON lpr.emp_id = er.emp_id
                LEFT JOIN company c
                    ON lpr.comp_id = c.id
                LEFT JOIN department d
                    ON lpr.department_id = d.id
            """

            params = []

            # If may emp_id filter
            if emp_id:
                query += " WHERE lpr.emp_id = %s"
                params.append(emp_id)

            # Latest first
            query += " ORDER BY lpr.created_at DESC"
            query += " LIMIT %s OFFSET %s"
            params.extend([page_size, offset])

            cursor.execute(query, params)

            # Column names
            columns = [col[0] for col in cursor.description]

            # Convert rows to dictionary
            records = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

        return Response(
            {
                "result": "success",
                "data": records,
                "total": total_count,
                "page": page,
                "page_size": page_size,
                "message": "OK"
            },
            status=status.HTTP_200_OK,
        )

    except DatabaseError:
        return Response(
            {
                "result": "error",
                "message": "Database connection error. Please try again later."
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    except Exception as e:
        logger.error(f"Unexpected error in last_pay_records_list: {str(e)}")
        return Response(
            {
                "result": "error",
                "message": "Failed to load records. Please contact support."
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

@api_view(["GET"])
def last_pay_records_detail(request, ref_no):
    # record detail
    try:
        # Hanapin record
        record = LastPayRecord.objects.get(ref_no=ref_no)

        # Serialize nested data
        serializer = LastPayRecordSerializer(record)
        data = serializer.data

        return Response(
            {
                "result": "success",
                "data": data,
                "message": "OK"
            },
            status=status.HTTP_200_OK,
        )

    except LastPayRecord.DoesNotExist:
        return Response(
            {
                "result": "error",
                "message": "Record not found"
            },
            status=status.HTTP_404_NOT_FOUND,
        )

@api_view(["PUT"])
def last_pay_records_edit(request):
    # Update existing record
    identifier = request.data.get("last_pay_record_id")

    if not identifier:
        return Response(
            {"result": "error", "message": "Identifier required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Hanapin record
    record = get_record_by_identifier(identifier)

    if not record:
        return Response(
            {"result": "error", "message": "Record not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Partial update allowed
    serializer = LastPayRecordSerializer(
        record,
        data=request.data,
        partial=True
    )

    if serializer.is_valid():
        try:
            with transaction.atomic():
                # Save updated values
                serializer.save()
                # Recompute totals
                persist_totals(record)

            data = serializer.data

            return Response(
                {
                    "result": "success",
                    "data": data,
                    "message": "Record updated successfully"
                },
                status=status.HTTP_200_OK,
            )

        except DatabaseError:
            return Response(
                {"result": "error", "message": "Database error during update. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        except IntegrityError:
            return Response(
                {"result": "error", "message": "Data integrity error during update."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            logger.error(f"Unexpected error in last_pay_records_edit: {str(e)}")
            return Response(
                {"result": "error", "message": "Update failed. Please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # Validation failed
    return Response(
        {
            "result": "error",
            "data": serializer.errors,
            "message": "Validation failed"
        },
        status=status.HTTP_400_BAD_REQUEST,
    )

@api_view(["DELETE"])
def last_pay_records_delete(request):
    # Delete record gamit last_pay_record_id
    identifier = request.data.get("last_pay_record_id")

    if not identifier:
        return Response(
            {"result": "error", "message": "Identifier required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Hanapin record
    record = get_record_by_identifier(identifier)

    if not record:
        return Response(
            {"result": "error", "message": "Record not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    record_name = record.emp_name
    user_name = request.data.get('performed_by', 'system')

    # Save delete logs bago idelete
    GeneralLog.objects.create(
        table_id=record.last_pay_record_id,
        table_name='LastPayRecord',
        action='DELETE',
        details={
            'ref_no': record.ref_no,
            'emp_name': record.emp_name,
            'emp_id': record.emp_id
        },
        performed_by=user_name
    )

    # Actual delete
    record.delete()

    return Response(
        {
            "result": "success",
            "data": None,
            "message": f"Record for {record_name} deleted successfully"
        },
        status=status.HTTP_200_OK,
    )

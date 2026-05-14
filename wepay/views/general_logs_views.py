from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import DatabaseError
from wepay.models import GeneralLog
from wepay.serializers import GeneralLogSerializer
import logging

# Pang logs sa terminal / server
logger = logging.getLogger(__name__)


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
                        "message": f"Database error during {operation_name}. Please try again later."
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            # Kapag unexpected issue
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {str(e)}")

                return Response(
                    {
                        "result": "error",
                        "message": f"{operation_name} failed. Please contact support."
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return wrapper
    return decorator


@api_view(["GET"])
@handle_database_error("loading logs")
def general_logs_list(request):
    """
    Optional filter by table_name / table_id, kunin lahat ng general logs with pagination
    """
    table_name = request.GET.get("table_name", "").strip()
    table_id = request.GET.get("table_id", "").strip()
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 25))

    # Validate pagination params
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 25

    offset = (page - 1) * page_size

    logs = GeneralLog.objects.all()

    # Filter by module/table
    if table_name:
        logs = logs.filter(table_name=table_name)

    # Filter by specific record id
    if table_id:
        logs = logs.filter(table_id=table_id)

    # Count total records
    total_count = logs.count()

    # Apply pagination and sort by performed_at desc (newest first)
    logs = logs.order_by('-performed_at')[offset:offset + page_size]

    serializer = GeneralLogSerializer(logs, many=True)

    return Response(
        {
            "result": "success",
            "data": serializer.data,
            "total": total_count,
            "page": page,
            "page_size": page_size,
        },
        status=status.HTTP_200_OK,
    )

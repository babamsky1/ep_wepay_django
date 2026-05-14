import traceback
import uuid
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from ..models import AdditionalsType, LastPayRecord
from ..serializers import AdditionalsTypeSerializer
from ..services import persist_totals
from ..signals import set_current_user, clear_current_user



@api_view(["GET"])
def additionals_type_list(request):
    # Kunin lahat ng Additionals Type records

    additionals = AdditionalsType.objects.all()

    serializer = AdditionalsTypeSerializer(
        additionals,
        many=True
    )

    return Response(
        {
            "result": "success",
            "data": serializer.data,
            "message": "OK"
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def additionals_type_create(request):
    # Gumawa bagong additional type record
    # Auto generate ad_type_id pag blank
    # Then recompute totals


    # Copy request para editable
    data = request.data.copy()

    # Auto generate ID
    data["ad_type_id"] = str(uuid.uuid4()).replace("-", "").upper()

    serializer = AdditionalsTypeSerializer(data=data)

    if serializer.is_valid():

        try:
            # Save new record
            instance = serializer.save()

            try:
                # Kunin related last pay record
                record = LastPayRecord.objects.get(
                    last_pay_record_id=instance.last_pay_record_id.last_pay_record_id
                )

                # Recompute totals
                persist_totals(record)

                return Response(
                    {
                        "result": "success",
                        "data": serializer.data,
                        "message": "Created and Totals Updated"
                    },
                    status=status.HTTP_200_OK,
                )

            except LastPayRecord.DoesNotExist:
                return Response(
                    {
                        "result": "error",
                        "message": f"LastPayRecord not found: {instance.last_pay_record_id}"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            return Response(
                {
                    "result": "error",
                    "message": f"Calculation Error: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # Validation failed
    return Response(
        {
            "result": "error",
            "data": serializer.errors,
            "message": "Validation Failed"
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["PUT"])
def additionals_type_edit(request):
    # Update existing additional type
    # Then recompute totals

    ad_type_id = (
        request.data.get("ad_type_id")
        or request.data.get("id")
    )

    try:
        # Hanapin record
        instance = AdditionalsType.objects.get(
            ad_type_id=ad_type_id
        )

        serializer = AdditionalsTypeSerializer(
            instance,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():

            # Save update
            serializer.save()

            # Kunin related last pay record
            record = LastPayRecord.objects.get(
                last_pay_record_id=instance.last_pay_record_id.last_pay_record_id
            )

            # Recompute totals
            persist_totals(record)

            return Response(
                {
                    "result": "success",
                    "data": serializer.data,
                    "message": "Updated and Totals Recalculated"
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "result": "error",
                "data": serializer.errors,
                "message": "Validation Failed"
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    except AdditionalsType.DoesNotExist:
        return Response(
            {
                "result": "error",
                "message": "Additional type not found"
            },
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["DELETE"])
def additionals_type_delete(request):
    # Delete additional type
    # Auto log via signals
    # Then recompute totals

    ad_type_id = (
        request.data.get("ad_type_id")
        or request.data.get("id")
    )

    try:
        # Hanapin record
        instance = AdditionalsType.objects.get(
            ad_type_id=ad_type_id
        )

        # User na gumawa delete
        performed_by = request.data.get(
            'performed_by',
            'system'
        )

        # Save sa thread-local para mabasa ng signals
        set_current_user(performed_by)

        try:
            # Save related record id bago delete
            last_pay_record_id = (
                instance.last_pay_record_id.last_pay_record_id
            )

            # Delete record
            # Audit log automatic sa signal
            instance.delete()

        finally:
            # Important cleanup ng thread local
            clear_current_user()

        # Recompute totals after delete
        record = LastPayRecord.objects.get(
            last_pay_record_id=last_pay_record_id
        )

        persist_totals(record)

        return Response(
            {
                "result": "success",
                "data": None,
                "message": "Deleted and Totals Updated"
            },
            status=status.HTTP_200_OK,
        )

    except AdditionalsType.DoesNotExist:
        return Response(
            {
                "result": "error",
                "message": "Not found"
            },
            status=status.HTTP_404_NOT_FOUND,
        )

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db import transaction, DatabaseError, IntegrityError
from ..models import LastPayRecord, GeneralLog
from ..serializers import LastPayRecordSerializer
from ..services import persist_totals
from ..utils import get_record_by_identifier
import logging

# Logger para makita errors sa backend
logger = logging.getLogger(__name__)

def get_user_name(request, data):
    # Kunin username mula request data
    # Kung wala, gamitin authenticated user
    user_name = data.get('updated_by')

    # If naka-login user sa Django auth
    if not user_name and hasattr(request, 'user') and request.user.is_authenticated:
        user_name = (
            request.user.username
            or request.user.get_full_name()
            or 'system'
        )

    return user_name or 'system'

def log_status_change(record, action, user_name, old_status=None):
    # Save audit log kapag nagbago quit claim status
    old_status = old_status or record.lp_status

    # Determine new status based sa action
    new_status = (
        action if action in ['FINALIZED', 'APPROVED', 'RELEASED', 'DISAPPROVED']
        else 'PENDING' if action == 'REOPENED'
        else record.lp_status
    )

    # Save sa GeneralLog
    GeneralLog.objects.create(
        table_id=record.last_pay_record_id,
        table_name='LastPayRecord',
        action=action,
        details={
            'ref_no': record.ref_no,
            'old_status': old_status,
            'new_status': new_status
        },
        performed_by=user_name
    )

@api_view(["PUT"])
def quit_claim_update_status(request):
    # Update quit claim status: FINALIZED / APPROVED / RELEASED / DISAPPROVED
    last_pay_record_id = request.data.get('last_pay_record_id')
    new_status = request.data.get('status')
    remark = request.data.get('remark', '')
    user_name = get_user_name(request, request.data)

    # Required fields
    if not last_pay_record_id or not new_status:
        return Response(
            {
                'result': 'error',
                'message': 'last_pay_record_id and status are required'
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Allowed statuses
    valid_statuses = [
        'FINALIZED',
        'APPROVED',
        'RELEASED',
        'DISAPPROVED'
    ]

    if new_status not in valid_statuses:
        return Response(
            {
                'result': 'error',
                'message': f'Invalid status. Must be one of: {valid_statuses}'
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Hanapin record
    record = get_record_by_identifier(last_pay_record_id)

    if not record:
        return Response(
            {
                'result': 'error',
                'message': 'Quit claim record not found'
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    current_time = timezone.now()

    # Set latest status
    record.lp_status = new_status

    # Save timestamps based on status
    if new_status == 'FINALIZED':
        record.finalized_at = current_time
        record.finalized_by = user_name
        log_status_change(record, 'FINALIZED', user_name)

    elif new_status == 'APPROVED':
        record.approved_at = current_time
        record.approved_by = user_name
        log_status_change(record, 'APPROVED', user_name)

    elif new_status == 'RELEASED':
        record.released_at = current_time
        record.released_by = user_name
        log_status_change(record, 'RELEASED', user_name)

    elif new_status == 'DISAPPROVED':
        record.disapproved_at = current_time
        record.disapproved_by = user_name
        record.disapprove_remark = remark
        log_status_change(record, 'DISAPPROVED', user_name)

    # Common update fields
    record.updated_at = current_time
    record.update_by = user_name

    try:
        with transaction.atomic():
            # Save changes
            record.save()

            # Recompute totals
            persist_totals(record)

    except DatabaseError:
        return Response(
            {
                'result': 'error',
                'message': 'Database error occurred. Please try again later.'
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    except IntegrityError:
        return Response(
            {
                'result': 'error',
                'message': 'Data integrity error. Please check your inputs.'
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        logger.error(f"Unexpected error in quit_claim_update_status: {str(e)}")
        return Response(
            {
                'result': 'error',
                'message': 'Internal server error. Please contact support.'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    serializer = LastPayRecordSerializer(record)

    return Response(
        {
            'result': 'success',
            'data': serializer.data,
            'message': f'Quit claim status updated to {new_status}'
        },
        status=status.HTTP_200_OK,
    )







@api_view(["PUT"])
def quit_claim_reopen(request):
    # Reopen quit claim
    # Status magiging PENDING
    # Clear approval/final/release history
    last_pay_record_id = request.data.get('last_pay_record_id')
    user_name = get_user_name(request, request.data)

    if not last_pay_record_id:
        return Response(
            {
                'result': 'error',
                'message': 'last_pay_record_id is required'
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Hanapin record
    record = get_record_by_identifier(last_pay_record_id)

    if not record:
        return Response(
            {
                'result': 'error',
                'message': 'Quit claim record not found'
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    current_time = timezone.now()

    # Save old status for logs
    old_status = record.lp_status

    # Reset status to pending
    record.lp_status = 'PENDING'

    # Clear previous workflow data
    record.finalized_at = None
    record.finalized_by = None
    record.approved_at = None
    record.approved_by = None
    record.released_at = None
    record.released_by = None
    record.disapproved_at = None
    record.disapproved_by = None
    record.disapprove_remark = None

    record.updated_at = current_time
    record.update_by = user_name

    log_status_change(record, 'REOPENED', user_name, old_status)

    try:
        with transaction.atomic():
            record.save()
            persist_totals(record)

    except DatabaseError:
        return Response(
            {
                'result': 'error',
                'message': 'Database error occurred during reopen. Please try again later.'
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    except IntegrityError:
        return Response(
            {
                'result': 'error',
                'message': 'Data integrity error during reopen.'
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        logger.error(f"Unexpected error in quit_claim_reopen: {str(e)}")
        return Response(
            {
                'result': 'error',
                'message': 'Reopen operation failed. Please contact support.'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    serializer = LastPayRecordSerializer(record)

    return Response(
        {
            'result': 'success',
            'data': serializer.data,
            'message': 'Quit claim reopened successfully'
        },
        status=status.HTTP_200_OK,
    )


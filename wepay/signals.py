"""
Django signals para sa centralized audit logging.

Dito naka-handle lahat ng automatic audit trail gamit signals.
Para hindi na paulit-ulit ang logging code sa views at serializers.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from .models import GeneralLog, AdditionalsType
import threading


# ---------------------------------------------------------
# THREAD LOCAL STORAGE
# ---------------------------------------------------------
# Ginagamit para maipasa current user habang tumatakbo
# ang request -> signal flow
# ---------------------------------------------------------

_thread_local = threading.local()


def set_current_user(user_name):
    """
    Save current user sa thread local storage.
    Para alam ng signal kung sino gumawa ng action.
    """
    _thread_local.current_user = user_name or 'system'


def get_current_user():
    """
    Kunin current user.
    Default = system kapag walang user.
    """
    return getattr(_thread_local, 'current_user', 'system')


def clear_current_user():
    """
    Linisin ang stored user pagkatapos ng process.
    Iwas maling user sa next request.
    """
    if hasattr(_thread_local, 'current_user'):
        delattr(_thread_local, 'current_user')


# ---------------------------------------------------------
# ADDITIONALS TYPE AUDIT LOGGING
# ---------------------------------------------------------

@receiver(post_save, sender=AdditionalsType)
def log_additionals_type_changes(sender, instance, created, **kwargs):
    """
    Automatic audit log kapag create/update ng AdditionalsType.
    """

    try:
        performed_by = get_current_user()

        # ---------------------------------
        # CREATE
        # ---------------------------------
        if created:

            action = "CREATE"

            details = {
                'description': instance.description,
                'amount': str(instance.amount),
                'addtl_type': instance.addtl_type,
                'is_confidential': instance.is_confidential,
                'last_pay_record_id': (
                    str(instance.last_pay_record_id.last_pay_record_id)
                    if instance.last_pay_record_id else None
                )
            }

        # ---------------------------------
        # UPDATE
        # ---------------------------------
        else:

            action = "UPDATE"

            # Old values galing serializer tracking
            old_description = getattr(
                instance,
                '_old_description',
                None
            )

            old_amount = getattr(
                instance,
                '_old_amount',
                None
            )

            old_is_confidential = getattr(
                instance,
                '_old_is_confidential',
                None
            )

            details = {
                'description': instance.description,
                'amount': str(instance.amount),
                'addtl_type': instance.addtl_type,
                'is_confidential': instance.is_confidential,
                'last_pay_record_id': (
                    str(instance.last_pay_record_id.last_pay_record_id)
                    if instance.last_pay_record_id else None
                )
            }

            # Isama lumang values kung meron
            if (
                old_description is not None
                or old_amount is not None
                or old_is_confidential is not None
            ):

                details['old_values'] = {}

                if old_description is not None:
                    details['old_values']['description'] = old_description

                if old_amount is not None:
                    details['old_values']['amount'] = str(old_amount)

                if old_is_confidential is not None:
                    details['old_values']['is_confidential'] = old_is_confidential

            # Check kung nagbago confidentiality
            if (
                hasattr(instance, '_confidentiality_changed')
                and instance._confidentiality_changed
            ):
                details['confidentiality_changed'] = True

        # ---------------------------------
        # SAVE AUDIT LOG
        # ---------------------------------
        GeneralLog.objects.create(
            table_id=instance.ad_type_id,
            table_name='AdditionalsType',
            action=action,
            details=details,
            performed_by=performed_by,
        )

    except Exception as e:
        # Huwag pigilan main transaction kapag log fail
        print(f"Failed to create audit log via signal: {e}")


# ---------------------------------------------------------
# DELETE LOGGING (OPTIONAL)
# ---------------------------------------------------------

@receiver(post_delete, sender=AdditionalsType)
def log_additionals_type_delete(sender, instance, **kwargs):
    """
    Automatic log kapag delete.
    """

    try:
        performed_by = get_current_user()

        GeneralLog.objects.create(
            table_id=instance.ad_type_id,
            table_name='AdditionalsType',
            action='DELETE',
            details={
                'description': instance.description,
                'amount': str(instance.amount),
                'addtl_type': instance.addtl_type,
            },
            performed_by=performed_by
        )

    except Exception as e:
        print(f"Failed to create delete log: {e}")

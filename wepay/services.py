from django.db.models import Sum
from .models import (
    AdditionalsType,
    LastPayRecord,
)
from decimal import Decimal
import calendar
from django.db import connection


# =============================================================================
# ADDITIONAL PAYABLES AND DEDUCTIONS CALCULATIONS
# =============================================================================

def compute_total_payables(record) -> float:
    """Sum all additional payables (additionals with addtl_type='P')."""
    return sum(
        float(payable.amount or 0)
        for payable in record.additionalstype_set.filter(addtl_type='P')
    )


def compute_total_deductions(record) -> float:
    """Sum all additional deductions (additionals with addtl_type='D')."""
    return sum(
        float(deduction.amount or 0)
        for deduction in record.additionalstype_set.filter(addtl_type='D')
    )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def persist_totals(record) -> None:
    """Update record totals based on additional payables and deductions."""
    record.lp_total_payables = compute_total_payables(record)
    record.lp_total_deductions = compute_total_deductions(record)

    # Recalculate net_pay: 13th month + last pay + payables - deductions
    old_net_pay = record.net_pay
    record.net_pay = Decimal(str(record.lp_total_tm)) + Decimal(str(record.last_pay)) + \
        Decimal(str(record.lp_total_payables)) - \
        Decimal(str(record.lp_total_deductions))


    record.save(update_fields=[
        'lp_total_payables',
        'lp_total_deductions',
        'net_pay',
    ])






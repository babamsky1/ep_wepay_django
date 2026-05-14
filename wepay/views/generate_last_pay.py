import calendar
import re
import traceback
import uuid
import logging
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN

from django.db import connection, transaction, DatabaseError, IntegrityError
from django.db.models import DecimalField, Min, Max, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from rest_framework.decorators import api_view
from rest_framework.response import Response

from wepay.models import (
    AllowanceTable, Employee, EmployeeAllowance,
    EmployeeLeave, EmployeeLoans,
    EmployeeRecord, LastPayRecord, LeaveMonthlyDetail, LeaveRequest, LoanDetail,
    Month13SalaryDetail, OvertimeDetail,
    PayrollData, ThirteenThMonthData, TimeSheet,
)
from wepay.serializers import LastPayRecordSerializer, GeneralLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper — TODO: ilipat sa shared utils.py para hindi mag-duplicate
# sa timesheet_upload_views.py
# ---------------------------------------------------------------------------
def get_employee_schedule(emp_id, tran_date):
    """
    Kunin ang schedule ng employee para sa specific na date.
    Una, tingnan ang employee_schedule (specific date).
    Kung wala, tingnan ang employee_schedule_default (weekly default).
    Returns: (time_in, time_out, rest_day, total_work_mins) or None
    """
    day_of_week = tran_date.isoweekday()  # 1=Monday, 7=Sunday

    with connection.cursor() as cursor:
        # check muna kung may special schedule
        cursor.execute(
            """
            SELECT time_in, time_out, rest_day, total_work_mins
            FROM employee_schedule
            WHERE emp_id = %s AND tran_date = %s
            """,
            [emp_id, tran_date],
        )
        result = cursor.fetchone()
        if result:
            return result
        # pag walang schedule sa special, gamitin yung default
        cursor.execute(
            """
            SELECT time_in, time_out, rest_day, total_work_mins
            FROM employee_schedule_default
            WHERE emp_id = %s AND tran_day = %s
            """,
            [emp_id, day_of_week],
        )
        return cursor.fetchone()


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------
@api_view(["GET"])
def generate__last_pay(request):

    emp_id = request.GET.get("emp_id")
    active_user = request.GET.get("active_user")

    if not emp_id:
        return Response({"error": "emp_id is required"}, status=400)

    emp_id = emp_id.strip()

    try:
        last_payroll_data = (
            PayrollData.objects.filter(emp_id=emp_id)
            .select_related("payroll")
            .order_by("-payroll__period_end_date")
            .first()
        )

        if last_payroll_data and last_payroll_data.payroll:
            # Magsimula sa araw pagkatapos ng huling araw ng payroll period
            period_start = last_payroll_data.payroll.period_end_date + timedelta(days=1)
        else:
            # Fallback: gamitin ang pinaka-unang timesheet date
            ts_first = TimeSheet.objects.filter(emp_id=emp_id).aggregate(ts_start=Min("tran_date"))
            period_start = ts_first["ts_start"]

        # Huling araw ng employment = pinaka-huling timesheet date
        last_day = TimeSheet.objects.filter(emp_id=emp_id).aggregate(
            ts_end=Max("tran_date")
        )["ts_end"]

        if last_day is None:
            return Response(
                {
                    "success": False,
                    "message": f"No timesheet records found for employee {emp_id}.",
                    "code": "NO_TIMESHEET_RECORDS",
                },
                status=400,
            )

    except Exception:
        logger.exception("Timesheet date resolution failed for emp_id=%s", emp_id)
        return Response(
            {
                "success": False,
                "message": "Could not resolve timesheet dates. Please try again.",
                "code": "TIMESHEET_VALIDATION_ERROR",
            },
            status=500,
        )

    # I-reject kung may existing na hindi pa released na last pay record
    if LastPayRecord.objects.filter(emp_id=emp_id).exclude(lp_status="R").exists():
        return Response(
            {
                "success": False,
                "message": "User already has an existing transaction. Refresh the page.",
                "code": "EXISTING_TRANSACTION",
            },
            status=409,
        )

    # --- Main computation — lahat nasa loob ng atomic transaction ---
    try:
        with transaction.atomic():

            # Kunin ang employee master data
            try:
                employee = Employee.objects.get(emp_id=emp_id)
                employee_record = EmployeeRecord.objects.get(emp_id=emp_id)
            except Employee.DoesNotExist:
                return Response({"error": "Employee not found"}, status=404)

            payroll_generation = employee_record.payroll_generation.upper()

            employee_name = " ".join(
                filter(None, [employee.first_name, employee.last_name, employee.middle_name])
            )

            # Fixed constants — 8 hrs/day, 480 mins/day
            avg_hours_per_day = Decimal("8.0")
            avg_work_mins_per_day = Decimal("480")

            # Kunin ang pre-computed timesheet totals mula sa lp_timesheet
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        SUM(basic_hours)  AS total_basic_hours,
                        SUM(absent_days)  AS total_absent_days,
                        SUM(late_mins)    AS total_late_mins,
                        SUM(ut_mins)      AS total_ut_mins
                    FROM lp_timesheet
                    WHERE emp_id = %s
                      AND tran_date BETWEEN %s AND %s
                    """,
                    [emp_id, period_start, last_day],
                )
                timesheet_totals = cursor.fetchone()

            total_basic_hours = Decimal(str(timesheet_totals[0] or 0))
            absent_days       = Decimal(str(timesheet_totals[1] or 0))
            total_late_mins   = Decimal(str(timesheet_totals[2] or 0))
            total_ut_mins     = Decimal(str(timesheet_totals[3] or 0))

            # Rates
            daily_rate    = Decimal(str(employee_record.daily_rate))
            avg_hour_rate = daily_rate / avg_hours_per_day  # Para sa overtime computation

            # Days worked — iba ang logic para sa FIXED vs DAILY
            sal_type = employee_record.sal_type.upper() if employee_record.sal_type else "DAILY"

            if sal_type == "FIXED":
                # FIXED: magsimula sa 13 days, ibabawas ang absent/late/UT
                base_days  = Decimal("13.00")
                late_days  = total_late_mins / avg_work_mins_per_day
                ut_days    = total_ut_mins   / avg_work_mins_per_day
                days_worked = max(base_days - absent_days - late_days - ut_days, Decimal("0.00"))
            else:
                # DAILY: i-derive ang days mula sa basic_hours
                # basic_hours na accounts for late/UT — hindi na kailangan ibawas ulit
                basic_days  = total_basic_hours / avg_work_mins_per_day
                days_worked = max(basic_days - absent_days, Decimal("0.00"))

            # 13th month: ibalik ang late/UT deductions — hindi binabawas dito
            late_days_13th = total_late_mins / avg_work_mins_per_day
            ut_days_13th   = total_ut_mins   / avg_work_mins_per_day
            days_for_13th  = max(days_worked + late_days_13th + ut_days_13th, Decimal("0.00"))

            # Basic pay at absent amount
            basic_pay  = max(days_worked * daily_rate, Decimal("0.00"))
            absent_amt = absent_days * daily_rate

            # --- Leave credit computation ---
            employee_leave_allocation = EmployeeLeave.objects.filter(
                emp_id=emp_id,
                year=str(last_day.year),
            ).first()

            total_leave_hrs = (
                Decimal(str(employee_leave_allocation.total_days or 0))
                if employee_leave_allocation
                else Decimal("0")
            )

            # Kunin ang approved leaves grouped by month para sa LeaveMonthlyDetail records
            approved_leave_by_month = (
                LeaveRequest.objects.filter(
                    emp_id=emp_id,
                    status="AP",
                    sched_date__year=last_day.year,
                )
                .values("sched_date__month", "sched_date__year")
                .annotate(total_used_hrs=Sum("approved_hrs"))
                .order_by("sched_date__month")
            )

            # I-sum ang lahat ng used hours para makuha ang remaining
            total_used_hrs = Decimal("0")
            for m in approved_leave_by_month:
                total_used_hrs += Decimal(str(m["total_used_hrs"] or 0))

            remaining_hrs  = max(total_leave_hrs - total_used_hrs, Decimal("0"))
            remaining_days = remaining_hrs / avg_hours_per_day
            leave_credit_amt = daily_rate * remaining_days

            # --- Schedule filter para sa allowances at loans ---
            if payroll_generation == "WEEKLY":
                sched_filter = ["E"]
            else:
                sched_filter = ["E", "1"] if last_day.day <= 15 else ["E", "3"]

            # --- Allowances ---
            employee_allowance = EmployeeAllowance.objects.filter(
                emp_id=emp_id,
                active="Y",
                date_start__lte=last_day,
                sched__in=sched_filter,
            ).select_related("allow")

            total_allowance_amt = Decimal(
                str(employee_allowance.aggregate(total=Sum("amount")).get("total") or 0)
            )

            # I-prorate ang allowance base sa actual days worked
            std_period_days = Decimal("5") if payroll_generation == "WEEKLY" else Decimal("13")

            rem_allowance = (
                (total_allowance_amt / std_period_days) * days_worked
                if total_allowance_amt > 0
                else Decimal("0.00")
            )

            # --- Loans ---
            employee_loans = EmployeeLoans.objects.filter(
                emp_id=emp_id,
                date_start__lte=last_day,
                sched__in=sched_filter,
            ).select_related("loan")

            total_loan_balance = employee_loans.aggregate(
                total=Coalesce(Sum("balance_amount"), 0, output_field=DecimalField())
            )["total"]

            # --- Overtime ---
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT a.emp_id, a.sched_date, b.ot_code, b.applied_hrs,
                           IF(c.sal_type = 'DAILY', d.daily_percent, d.fixed_percent) AS ot_multiplier
                    FROM ot_request a
                    INNER JOIN ot_request_applied b ON a.id = b.req_id
                    LEFT JOIN ot_multiplier d ON b.ot_code = d.code
                    LEFT JOIN employee_record c ON a.emp_id = c.emp_id
                    WHERE a.emp_id = %s
                      AND a.status = 'AP'
                      AND a.sched_date BETWEEN %s AND %s
                    ORDER BY a.sched_date, b.ot_code
                    """,
                    [emp_id, period_start, last_day],
                )
                columns     = [col[0] for col in cursor.description]
                overtime_res = [dict(zip(columns, row)) for row in cursor.fetchall()]

            # I-compute ang total OT amount
            total_ot_amt = Decimal("0.00")
            for ot in overtime_res:
                hours    = Decimal(str(ot["applied_hrs"]))
                mult     = Decimal(str(ot["ot_multiplier"]))
                raw_amt  = (hours * avg_hour_rate) * mult
                total_ot_amt += raw_amt.quantize(Decimal("0.00"), rounding=ROUND_HALF_EVEN)

            # --- 13th month pay ---
            # basic_pay_for_13th_month: base sa days_for_13th (walang late/UT deduction)
            basic_pay_for_13th_month = days_for_13th * daily_rate

            latest_13th_month = (
                ThirteenThMonthData.objects.filter(emp_id=emp_id, head__status="A")
                .select_related("head")
                .order_by("-head__generated_date")
                .values("head__payroll_type", "head__generated_date", "head__trantype")
                .first()
            )

            # Months na ililista sa 13th month computation
            thirteenthmont_pay_first = [12, 1, 2, 3, 4, 5]
            results_thirteenth       = []
            grand_total_thirteenth   = Decimal("0.00")

            with connection.cursor() as cursor:
                is_leaving_second_half = last_day.month >= 6

                if (
                    latest_13th_month
                    and latest_13th_month.get("head__trantype") == "2ND"
                    and not is_leaving_second_half
                ):
                    # Natanggap na ang 2nd-half 13th month — i-compute lang ang 1st-half months
                    months_to_process = thirteenthmont_pay_first
                else:
                    # I-process ang Jan hanggang buwan bago mag-last_day (full payroll periods lang)
                    months_to_process = list(range(1, last_day.month))

                for month in months_to_process:
                    year             = last_day.year - 1 if month == 12 else last_day.year
                    last_day_of_month = calendar.monthrange(year, month)[1]
                    start_date       = f"{year}-{month:02d}-01"
                    end_date         = f"{year}-{month:02d}-{last_day_of_month}"

                    cursor.execute(
                        """
                        SELECT
                            b.period_start_date,
                            b.period_end_date,
                            SUM(a.total_allowance + a.vl_amt + a.sl_amt
                                + (a.daily_rate * (a.days_work - a.days_absent))) AS total_amt,
                            SUM(a.days_absent) AS days_absent
                        FROM payroll_data a
                        LEFT JOIN payroll_header b ON a.payroll_id = b.id
                        WHERE b.payroll_date BETWEEN %s AND %s
                          AND a.emp_id = %s
                        GROUP BY b.period_start_date, b.period_end_date
                        ORDER BY b.period_start_date
                        """,
                        [start_date, end_date, emp_id],
                    )
                    for row in cursor.fetchall():
                        period_start_date, period_end_date, period_total, period_days_absent = row
                        if period_total and period_total > 0:
                            results_thirteenth.append(
                                {
                                    "month": month,
                                    "year": year,
                                    "total": period_total,
                                    "days_absent": period_days_absent,
                                    "period_start_date": period_start_date,
                                    "period_end_date": period_end_date,
                                }
                            )
                            grand_total_thirteenth += Decimal(str(period_total))

            # Idagdag ang current period basic pay sa grand total ng 13th month
            grand_total_thirteenth += basic_pay_for_13th_month

            amount_thirteenth = (grand_total_thirteenth / Decimal("12")).quantize(
                Decimal("1.00"), rounding=ROUND_HALF_EVEN
            )

            # --- Last pay at net pay ---
            last_pay = max(
                basic_pay + rem_allowance + total_ot_amt + leave_credit_amt,
                Decimal("0.00"),
            )

            # Loans ay para sa display lang — hindi ibinabawas sa net pay
            total_net_pay = max(amount_thirteenth + last_pay, Decimal("0.00"))

            # --- I-generate ang reference number ---
            new_last_pay_record_id = str(uuid.uuid4()).replace("-", "").upper()
            gen_header = f"REF{timezone.now().strftime('%m%y')}"

            last_record = (
                LastPayRecord.objects.filter(ref_no__startswith=gen_header)
                .order_by("-ref_no")
                .first()
            )
            if last_record:
                match      = re.search(r"-(\d+)$", last_record.ref_no)
                new_number = (int(match.group(1)) + 1) if match else 1
            else:
                new_number = 1

            new_ref_no = f"{gen_header}-{new_number:04d}"

            # I-store ang aware datetimes para sa cut-off fields
            cut_off_start_dt = timezone.make_aware(datetime.combine(period_start, datetime.min.time()))
            cut_off_end_dt   = timezone.make_aware(datetime.combine(last_day,     datetime.min.time()))

            # --- I-save ang LastPayRecord ---
            new_record = LastPayRecord(
                last_pay_record_id=new_last_pay_record_id,
                ref_no=new_ref_no,
                lp_status="PENDING",
                emp_id=emp_id,
                emp_name=employee_name,
                emp_status=employee_record.emp_status,
                bank_id=employee_record.bank_id,
                comp_id=employee_record.comp_id,
                emp_type=employee_record.payroll_type,
                department_id=employee_record.dept_id,
                position=employee_record.position,
                daily_rate=employee_record.daily_rate,
                total_days_worked=days_worked,
                basic_pay=basic_pay,
                lp_total_absents=absent_amt,
                lp_total_late_amt=Decimal("0.00"),   # Basic_hours na ang nag-account ng late
                lp_total_ut_amt=Decimal("0.00"),      # Basic_hours na ang nag-account ng UT
                employee_start_date=employee_record.date_hired,
                employee_end_date=last_day,
                cut_off_start_date=cut_off_start_dt,
                cut_off_end_date=cut_off_end_dt,
                last_pay=last_pay,
                lp_total_ot=total_ot_amt,
                lp_total_leave=leave_credit_amt,
                lp_total_allowance=rem_allowance,
                lp_total_loan_balance=total_loan_balance,
                lp_total_tm=amount_thirteenth,
                net_pay=total_net_pay,
                created_at=timezone.now(),
                created_by=active_user,
                update_by=active_user,
                updated_at=timezone.now(),
            )
            new_record.save()

            # I-log ang generation
            GeneralLog.objects.create(
                table_id=new_record.last_pay_record_id,
                table_name="LastPayRecord",
                action="GENERATED",
                details={"ref_no": new_record.ref_no, "new_status": new_record.lp_status},
                performed_by=active_user or "system",
            )

            # I-save ang allowance details
            for allowance in employee_allowance:
                AllowanceTable(
                    allowance_id=str(uuid.uuid4()).replace("-", "").upper(),
                    last_pay_record_id=new_record,
                    allowance_desc=allowance.allow.description,
                    amount=allowance.amount,
                ).save()

            # I-save ang loan details
            for loan in employee_loans:
                LoanDetail(
                    loan_id=str(uuid.uuid4()).replace("-", "").upper(),
                    last_pay_record_id=new_record,
                    loan_description=loan.loan.description,
                    paid_amt=loan.paid_amount,
                    loan_amt=loan.loan_amount,
                    balance_amt=loan.balance_amount,
                ).save()

            # I-save ang overtime details
            for ot in overtime_res:
                hours       = Decimal(str(ot["applied_hrs"]))
                mult        = Decimal(str(ot["ot_multiplier"]))
                raw_amt     = (hours * avg_hour_rate) * mult
                rounded_amt = raw_amt.quantize(Decimal("0.00"), rounding=ROUND_HALF_EVEN)
                OvertimeDetail(
                    overtime_id=str(uuid.uuid4()).replace("-", "").upper(),
                    last_pay_record_id=new_record,
                    date_granted=ot.get("sched_date"),
                    hours=ot.get("applied_hrs") or 0,
                    rate=avg_hour_rate,
                    amount=rounded_amt,
                    ot_type=ot.get("ot_code"),
                ).save()

            # I-save ang 13th month details
            # Una: historical payroll months, para maiwasan ang duplication
            for res in results_thirteenth:
                Month13SalaryDetail(
                    tm_id=str(uuid.uuid4()).replace("-", "").upper(),
                    last_pay_record_id=new_record,
                    month=res["month"] or 0,
                    year=res["year"] or 0,
                    days_absent=res["days_absent"] or 0,
                    total_amt=res["total"] or 0,
                    period_start_date=res.get("period_start_date"),
                    period_end_date=res.get("period_end_date"),
                ).save()

            # Pangalawa: current period — isang beses lang, hiwalay sa loop
            if basic_pay_for_13th_month > 0:
                Month13SalaryDetail(
                    tm_id=str(uuid.uuid4()).replace("-", "").upper(),
                    last_pay_record_id=new_record,
                    month=last_day.month,
                    year=last_day.year,
                    days_absent=0,
                    total_amt=basic_pay_for_13th_month,
                    period_start_date=period_start,
                    period_end_date=last_day,
                ).save()

            # I-save ang leave monthly details
            if approved_leave_by_month:
                cumulative_used_hrs = Decimal("0")
                for month_data in approved_leave_by_month:
                    month    = month_data["sched_date__month"]
                    year     = month_data["sched_date__year"]
                    used_hrs = Decimal(str(month_data["total_used_hrs"] or 0))
                    used_days_detail = used_hrs / avg_hours_per_day

                    cumulative_used_hrs    += used_hrs
                    running_remaining_hrs   = max(total_leave_hrs - cumulative_used_hrs, Decimal("0"))
                    running_remaining_days  = (running_remaining_hrs / avg_hours_per_day).quantize(Decimal("0.01"))

                    LeaveMonthlyDetail(
                        leave_id=str(uuid.uuid4()).replace("-", "").upper(),
                        last_pay_record_id=new_record,
                        days_used=used_days_detail,
                        remaining=running_remaining_days,
                        coverage_month=month,
                        year=year,
                    ).save()
            elif total_leave_hrs > 0:
                # Walang approved leaves pero may allocation — i-record ang full remaining
                LeaveMonthlyDetail(
                    leave_id=str(uuid.uuid4()).replace("-", "").upper(),
                    last_pay_record_id=new_record,
                    days_used=Decimal("0.00"),
                    remaining=(total_leave_hrs / avg_hours_per_day).quantize(Decimal("0.01")),
                    coverage_month=last_day.month,
                    year=last_day.year,
                ).save()

        # I-return ang saved record
        serializer = LastPayRecordSerializer(new_record)
        return Response(serializer.data)

    except DatabaseError as e:
        logger.exception("DatabaseError in generate_last_pay for emp_id=%s", emp_id)
        return Response(
            {
                "error": "Database error during last pay generation. Please try again later.",
                "detail": str(e),
            },
            status=503,
        )
    except IntegrityError as e:
        logger.exception("IntegrityError in generate_last_pay for emp_id=%s", emp_id)
        return Response(
            {
                "error": "Data integrity error during last pay generation.",
                "detail": str(e),
            },
            status=400,
        )
    except Exception as e:
        logger.error(
            "Unexpected error in generate_last_pay for emp_id=%s:\n%s",
            emp_id,
            traceback.format_exc(),
        )
        return Response(
            {
                "error": "Last pay generation failed. Please contact support.",
                "detail": str(e),
            },
            status=500,
        )
from rest_framework import serializers
from django.db import connection
from .utils import SQLLookupMixin
from .models import (
    Employee,
    LastPayRecord,
    AdditionalsType,
    LoanDetail,
    LeaveMonthlyDetail,
    Month13SalaryDetail,
    OvertimeDetail,
    AllowanceTable,
    GeneralLog,
    TimesheetRecord,
)

from .services import (
    compute_total_payables,
    compute_total_deductions,
    persist_totals,
)

from .signals import set_current_user, clear_current_user


class GeneralLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralLog
        fields = "__all__"


class LoanDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanDetail
        fields = "__all__"


class LeaveMonthlyDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveMonthlyDetail
        fields = "__all__"


class Month13SalaryDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Month13SalaryDetail
        fields = "__all__"


class OvertimeDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = OvertimeDetail
        fields = "__all__"


class AllowanceTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = AllowanceTable
        fields = "__all__"


class EmployeeFieldsMixin:
    """Shared position/dept/company fields for Employee serializers"""

    def _get_employee_record(self, obj):
        try:
            from .models import EmployeeRecord

            return EmployeeRecord.objects.filter(emp_id=obj.emp_id).first()
        except:
            return None

    def get_position(self, obj):
        record = self._get_employee_record(obj)
        return record.position if record else None

    def get_dept_name(self, obj):
        record = self._get_employee_record(obj)
        if record and record.dept_id:
            return self.get_department_name(record.dept_id)
        return None

    def get_company(self, obj):
        record = self._get_employee_record(obj)
        if record and record.comp_id:
            return self.get_company_name(record.comp_id)
        return None


class EmployeeListSerializer(
    EmployeeFieldsMixin, SQLLookupMixin, serializers.ModelSerializer
):
    # lightweight list
    position = serializers.SerializerMethodField()
    dept_name = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            "emp_id",
            "first_name",
            "last_name",
            "email_address",
            "role_id",
            "system_access",
            "system_password",
            "position",
            "dept_name",
            "company",
        ]


# ---------------------------------------------------------
# ADDITIONALS TYPE
# ---------------------------------------------------------


class AdditionalsTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = AdditionalsType
        fields = "__all__"

    def create(self, validated_data):
        # Create with signal user context

        set_current_user(validated_data.get("created_by", "system"))

        try:
            instance = AdditionalsType.objects.create(**validated_data)

            return instance

        finally:
            clear_current_user()

    def update(self, instance, validated_data):
        # Update with audit tracking

        # Old values for logs
        instance._old_description = instance.description
        instance._old_amount = instance.amount
        instance._old_is_confidential = instance.is_confidential

        old_confidential = instance.is_confidential
        new_confidential = validated_data.get("is_confidential", old_confidential)

        # Flag if changed
        if old_confidential != new_confidential:
            instance._confidentiality_changed = True

        set_current_user(validated_data.get("updated_by", "system"))

        try:
            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.save()

            return instance

        finally:
            clear_current_user()


# ---------------------------------------------------------
# LAST PAY RECORD
# ---------------------------------------------------------


class LastPayRecordListSerializer(serializers.ModelSerializer):

    # lightweight list serializer, for last pay page
    class Meta:
        model = LastPayRecord
        fields = [
            "last_pay_record_id",
            "ref_no",
            "emp_id",
            "emp_name",
            "position",
            "department_id",
            "emp_status",
            "comp_id",
            "lp_status",
            # "generated_at",
        ]


class LastPayRecordSerializer(SQLLookupMixin, serializers.ModelSerializer):
    # Full serializer with nested fields

    payables = serializers.SerializerMethodField()
    deductions = serializers.SerializerMethodField()

    audit_logs = serializers.SerializerMethodField()
    status_logs = serializers.SerializerMethodField()

    total_payables_computed = serializers.SerializerMethodField()
    total_deductions_computed = serializers.SerializerMethodField()

    # computed_month13_remaining_balance = serializers.SerializerMethodField()
    gross_amount_computed = serializers.SerializerMethodField()
    accumulated_13th_month_computed = serializers.SerializerMethodField()
    # absent_days_computed = serializers.SerializerMethodField()
    # total_working_days_amount_computed = serializers.SerializerMethodField()

    comp_name = serializers.SerializerMethodField()
    dept_name = serializers.SerializerMethodField()

    # Nested detail serializers for frontend display
    leave_monthly_breakdown = serializers.SerializerMethodField()
    month13_salary_periods = serializers.SerializerMethodField()
    loans = serializers.SerializerMethodField()
    allowances = serializers.SerializerMethodField()
    overtime = serializers.SerializerMethodField()

    class Meta:
        model = LastPayRecord
        fields = "__all__"

    # -----------------------
    # Read Methods
    # -----------------------

    def _get_additionals_by_type(self, obj, addtl_type):
        items = obj.additionalstype_set.filter(addtl_type=addtl_type)

        return AdditionalsTypeSerializer(items, many=True).data

    def get_payables(self, obj):
        return self._get_additionals_by_type(obj, "P")

    def get_deductions(self, obj):
        return self._get_additionals_by_type(obj, "D")

    def get_audit_logs(self, obj):
        logs = GeneralLog.objects.filter(
            table_name="AdditionalsType",
            table_id__in=obj.additionalstype_set.values_list("ad_type_id", flat=True),
        ).order_by("-performed_at")

        return GeneralLogSerializer(logs, many=True).data

    def get_status_logs(self, obj):
        logs = GeneralLog.objects.filter(
            table_name="LastPayRecord", table_id=obj.last_pay_record_id
        ).order_by("-performed_at")

        return GeneralLogSerializer(logs, many=True).data

    def get_total_payables_computed(self, obj):
        return compute_total_payables(obj)

    def get_total_deductions_computed(self, obj):
        return compute_total_deductions(obj)

    # def get_computed_month13_remaining_balance(self, obj):
    #     # Calculate remaining 13th month balance
    #     # This would typically be computed from month13_salary_periods
    #     try:
    #         total_13th = sum(
    #             float(m.total_amt or 0) for m in obj.month13salarydetail_set.all()
    #         )
    #         return float(obj.lp_total_tm or 0) - total_13th
    #     except:
    #         return 0.0

    def get_gross_amount_computed(self, obj):
        return (
            float(obj.last_pay or 0)
            + float(obj.lp_total_tm or 0)
            + float(obj.lp_total_payables or 0)
        )

    def get_accumulated_13th_month_computed(self, obj):
        # Total accumulated 13th month from salary periods
        try:
            return sum(
                float(m.total_amt or 0) for m in obj.month13salarydetail_set.all()
            )
        except:
            return 0.0

    # def get_absent_days_computed(self, obj):
    #     # Computed absent days from lp_total_absents
    #     return float(obj.lp_total_absents or 0)

    # def get_total_working_days_amount_computed(self, obj):
    #     # Total working days amount = daily_rate * total_days_worked
    #     return float(obj.daily_rate or 0) * float(obj.total_days_worked or 0)

    def get_comp_name(self, obj):
        return self.get_company_name(obj.comp_id)

    def get_dept_name(self, obj):
        return self.get_department_name(obj.department_id)

    def get_leave_monthly_breakdown(self, obj):
        """Get leave monthly breakdown details"""
        return LeaveMonthlyDetailSerializer(
            obj.leavemonthlydetail_set.all(), many=True
        ).data

    def get_month13_salary_periods(self, obj):
        """Get 13th month salary period details"""
        return Month13SalaryDetailSerializer(
            obj.month13salarydetail_set.all(), many=True
        ).data

    def get_loans(self, obj):
        """Get loan details"""
        return LoanDetailSerializer(obj.loandetail_set.all(), many=True).data

    def get_allowances(self, obj):
        """Get allowance details"""
        return AllowanceTableSerializer(obj.allowancetable_set.all(), many=True).data

    def get_overtime(self, obj):
        """Get overtime details"""
        return OvertimeDetailSerializer(obj.overtimedetail_set.all(), many=True).data

    # -----------------------
    # Write Helpers
    # -----------------------

    def to_internal_value(self, data):
        # Capture nested arrays from frontend

        self.nested_payables = data.pop("payables", [])
        self.nested_deductions = data.pop("deductions", [])

        return super().to_internal_value(data)

    def _build_nested_item(self, item, last_pay_record, addtl_type):
        data = {
            k: v
            for k, v in item.items()
            if k not in ("last_pay_record", "last_pay_record_id")
        }

        data["last_pay_record_id"] = last_pay_record
        data["addtl_type"] = addtl_type

        return data

    # -----------------------
    # Create / Update
    # -----------------------

    def create(self, validated_data):

        payables_data = getattr(self, "nested_payables", [])

        deductions_data = getattr(self, "nested_deductions", [])

        last_pay_record = LastPayRecord.objects.create(**validated_data)

        # Save payables
        for payable in payables_data:
            AdditionalsType.objects.create(
                **self._build_nested_item(payable, last_pay_record, "P")
            )

        # Save deductions
        for deduction in deductions_data:
            AdditionalsType.objects.create(
                **self._build_nested_item(deduction, last_pay_record, "D")
            )

        # Compute totals
        persist_totals(last_pay_record)

        return last_pay_record

    def update(self, instance, validated_data):

        payables_data = getattr(self, "nested_payables", None)

        deductions_data = getattr(self, "nested_deductions", None)

        # Update main fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Replace payables
        if payables_data is not None:
            AdditionalsType.objects.filter(
                last_pay_record_id=instance, addtl_type="P"
            ).delete()

            for payable in payables_data:
                AdditionalsType.objects.create(
                    **self._build_nested_item(payable, instance, "P")
                )

        # Replace deductions
        if deductions_data is not None:
            AdditionalsType.objects.filter(
                last_pay_record_id=instance, addtl_type="D"
            ).delete()

            for deduction in deductions_data:
                AdditionalsType.objects.create(
                    **self._build_nested_item(deduction, instance, "D")
                )

        # Recompute if nested changed
        if payables_data is not None or deductions_data is not None:
            persist_totals(instance)

        return instance


# ---------------------------------------------------------
# TIMESHEET
# ---------------------------------------------------------
class TimesheetRecordSerializer(SQLLookupMixin, serializers.ModelSerializer):

    class Meta:
        model = TimesheetRecord
        fields = [
            "timesheet_id",
            "emp_id",
            "emp_name",
            "uploaded_at",
            "uploaded_by",
            "updated_at",
            "updated_by",
        ]


# ---------------------------------------------------------
# EMPLOYEE
# ---------------------------------------------------------

class EmployeeSerializer(
    EmployeeFieldsMixin, SQLLookupMixin, serializers.ModelSerializer
):

    position = serializers.SerializerMethodField()
    dept_name = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = "__all__"

from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid

from rest_framework import serializers
from django.core.validators import MinValueValidator, MaxValueValidator


class GeneralLog(models.Model):
    log_id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    table_id = models.CharField(max_length=255)
    table_name = models.CharField(max_length=100)
    action = models.CharField(max_length=50)
    details = models.JSONField(default=dict)
    performed_by = models.CharField(max_length=255, null=True, blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "general_logs"
        ordering = ["-performed_at"]
        indexes = [
            models.Index(fields=["table_name", "table_id"]),
            models.Index(fields=["action"]),
            models.Index(fields=["performed_at"]),
        ]

    def __str__(self):
        return f"{self.action} on {self.table_name} by {self.performed_by} at {self.performed_at}"


class LastPayRecord(models.Model):
    last_pay_record_id = models.CharField(max_length=50, primary_key=True)
    ref_no = models.CharField(max_length=50, unique=True)
    lp_status = models.CharField(
        max_length=20,
        choices=[
            ("PENDING", "Pending"),
            ("FINALIZED", "Finalized"),
            ("RELEASED", "Released"),
            ("APPROVED", "Approved"),
            ("DISAPPROVED", "Disapproved"),
            ("DRAFT", "Draft"),
        ],
        default="DRAFT",
    )
    emp_id = models.CharField(max_length=50, db_index=True)
    emp_name = models.CharField(max_length=255)
    emp_type = models.CharField(max_length=50, default="Regular")
    emp_status = models.CharField(max_length=5, default="Reg")
    bank_id = models.CharField(max_length=50, default="")
    comp_id = models.CharField(max_length=50, default="")
    department_id = models.CharField(max_length=50, db_index=True, default="")
    position = models.CharField(max_length=100, db_index=True, default="")
    daily_rate = models.DecimalField(max_digits=15, decimal_places=2)
    total_days_worked = models.DecimalField(max_digits=5, decimal_places=2)
    basic_pay = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    employee_start_date = models.DateField()
    employee_end_date = models.DateField()
    cut_off_start_date = models.DateTimeField()
    cut_off_end_date = models.DateTimeField()
    last_pay = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    lp_total_ot = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    lp_total_leave = models.DecimalField(max_digits=15, decimal_places=2, null=True)
    lp_total_allowance = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    lp_total_absents = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00
    )
    lp_total_late_amt = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00
    )
    lp_total_ut_amt = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    lp_total_payables = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00
    )
    lp_total_deductions = models.DecimalField(
        max_digits=15, decimal_places=2, default=0.00
    )
    lp_total_loan_balance = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    lp_total_tm = models.DecimalField(max_digits=15, decimal_places=2)
    net_pay = models.DecimalField(max_digits=15, decimal_places=2)
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    update_by = models.CharField(max_length=255, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=255, null=True, blank=True)
    finalized_by = models.CharField(max_length=255, null=True, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=255, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    disapproved_by = models.CharField(max_length=255, null=True, blank=True)
    disapproved_at = models.DateTimeField(null=True, blank=True)
    disapprove_remark = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "lp_last_pay_records"
        verbose_name = "Last Pay Record"
        verbose_name_plural = "Last Pay Records"

    def __str__(self):
        return (
            f"{self.emp_name} - {self.employee_start_date} to {self.employee_end_date}"
        )


class AdditionalsType(models.Model):
    ad_type_id = models.CharField(max_length=50, primary_key=True)
    last_pay_record_id = models.ForeignKey(
        LastPayRecord,
        on_delete=models.CASCADE,
        db_column="last_pay_record_id",
        db_index=True,
    )
    addtl_type = models.CharField(
        max_length=1, choices=[("P", "Payable"), ("D", "Deduction")]
    )
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=255, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=255, null=True, blank=True)
    is_confidential = models.CharField(max_length=1, null=True, blank=True)
    created_by_role = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "lp_addtl_details"
        verbose_name = "Additional Detail"
        verbose_name_plural = "Additional Details"

    def __str__(self):
        return f"{self.description} - {self.addtl_type}"


class LoanDetail(models.Model):
    loan_id = models.CharField(max_length=50, primary_key=True)
    last_pay_record_id = models.ForeignKey(
        LastPayRecord,
        on_delete=models.CASCADE,
        db_column="last_pay_record_id",
        db_index=True,
    )
    loan_description = models.CharField(max_length=255)
    loan_amt = models.DecimalField(max_digits=15, decimal_places=2)
    paid_amt = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    balance_amt = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = "lp_loan_details"
        verbose_name = "Loan Detail"
        verbose_name_plural = "Loan Details"

    def __str__(self):
        return f"{self.loan_description} - {self.loan_amt}"

    @property
    def loan_balance(self):
        return self.loan_amt - (self.paid_amt or 0)


class LeaveMonthlyDetail(models.Model):
    leave_id = models.CharField(max_length=50, primary_key=True)
    last_pay_record_id = models.ForeignKey(
        LastPayRecord,
        on_delete=models.CASCADE,
        db_column="last_pay_record_id",
        db_index=True,
    )
    days_used = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    remaining = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    coverage_month = models.SmallIntegerField()
    year = models.SmallIntegerField()

    class Meta:
        db_table = "lp_leave_monthly_details"
        verbose_name = "Leave Monthly Detail"
        verbose_name_plural = "Leave Monthly Details"

    def __str__(self):
        return f"Leave {self.leave_id} - {self.days_used} days used"


class Month13SalaryDetail(models.Model):
    tm_id = models.CharField(max_length=50, primary_key=True)
    last_pay_record_id = models.ForeignKey(
        LastPayRecord,
        on_delete=models.CASCADE,
        db_column="last_pay_record_id",
        db_index=True,
    )
    month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )

    year = models.IntegerField(
        validators=[MinValueValidator(1900), MaxValueValidator(2100)]
    )
    total_amt = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    days_absent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    period_start_date = models.DateField(
        null=True, blank=True, db_comment="Payroll period start date"
    )
    period_end_date = models.DateField(
        null=True, blank=True, db_comment="Payroll period end date"
    )

    class Meta:
        db_table = "lp_month13_salary_details"
        verbose_name = "13th Month Salary Detail"
        verbose_name_plural = "13th Month Salary Details"

    def __str__(self):
        return f"13th Month {self.period_start_date} to {self.period_end_date} - {self.total_amt}"


class OvertimeDetail(models.Model):
    overtime_id = models.CharField(max_length=50, primary_key=True)
    last_pay_record_id = models.ForeignKey(
        LastPayRecord,
        on_delete=models.CASCADE,
        db_column="last_pay_record_id",
        db_index=True,
    )
    date_granted = models.DateTimeField(default=timezone.now)
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    rate = models.DecimalField(max_digits=15, decimal_places=2)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.CharField(max_length=255, null=True, blank=True)
    ot_type = models.CharField(max_length=20, default="Regular")

    class Meta:
        db_table = "lp_overtime_details"
        verbose_name = "Overtime Detail"
        verbose_name_plural = "Overtime Details"

    def __str__(self):
        return f"{self.hours} hours"


class AllowanceTable(models.Model):
    allowance_id = models.CharField(max_length=50, primary_key=True, editable=False)
    last_pay_record_id = models.ForeignKey(
        LastPayRecord,
        on_delete=models.CASCADE,
        db_column="last_pay_record_id",
        db_index=True,
    )
    allowance_desc = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = "lp_allowance_table"
        verbose_name = "Allowance"
        verbose_name_plural = "Allowances"

    def __str__(self):
        return f"{self.allowance_desc} - {self.amount}"

    def save(self, *args, **kwargs):
        """Auto-generate allowance_id if not provided"""
        if not self.allowance_id:
            self.allowance_id = f"AL-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class Employee(models.Model):
    emp_id = models.CharField(primary_key=True, max_length=15, db_comment="Employee ID")
    biometric_id = models.IntegerField(blank=True, null=True)
    register_date = models.DateField(db_comment="Registration Date")
    last_name = models.CharField(max_length=50, db_comment="Last Name")
    first_name = models.CharField(max_length=50, db_comment="First Name")
    middle_name = models.CharField(
        max_length=50, blank=True, null=True, db_comment="Middle Name"
    )
    suffix = models.CharField(
        max_length=10, blank=True, null=True, db_comment="Name Suffix"
    )
    alias_name = models.CharField(
        max_length=100, blank=True, null=True, db_comment="Alias Name"
    )
    title = models.CharField(max_length=30, blank=True, null=True, db_comment="Title")
    mother_maiden_name = models.CharField(
        max_length=100, blank=True, null=True, db_comment="Mother Full Maiden name"
    )
    citizenship = models.CharField(
        max_length=50, blank=True, null=True, db_comment="citizenship"
    )
    birth_date = models.DateField(db_comment="Date of Birth", blank=True, null=True)
    birth_place = models.CharField(
        max_length=255, blank=True, null=True, db_comment="Place of Birth"
    )
    sex = models.CharField(
        max_length=10, db_comment="Male, Female", blank=True, null=True
    )
    marital_stat = models.CharField(
        max_length=10,
        db_comment=" S    = Single\r\n M  = Married\r\n W  = Widowed\r\n D  = Divorced\r\n X = Separated",
        blank=True,
        null=True,
    )
    height = models.CharField(max_length=20, blank=True, null=True, db_comment="Height")
    weight = models.CharField(max_length=20, blank=True, null=True, db_comment="Weight")
    religion = models.CharField(
        max_length=30, blank=True, null=True, db_comment="Religion"
    )
    addr1 = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        db_comment="Lot/Block/Phase/Unit/Room/Floor/Bldg/Sub. Street",
    )
    addr2 = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        db_comment="Bldg No/Street Name/Subd/Village/Zone",
    )
    brgy = models.CharField(
        max_length=100, blank=True, null=True, db_comment="Barangay"
    )
    municipality = models.CharField(
        max_length=100, blank=True, null=True, db_comment="Municipality/City/District"
    )
    province = models.CharField(
        max_length=100, blank=True, null=True, db_comment="Province"
    )
    zip_code = models.CharField(
        max_length=15, blank=True, null=True, db_comment="Zip Code"
    )
    country = models.CharField(
        max_length=100, blank=True, null=True, db_comment="Country"
    )
    phone_no = models.CharField(
        max_length=20, blank=True, null=True, db_comment="Phone number"
    )
    local_no = models.CharField(
        max_length=10, blank=True, null=True, db_comment="Phone number local"
    )
    mobile_no = models.CharField(
        max_length=20, blank=True, null=True, db_comment="Mobile number"
    )
    role_id = models.IntegerField(blank=True, null=True)
    email_address = models.CharField(
        max_length=255, blank=True, null=True, db_comment="Email address"
    )
    emer_contact_name = models.CharField(
        max_length=150, blank=True, null=True, db_comment="Emergency contact name"
    )
    emer_contact_rel = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        db_comment="Emergency contact relationship",
    )
    emer_contact_no = models.CharField(
        max_length=20, blank=True, null=True, db_comment="Emergency contact number"
    )
    emer_contact_no_local = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        db_comment="Emergency contact number local",
    )
    emer_contact_address = models.CharField(
        max_length=255, blank=True, null=True, db_comment="Emergency contact address"
    )
    spouse_name = models.CharField(
        max_length=255, blank=True, null=True, db_comment="Spouse name"
    )
    spouse_phone_no = models.CharField(
        max_length=20, blank=True, null=True, db_comment="Spouse phone number"
    )
    spouse_local_no = models.CharField(
        max_length=10, blank=True, null=True, db_comment="Spouse phone number local"
    )
    spouse_mobile_no = models.CharField(
        max_length=20, blank=True, null=True, db_comment="Spouse mobile number"
    )
    spouse_occupation = models.CharField(
        max_length=255, blank=True, null=True, db_comment="Spouse occupation"
    )
    system_access = models.CharField(
        max_length=1, blank=True, null=True, db_comment=" Y = Yes,\r\n N = No"
    )
    system_password = models.CharField(
        max_length=255, blank=True, null=True, db_comment="System access password"
    )
    password_hint = models.CharField(
        max_length=255, blank=True, null=True, db_comment="Password Hint"
    )
    emp_pic = models.TextField(blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.CharField(max_length=255, blank=True, null=True)
    is_compressed = models.CharField(max_length=1, blank=True, null=True)
    is_approver = models.CharField(max_length=1, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "employee"
        verbose_name = "Employee"
        verbose_name_plural = "Employees"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.emp_id})"


class EmployeeRecord(models.Model):
    comp_id = models.CharField(max_length=3, null=False, db_comment="Employee ID")
    emp_id = models.CharField(
        max_length=15, null=False, primary_key=True, db_comment="Employee ID"
    )
    dept_id = models.CharField(max_length=15, null=False, db_comment="Department ID")
    position = models.CharField(
        max_length=255, blank=True, null=True, db_comment="Position in company"
    )
    emp_status = models.CharField(
        max_length=20,
        db_comment="CONTRACTUAL \r\nPROBATIONARY\r\nREGULAR\r\nPROJECT BASED\r\nRESIGNED \r\nTERMINATED \r\nAWOL\r\nEND OF SERVICE",
    )
    date_hired = models.DateField(db_comment="Hired date")
    date_regularization = models.DateField(
        blank=True, null=True, db_comment="Regularization Date"
    )
    date_eos = models.DateField(blank=True, null=True, db_comment="End of Service Date")
    payroll_type = models.CharField(
        max_length=20, db_comment=" Regular, \r\n Production"
    )
    payroll_generation = models.CharField(
        max_length=15, db_comment="Weekly,\r\nSemi-Monthly,\r\nMonthly"
    )
    sal_type = models.CharField(
        max_length=10, db_comment="Daily,\r\nFixed,\r\nProduction"
    )
    required_inout = models.CharField(max_length=1, db_comment=" Y = Yes,\r\n N = No")
    daily_rate = models.FloatField(db_comment="Daily Rate")
    monthly_rate = models.FloatField(db_comment="Monthly Rate")
    ecola_rate = models.FloatField(db_comment="Ecola Rate per day")
    bank_id = models.CharField(max_length=15, null=False, db_comment="Bank Id")
    account_no = models.CharField(
        max_length=50, blank=True, null=True, db_comment="Bank account number"
    )
    mgr_id = models.CharField(
        max_length=15, blank=True, null=True, db_comment="Manager OT Approver ID"
    )
    region_id = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "employee_record"

    def __str__(self):
        return f"{self.comp_id} {self.emp_id}"


class PayrollHeader(models.Model):
    id = models.CharField(
        primary_key=True,
        max_length=15,
        db_comment=" Payroll header key\r\n format : YYYYDD-XXXX",
    )
    comp_id = models.CharField(max_length=3, db_comment="Company ID")
    payroll_date = models.DateField(db_comment="Payroll Date")
    payroll_type = models.CharField(
        max_length=1, db_comment=" R = Regular Payroll, \r\n P = Production Payroll"
    )
    payroll_generation = models.CharField(
        max_length=1, db_comment=" W = Weekly,\r\n S  = Semi-Monthly,\r\n M = Monthly"
    )
    week_no = models.IntegerField(db_comment="Week No for weekly payroll")
    period_start_date = models.DateField(db_comment="period covered from")
    period_end_date = models.DateField(db_comment="period covered to")
    pay_status = models.CharField(max_length=1)
    date_dtr_generated = models.DateTimeField(blank=True, null=True)
    date_pay_generated = models.DateTimeField(blank=True, null=True)
    is_locked = models.CharField(max_length=1, blank=True, null=True)
    prod_head_id = models.IntegerField(
        blank=True,
        null=True,
        db_comment="Production Summary head ID null for non production",
    )
    locked_by = models.CharField(max_length=100, blank=True, null=True)
    locked_date = models.DateTimeField(blank=True, null=True)
    locked_remarks = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "payroll_header"
        unique_together = (
            ("comp_id", "payroll_date", "payroll_type", "payroll_generation"),
        )

    def __str__(self):
        return f"{self.id}"


class PayrollData(models.Model):
    pk = models.CompositePrimaryKey("payroll_id", "emp_id")
    payroll = models.ForeignKey(
        "PayrollHeader",
        models.DO_NOTHING,
        db_comment=" Payroll header key\r\n format : YYYYDD-XXXX",
    )
    emp_id = models.ForeignKey(
        "Employee", models.DO_NOTHING, db_column="emp_id", db_comment="Employee ID"
    )
    last_name = models.CharField(max_length=50, db_comment="Last Name")
    first_name = models.CharField(max_length=50, db_comment="First Name")
    middle_name = models.CharField(
        max_length=50, blank=True, null=True, db_comment="Middle Name"
    )
    alias_name = models.CharField(
        max_length=100, blank=True, null=True, db_comment="Alias Name"
    )
    title = models.CharField(max_length=30, blank=True, null=True, db_comment="Title")
    suffix = models.CharField(
        max_length=10, blank=True, null=True, db_comment="Name Suffix"
    )
    dept_id = models.CharField(max_length=15, db_comment="Department ID")
    position = models.CharField(
        max_length=255, blank=True, null=True, db_comment="Position in company"
    )
    emp_status = models.CharField(
        max_length=1,
        db_comment=" C = Contractual, \r\n P = Probationary, \r\n R = Regular, \r\n X = Resigned, \r\n T = Terminated, \r\n A = AWOL\r\n E = End of Service",
    )
    payroll_type = models.CharField(
        max_length=1,
        db_comment=" R = Regular Payroll, \r\n P = Production Payroll\r\n U = Undefine",
    )
    payroll_generation = models.CharField(
        max_length=15,
        db_comment=" W = Weekly,\r\n S  = Semi-Monthly,\r\n M = Monthly\r\n U = Undefine",
    )
    sal_type = models.CharField(
        max_length=10,
        db_comment=" D = Daily Earner,\r\n F = Fixed Earner,\r\n P = Production Output\r\n U = Undefine",
    )
    daily_rate = models.FloatField(db_comment="Daily Rate")
    monthly_rate = models.FloatField(db_comment="Monthly Rate")
    bank_id = models.CharField(max_length=15, db_comment="Bank ID")
    account_no = models.CharField(
        max_length=50, blank=True, null=True, db_comment="Bank account number"
    )
    days_work = models.FloatField(db_comment="Not apllicable for production")
    days_absent = models.FloatField(
        blank=True,
        null=True,
        db_comment="Days absent not applicable for daily earner and production",
    )
    vl_days = models.FloatField()
    sl_days = models.FloatField()
    vl_amt = models.FloatField()
    sl_amt = models.FloatField()
    basic_pay = models.FloatField(
        blank=True,
        null=True,
        db_comment=" Daily Earner = hrs work * hrs rate\r\n Fixed Earner = Compute based on rate given\r\n Production  = Total completed amount ",
    )
    ecola_rate = models.FloatField(db_comment="Ecola Rate per day")
    ecola_amount = models.FloatField(db_comment="Ecola Rate * Daily Rate")
    time_absent_amt = models.FloatField(
        blank=True,
        null=True,
        db_comment="Days absent amount not applicable for daily earner and production",
    )
    time_late = models.IntegerField(db_comment="minutes")
    time_undertime = models.IntegerField(db_comment="minutes")
    time_late_amt = models.FloatField()
    time_undertime_amt = models.FloatField()
    ot_total_amount = models.FloatField()
    adj_nontax = models.FloatField()
    adj_taxable = models.FloatField()
    adj_late_ot = models.FloatField()
    adj_late_ob = models.FloatField()
    adj_late_leave = models.FloatField()
    gross_pay = models.FloatField(db_comment="Total Taxable income")
    total_allowance = models.FloatField()
    other_deductions = models.FloatField()
    loans = models.FloatField()
    sss_ee = models.FloatField()
    sss_er = models.FloatField()
    sss_ec_er = models.FloatField()
    sss_ec_ee = models.FloatField()
    sss_mpf_ee = models.FloatField()
    sss_mpf_er = models.FloatField()
    pag_ee = models.FloatField()
    pag_er = models.FloatField()
    ph_ee = models.FloatField()
    ph_er = models.FloatField()
    tax_ee = models.FloatField()
    total_gov_ded = models.FloatField(db_comment="Total government employee share")
    total_non_tax = models.FloatField(
        blank=True, null=True, db_comment="Total non taxable income"
    )
    netpay = models.FloatField(
        blank=True, null=True, db_comment="gross pay - total_gov_ded + total_non_tax"
    )
    notes = models.CharField(max_length=500, blank=True, null=True)
    notes_late_ot = models.TextField(blank=True, null=True)
    notes_late_ob = models.TextField(blank=True, null=True)
    notes_late_leave = models.TextField(blank=True, null=True)
    auto_gov_sss = models.CharField(max_length=1, db_comment="Y=Yes, N=No")
    auto_gov_pag = models.CharField(max_length=1, db_comment="Y=Yes, N=No")
    auto_gov_ph = models.CharField(max_length=1, db_comment="Y=Yes, N=No")
    auto_gov_tax = models.CharField(max_length=1, db_comment="Y=Yes, N=No")
    region_id = models.CharField(
        max_length=30, blank=True, null=True, db_comment="Region ID"
    )

    class Meta:
        managed = False
        db_table = "payroll_data"

    def __str__(self):
        return f"{self.pk}"


class TimeSheet(models.Model):
    pk = models.CompositePrimaryKey("emp_id", "tran_date")
    emp_id = models.ForeignKey(
        "Employee", models.DO_NOTHING, db_column="emp_id", db_comment="Employee ID"
    )
    tran_date = models.DateField(db_comment="Transaction Date")
    default_time_in = models.TimeField(blank=True, null=True)
    default_time_out = models.TimeField(blank=True, null=True)
    actual_time_in = models.TimeField(blank=True, null=True, db_comment="HH:MM")
    actual_time_out = models.TimeField(blank=True, null=True, db_comment="HH:MM")
    is_rest_day = models.CharField(
        max_length=1, blank=True, null=True, db_comment="Y/N"
    )
    is_compressed = models.CharField(
        max_length=1, blank=True, null=True, db_comment="Y/N"
    )
    basic_days = models.FloatField(blank=True, null=True, db_comment="days")
    absent_days = models.FloatField(blank=True, null=True, db_comment="days")
    late_mins = models.IntegerField(db_comment="minutes late")
    ut_mins = models.IntegerField(db_comment="minutes ut")
    vl_days = models.FloatField(blank=True, null=True)
    sl_days = models.FloatField(blank=True, null=True)
    basic_hours = models.FloatField(blank=True, null=True)
    days_worked = models.FloatField(blank=True, null=True)
    absent_hours = models.FloatField(blank=True, null=True)
    vl_hours = models.FloatField(blank=True, null=True)
    sl_hours = models.FloatField(blank=True, null=True)
    gerkie_data_id = models.CharField(max_length=30, blank=True, null=True)
    # log_import_data_id = models.CharField(
    #     max_length=30,
    #     blank=True,
    #     null=True,
    #     db_comment="logistic attendance import data",
    # )
    ot_request_id = models.CharField(max_length=30, blank=True, null=True)
    leave_request_id = models.CharField(max_length=30, blank=True, null=True)
    ob_request_id = models.CharField(max_length=30, blank=True, null=True)
    date_generated = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "lp_timesheet"

    def __str__(self):
        return f"{self.pk}"


class TimesheetRecord(models.Model):
    """Model to store processed timesheet records for display in datatable."""

    timesheet_id = models.CharField(
        max_length=50, primary_key=True, db_comment="Timesheet ID"
    )
    emp_id = models.ForeignKey(
        "Employee", models.DO_NOTHING, db_column="emp_id", db_comment="Employee ID"
    )
    emp_name = models.CharField(max_length=255, db_comment="Employee Name")
    uploaded_at = models.DateTimeField(auto_now_add=True, db_comment="Upload Timestamp")
    uploaded_by = models.CharField(
        max_length=255, blank=True, null=True, db_comment="Uploaded By"
    )
    updated_at = models.DateTimeField(auto_now=True, db_comment="Updated At")
    updated_by = models.CharField(
        max_length=255, blank=True, null=True, db_comment="Updated By"
    )

    class Meta:
        managed = False
        db_table = "timesheet_uploads"

    def __str__(self):
        return f"{self.timesheet_id} - {self.emp_name}"


class EmployeeAllowance(models.Model):
    pk = models.CompositePrimaryKey("emp_id", "allow_id")
    emp_id = models.ForeignKey(
        "Employee", models.DO_NOTHING, db_column="emp_id", db_comment="Employee ID"
    )
    allow = models.ForeignKey(
        "AllowanceType", models.DO_NOTHING, db_comment="Allowance ID"
    )
    date_start = models.DateField(db_comment="Date started")
    active = models.CharField(max_length=1, db_comment=" Y = Yes,\r\n N = No ")
    amount = models.FloatField(db_comment="Allowance amount")
    sched = models.CharField(
        max_length=1,
        db_comment=" E = Every Payroll\r\n 1 = 15th Payroll\r\n3 = 30th Payroll",
    )
    taxable = models.CharField(
        max_length=1, blank=True, null=True, db_comment=" Y = Yes,\r\n N = No "
    )
    notes = models.CharField(
        max_length=255, blank=True, null=True, db_comment="remarks"
    )

    class Meta:
        managed = False
        db_table = "employee_allowance"

    def __str__(self):
        return f"{self.pk}"


class AllowanceType(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    description = models.CharField(max_length=100)
    active = models.CharField(max_length=1, db_comment=" Y = Yes,\r\n N = No")

    class Meta:
        managed = False
        db_table = "allowance_type"

    def __str__(self):
        return f"{self.id}"


class TimesheetOvertime(models.Model):
    emp_id = models.ForeignKey(
        "Employee", models.DO_NOTHING, db_column="emp_id", db_comment="Employee ID"
    )
    tran_date = models.DateField()
    ot_code = models.CharField(max_length=20)
    ot_hours = models.FloatField()

    class Meta:
        managed = False
        db_table = "timesheet_overtime"
        unique_together = (("emp_id", "tran_date", "ot_code"),)

    def __str__(self):
        return f"{self.emp_id} - {self.tran_date} - {self.ot_code}"


class OtMultiplier(models.Model):
    code = models.CharField(primary_key=True, max_length=20)
    sort_order = models.IntegerField(blank=True, null=True)
    description = models.CharField(max_length=255)
    daily_percent = models.FloatField()
    fixed_percent = models.FloatField()
    remarks = models.CharField(max_length=255, blank=True, null=True)
    group_code = models.CharField(max_length=3, blank=True, null=True)
    is_regular = models.CharField(max_length=1, blank=True, null=True)
    is_nd = models.CharField(max_length=1, blank=True, null=True)
    is_ot = models.CharField(max_length=1, blank=True, null=True)
    is_holiday = models.CharField(max_length=1, blank=True, null=True)
    is_rest_day = models.CharField(max_length=1, blank=True, null=True)
    hol_type = models.CharField(max_length=3, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "ot_multiplier"

    def __str__(self):
        return f"{self.code}"


class LoanType(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    description = models.CharField(max_length=100)
    active = models.CharField(max_length=1, db_comment=" Y = Yes,\r\n N = No")

    class Meta:
        managed = False
        db_table = "loan_type"

    def __str__(self):
        return f"{self.pk}"


class EmployeeLoans(models.Model):
    pk = models.CompositePrimaryKey("emp_id", "loan_id", "loan_date")
    emp_id = models.ForeignKey(
        "Employee", models.DO_NOTHING, db_column="emp_id", db_comment="Employee ID"
    )
    loan = models.ForeignKey("LoanType", models.DO_NOTHING, db_comment="Loan ID")
    loan_date = models.DateField()
    date_start = models.DateField(db_comment="Date started")
    sched = models.CharField(
        max_length=1,
        db_comment=" E = Every Payroll\r\n1 = Every 15th Payroll\r\n3 = Every End of month Payroll",
    )
    loan_amount = models.FloatField(db_comment="Loan amount")
    interest_amount = models.FloatField(db_comment="Interest amount")
    amount = models.FloatField(db_comment="Total payable amount")
    ded_amount = models.FloatField(db_comment="Deduction Amount")
    paid_amount = models.FloatField(db_comment="Amount paid")
    balance_amount = models.FloatField(db_comment="Balance Amount")
    notes = models.CharField(
        max_length=255, blank=True, null=True, db_comment="remarks"
    )
    onhold = models.CharField(max_length=1, db_comment=" Y = Yes,\r\n N = No ")

    class Meta:
        managed = False
        db_table = "employee_loans"

    def __str__(self):
        return f"{self.pk}"


class OtherDedType(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    description = models.CharField(max_length=100)
    active = models.CharField(max_length=1, db_comment=" Y = Yes,\r\n N = No")

    class Meta:
        managed = False
        db_table = "other_ded_type"

    def __str__(self):
        return f"{self.pk}"


class InOutRecord(models.Model):
    """Model for lp_inout table storing biometric attendance data"""

    biometric_id = models.IntegerField(db_comment="Biometric ID")
    tran_date = models.DateField(db_comment="Transaction Date")
    tran_time = models.TimeField(db_comment="Transaction Time")

    class Meta:
        managed = False
        db_table = "lp_inout"
        unique_together = (("biometric_id", "tran_date", "tran_time"),)

    def __str__(self):
        return f"{self.biometric_id} - {self.tran_date} {self.tran_time}"


class EmployeeOtherDed(models.Model):
    emp_id = models.ForeignKey(
        "Employee",
        models.DO_NOTHING,
        primary_key=True,
        db_column="emp_id",
        db_comment="Employee ID",
    )
    ded = models.ForeignKey(
        "OtherDedType", models.DO_NOTHING, db_comment="Deduction ID"
    )
    ded_date = models.DateField()
    date_start = models.DateField(db_comment="Date started")
    sched = models.CharField(
        max_length=1,
        db_comment=" E = Every Payroll\r\n1 = Every 15th Payroll\r\n3 = Every End of month Payroll",
    )
    amount = models.FloatField(db_comment="Total payable amount")
    ded_amount = models.FloatField(db_comment="Deduction Amount")
    paid_amount = models.FloatField(db_comment="Amount paid")
    balance_amount = models.FloatField(db_comment="Balance Amount")
    notes = models.CharField(
        max_length=255, blank=True, null=True, db_comment="remarks"
    )
    onhold = models.CharField(max_length=1, db_comment=" Y = Yes,\r\n N = No ")

    class Meta:
        managed = False
        db_table = "employee_other_ded"

    def __str__(self):
        return f"{self.pk}"


class ThirteenThMonthHead(models.Model):
    comp_id = models.CharField(
        max_length=3, db_collation="latin1_swedish_ci", db_comment="Company ID"
    )
    payroll_type = models.CharField(
        max_length=1,
        db_collation="latin1_swedish_ci",
        db_comment=" R = Regular Payroll, \r\n P = Production Payroll",
    )
    year = models.IntegerField()
    trantype = models.CharField(max_length=3, db_comment="1ST , 2ND")
    generated_date = models.DateTimeField()
    generated_by = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=1, db_comment="O=Open, A=Approved")
    approved_date = models.DateTimeField(blank=True, null=True)
    approved_by = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = "13th_month_head"

    def __str__(self):
        return f"{self.pk}"


class ThirteenThMonthData(models.Model):
    pk = models.CompositePrimaryKey("head_id", "emp_id")
    head = models.ForeignKey("ThirteenThMonthHead", models.DO_NOTHING)
    emp_id = models.ForeignKey(
        "Employee", models.DO_NOTHING, db_column="emp_id", db_comment="Employee ID"
    )
    last_name = models.CharField(
        max_length=50, db_collation="latin1_swedish_ci", db_comment="Last Name"
    )
    first_name = models.CharField(
        max_length=50, db_collation="latin1_swedish_ci", db_comment="First Name"
    )
    middle_name = models.CharField(
        max_length=50,
        db_collation="latin1_swedish_ci",
        blank=True,
        null=True,
        db_comment="Middle Name",
    )
    alias_name = models.CharField(
        max_length=100,
        db_collation="latin1_swedish_ci",
        blank=True,
        null=True,
        db_comment="Alias Name",
    )
    suffix = models.CharField(
        max_length=10,
        db_collation="latin1_swedish_ci",
        blank=True,
        null=True,
        db_comment="Name Suffix",
    )
    dept_id = models.CharField(max_length=50, db_comment="Department ID")
    position = models.CharField(
        max_length=255,
        db_collation="latin1_swedish_ci",
        blank=True,
        null=True,
        db_comment="Position in company",
    )
    emp_status = models.CharField(
        max_length=1,
        db_collation="latin1_swedish_ci",
        db_comment=" C = Contractual, \r\n P = Probationary, \r\n R = Regular, \r\n X = Resigned, \r\n T = Terminated, \r\n A = AWOL\r\n E = End of Service",
    )
    sal_type = models.CharField(
        max_length=10,
        db_collation="latin1_swedish_ci",
        db_comment=" D = Daily Earner,\r\n F = Fixed Earner,\r\n P = Production Output",
    )
    bank_id = models.CharField(max_length=50, db_comment="Bank ID")
    region_id = models.CharField(max_length=30, blank=True, null=True)
    account_no = models.CharField(max_length=50, blank=True, null=True)
    m1_1_basic = models.FloatField()
    m1_1_vlslallow = models.FloatField()
    m1_1_adj = models.FloatField()
    m1_1_abs = models.FloatField()
    m1_1_total = models.FloatField()
    m1_2_basic = models.FloatField()
    m1_2_vlslallow = models.FloatField()
    m1_2_adj = models.FloatField()
    m1_2_abs = models.FloatField()
    m1_2_total = models.FloatField()
    m2_1_basic = models.FloatField()
    m2_1_vlslallow = models.FloatField()
    m2_1_adj = models.FloatField()
    m2_1_abs = models.FloatField()
    m2_1_total = models.FloatField()
    m2_2_basic = models.FloatField()
    m2_2_vlslallow = models.FloatField()
    m2_2_adj = models.FloatField()
    m2_2_abs = models.FloatField()
    m2_2_total = models.FloatField()
    m3_1_basic = models.FloatField()
    m3_1_vlslallow = models.FloatField()
    m3_1_adj = models.FloatField()
    m3_1_abs = models.FloatField()
    m3_1_total = models.FloatField()
    m3_2_basic = models.FloatField()
    m3_2_vlslallow = models.FloatField()
    m3_2_adj = models.FloatField()
    m3_2_abs = models.FloatField()
    m3_2_total = models.FloatField()
    m4_1_basic = models.FloatField()
    m4_1_vlslallow = models.FloatField()
    m4_1_adj = models.FloatField()
    m4_1_abs = models.FloatField()
    m4_1_total = models.FloatField()
    m4_2_basic = models.FloatField()
    m4_2_vlslallow = models.FloatField()
    m4_2_adj = models.FloatField()
    m4_2_abs = models.FloatField()
    m4_2_total = models.FloatField()
    m5_1_basic = models.FloatField()
    m5_1_vlslallow = models.FloatField()
    m5_1_adj = models.FloatField()
    m5_1_abs = models.FloatField()
    m5_1_total = models.FloatField()
    m5_2_basic = models.FloatField()
    m5_2_vlslallow = models.FloatField()
    m5_2_adj = models.FloatField()
    m5_2_abs = models.FloatField()
    m5_2_total = models.FloatField()
    m6_1_basic = models.FloatField()
    m6_1_vlslallow = models.FloatField()
    m6_1_adj = models.FloatField()
    m6_1_abs = models.FloatField()
    m6_1_total = models.FloatField()
    m6_2_basic = models.FloatField()
    m6_2_vlslallow = models.FloatField()
    m6_2_adj = models.FloatField()
    m6_2_abs = models.FloatField()
    m6_2_total = models.FloatField()
    total_generated = models.FloatField()
    addt_amount = models.FloatField()
    grand_total = models.FloatField()
    amount_13th = models.FloatField()

    class Meta:
        managed = False
        db_table = "13th_month_data"

    def __str__(self):
        return f"{self.pk}"


class EmployeeLeave(models.Model):
    pk = models.CompositePrimaryKey("emp_id", "leave_id")
    emp_id = models.ForeignKey(
        "Employee", models.DO_NOTHING, db_column="emp_id", db_comment="Employee ID"
    )
    leave = models.ForeignKey("LeaveType", models.DO_NOTHING, db_comment="Leave ID")
    year = models.CharField(max_length=4)
    assigned_hrs = models.FloatField(
        blank=True, null=True, db_comment="Assigned hours per year"
    )
    used_hrs = models.FloatField(blank=True, null=True, db_comment="Used hours")
    total_days = models.FloatField(db_comment="Number of hours allowed per year")
    notes = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    created_by = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(
        blank=True, null=True, db_comment="will only be updated on maintenance"
    )
    updated_by = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_comment="will only be updated on maintenance",
    )

    class Meta:
        managed = False
        db_table = "employee_leave"

    def __str__(self):
        return f"{self.pk}"


class LeaveType(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    description = models.CharField(max_length=100)
    active = models.CharField(max_length=1, db_comment=" Y = Yes,\r\n N = No")
    cash_converted = models.CharField(max_length=1, db_comment=" Y = Yes,\r\n N = No")

    class Meta:
        managed = False
        db_table = "leave_type"

    def __str__(self):
        return f"{self.pk}"


class LeaveRequest(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    emp_id = models.CharField(max_length=11)
    leave_id = models.CharField(max_length=10)
    sched_date = models.DateField()
    is_half_day = models.CharField(max_length=1, default="N")
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    approved_hrs = models.FloatField(null=True, blank=True)
    with_pay = models.CharField(max_length=1, default="Y")
    status = models.CharField(
        max_length=2,
        default="FA",
        db_comment="FA = FOR APPROVAL, AP = APPROVED, DA = DISAPPROVED, CN = CANCELLED, OK = DONE/OK/APPLIED, XP = EXPIRED",
    )
    remarks = models.CharField(max_length=255, blank=True, null=True)
    payroll_id = models.CharField(max_length=15, blank=True, null=True)
    approver_id = models.CharField(max_length=11, blank=True, null=True)
    approver_remarks = models.CharField(max_length=255, blank=True, null=True)
    system_remarks = models.CharField(max_length=255, blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "leave_request"

    def __str__(self):
        return f"{self.id} - {self.emp_id} - {self.sched_date}"


class OtRequestApplied(models.Model):
    id = models.CharField(primary_key=True, max_length=36)
    req_id = models.CharField(max_length=36)
    ot_code = models.CharField(max_length=20)
    applied_hrs = models.FloatField()

    class Meta:
        managed = False
        db_table = "ot_request_applied"

    def __str__(self):
        return f"{self.id} - {self.req_id} - {self.ot_code}"


class OtRequest(models.Model):
    id = models.CharField(primary_key=True, max_length=36)
    emp_id = models.CharField(max_length=15)
    sched_date = models.DateField()
    time_in = models.TimeField()
    time_out = models.DateTimeField()
    next_day_out = models.CharField(max_length=1, default="N")
    hrs_req = models.FloatField()
    apprv_hrs = models.FloatField(null=True, blank=True)
    applied_hrs = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=2,
        default="FA",
        db_comment="FA = FOR APPROVAL, AP = APPROVED, DA = DISAPPROVED, CN = CANCELLED, OK = DONE/OK/APPLIED, XP = EXPIRED",
    )
    remarks = models.CharField(max_length=255, blank=True, null=True)
    payroll_id = models.CharField(max_length=15, blank=True, null=True)
    approver_id = models.CharField(max_length=255, blank=True, null=True)
    approver_remarks = models.CharField(max_length=255, blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "ot_request"

    def __str__(self):
        return f"{self.id} - {self.emp_id} - {self.sched_date}"


class OBRequest(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    emp_id = models.ForeignKey("Employee", models.DO_NOTHING, db_column="emp_id")
    sched_date = models.DateField()
    time_in = models.TimeField()
    time_out = models.DateTimeField()
    next_day_out = models.CharField(max_length=1, default="N")
    remarks = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(
        max_length=2,
        default="FA",
        db_comment="FA = FOR APPROVAL, AP = APPROVED, DA = DISAPPROVED, CN = CANCELLED, OK = DONE/OK/APPLIED, XP = EXPIRED",
    )
    payroll_id = models.CharField(max_length=15, blank=True, null=True)
    approver_id = models.CharField(max_length=15, blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    approver_remarks = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "ob_request"

    def __str__(self):
        return f"{self.id} - {self.emp_id} - {self.sched_date}"

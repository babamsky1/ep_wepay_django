from .last_pay_record_views import (
    last_pay_records_list,
    last_pay_records_detail,
    last_pay_records_edit,
    last_pay_records_delete,
)
from .employee_views import (
    employees_list,
    employee_create,
    employee_update,
    employee_delete,
)
from .general_logs_views import (
    general_logs_list,
)
from .additionals_type_views import (
    additionals_type_list,
    additionals_type_create,
    additionals_type_edit,
    additionals_type_delete,
)
from .loan_detail_views import (
    loan_detail_list,
)
from .leave_monthly_detail_views import (
    leave_monthly_detail_list,
)
from .month13_salary_detail_views import (
    month13_salary_detail_list,
)
from .overtime_detail_views import (
    overtime_detail_list,
)
from .allowance_table_views import (
    allowance_table_list,
)
from .quit_claim_actions_views import (
    quit_claim_update_status,
    quit_claim_reopen,
)
from .auth_views import login_view

__all__ = [
    # Authentication
    "login_view",
    # Employees
    "employees_list",
    "employee_create",
    "employee_update",
    "employee_delete",
    "general_logs_list",
    # Last Pay Records
    "last_pay_records_list",
    "last_pay_records_detail",
    "last_pay_records_edit",
    "last_pay_records_delete",
    # Additionals Type
    "additionals_type_list",
    "additionals_type_create",
    "additionals_type_edit",
    "additionals_type_delete",
    # Loan Details
    "loan_detail_list",
    # Leave Monthly Details
    "leave_monthly_detail_list",
    # Month13 Salary Details
    "month13_salary_detail_list",
    # Overtime Details
    "overtime_detail_list",
    # Allowance Table
    "allowance_table_list",
    # Quit Claim Actions
    "quit_claim_update_status",
    "quit_claim_reopen",
]

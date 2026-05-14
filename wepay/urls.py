from django.urls import path
from . import views
from .views.generate_last_pay import generate__last_pay
from .views import timesheet_upload_views

urlpatterns = [
    # Authentication
    path("auth/login/", views.login_view, name="login"),

    # Employees
    path("employees/", views.employees_list, name="employees_list"),
    path("employees/create/", views.employee_create, name="employee_create"),
    path("employees/edit/", views.employee_update, name="employee_update"),
    path("employees/delete/", views.employee_delete, name="employee_delete"),

    # General Logs
    path("general-logs/", views.general_logs_list, name="general_logs_list"),

    # Last Pay Records
    path(
        "last-pay-records/", views.last_pay_records_list, name="last_pay_records_list"
    ),
    path(
        "last-pay-records/edit/",
        views.last_pay_records_edit,
        name="last_pay_records_edit",
    ),
    path(
        "last-pay-records/delete/",
        views.last_pay_records_delete,
        name="last_pay_records_delete",
    ),
    path(
        "last-pay-records/<str:ref_no>/",
        views.last_pay_records_detail,
        name="last_pay_records_detail",
    ),
    # Additionals Type
    path(
        "additionals-type/", views.additionals_type_list, name="additionals_type_list"
    ),
    path(
        "additionals-type/create/",
        views.additionals_type_create,
        name="additionals_type_create",
    ),
    path(
        "additionals-type/edit/",
        views.additionals_type_edit,
        name="additionals_type_edit",
    ),
    path(
        "additionals-type/delete/",
        views.additionals_type_delete,
        name="additionals_type_delete",
    ),
    # Loan Details
    path("loan-details/", views.loan_detail_list, name="loan_detail_list"),
    # Leave Monthly Details
    path(
        "leave-monthly-details/",
        views.leave_monthly_detail_list,
        name="leave_monthly_detail_list",
    ),
    # Month13 Salary Details
    path(
        "month13-salary-details/",
        views.month13_salary_detail_list,
        name="month13_salary_detail_list",
    ),
    # Overtime Details
    path("overtime-details/", views.overtime_detail_list,
         name="overtime_detail_list"),
    # Allowance Table
    path("allowances/", views.allowance_table_list, name="allowance_table_list"),
    # Last Pay Generation
    path("generate-last-pay/", generate__last_pay, name="generate_last_pay"),

    # Timesheet Upload
    path("timesheet/upload/", timesheet_upload_views.upload_timesheet, name="upload_timesheet"),
    path("timesheet/records/", timesheet_upload_views.get_timesheet_records, name="get_timesheet_records"),
    path("timesheet/delete/<str:emp_id>/", timesheet_upload_views.delete_timesheet, name="delete_timesheet"),

    # Quit Claim Actions
    path(
        "quit-claim/update-status/",
        views.quit_claim_update_status,
        name="quit_claim_update_status",
    ),
    path(
        "quit-claim/reopen/",
        views.quit_claim_reopen,
        name="quit_claim_reopen",
    ),
]

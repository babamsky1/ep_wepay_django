from django.contrib import admin
from .models import (
    LastPayRecord, AdditionalsType, LoanDetail, 
    LeaveMonthlyDetail, Month13SalaryDetail, 
    OvertimeDetail, AllowanceTable
)

admin.site.register(LastPayRecord)
admin.site.register(AdditionalsType)
admin.site.register(LoanDetail)
admin.site.register(LeaveMonthlyDetail)
admin.site.register(Month13SalaryDetail)
admin.site.register(OvertimeDetail)
admin.site.register(AllowanceTable)
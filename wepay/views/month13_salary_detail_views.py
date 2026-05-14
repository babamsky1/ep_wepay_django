from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..models import Month13SalaryDetail
from ..serializers import Month13SalaryDetailSerializer


@api_view(["GET"])
def month13_salary_detail_list(request):
    salaries = Month13SalaryDetail.objects.all()
    serializer = Month13SalaryDetailSerializer(salaries, many=True)

    return Response(
        {"result": "success", "data": serializer.data, "message": "OK"},
        status=status.HTTP_200_OK,
    )

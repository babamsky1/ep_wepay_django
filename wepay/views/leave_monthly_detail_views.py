from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..models import LeaveMonthlyDetail
from ..serializers import LeaveMonthlyDetailSerializer


@api_view(["GET"])
def leave_monthly_detail_list(request):
    leaves = LeaveMonthlyDetail.objects.all()
    serializer = LeaveMonthlyDetailSerializer(leaves, many=True)

    return Response(
        {"result": "success", "data": serializer.data, "message": "OK"},
        status=status.HTTP_200_OK,
    )

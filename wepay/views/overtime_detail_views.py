from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..models import OvertimeDetail
from ..serializers import OvertimeDetailSerializer


@api_view(["GET"])
def overtime_detail_list(request):
    overtimes = OvertimeDetail.objects.all()
    serializer = OvertimeDetailSerializer(overtimes, many=True)

    return Response(
        {"result": "success", "data": serializer.data, "message": "OK"},
        status=status.HTTP_200_OK,
    )

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..models import AllowanceTable
from ..serializers import AllowanceTableSerializer


@api_view(["GET"])
def allowance_table_list(request):
    allowances = AllowanceTable.objects.all()
    serializer = AllowanceTableSerializer(allowances, many=True)

    return Response(
        {"result": "success", "data": serializer.data, "message": "OK"},
        status=status.HTTP_200_OK,
    )

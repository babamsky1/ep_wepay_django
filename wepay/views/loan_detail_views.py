from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..models import LoanDetail
from ..serializers import LoanDetailSerializer


@api_view(["GET"])
def loan_detail_list(request):
    loans = LoanDetail.objects.all()
    serializer = LoanDetailSerializer(loans, many=True)
    return Response(
        {"result": "success", "data": serializer.data, "message": "OK"},
        status=status.HTTP_200_OK,
    )

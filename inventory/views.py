from django.db.models.deletion import ProtectedError
from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import Branch, Copy
from .serializers import (
    BranchSerializer,
    CopyFilterSerializer,
    CopySerializer,
)


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "code": "branch_has_copies",
                    "message": ("Нельзя удалить филиал, пока в нём есть экземпляры."),
                },
                status=status.HTTP_409_CONFLICT,
            )


class CopyViewSet(viewsets.ModelViewSet):
    queryset = Copy.objects.all()
    serializer_class = CopySerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action != "list":
            return queryset

        filters = CopyFilterSerializer(data=self.request.query_params.dict())
        filters.is_valid(raise_exception=True)

        return queryset.filter(**filters.validated_data)

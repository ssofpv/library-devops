from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import Author
from .serializers import AuthorSerializer


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

    def destroy(self, request, *args, **kwargs):
        author = self.get_object()

        if author.books.exists():
            return Response(
                {
                    "code": "author_has_books",
                    "message": "Нельзя удалить автора, связанного с книгами.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        return super().destroy(request, *args, **kwargs)

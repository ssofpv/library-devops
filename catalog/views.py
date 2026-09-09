from django.db.models.deletion import ProtectedError
from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import Author, Book
from .serializers import AuthorSerializer, BookSerializer


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


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.prefetch_related("authors").all()
    serializer_class = BookSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "code": "book_has_related_records",
                    "message": (
                        "Нельзя удалить книгу, пока существуют "
                        "связанные записи, защищающие её от удаления."
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )

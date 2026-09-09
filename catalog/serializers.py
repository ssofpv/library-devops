from rest_framework import serializers

from .models import Author, Book


class AuthorSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(
        max_length=200,
        allow_blank=False,
        trim_whitespace=True,
    )

    class Meta:
        model = Author
        fields = ["id", "full_name"]
        read_only_fields = ["id"]


class BookSerializer(serializers.ModelSerializer):
    title = serializers.CharField(
        max_length=300,
        allow_blank=False,
        trim_whitespace=True,
    )
    publication_year = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=32767,
    )
    author_ids = serializers.PrimaryKeyRelatedField(
        source="authors",
        queryset=Author.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = Book
        fields = ["id", "title", "publication_year", "author_ids"]
        read_only_fields = ["id"]

    def validate_author_ids(self, authors):
        ids = [author.pk for author in authors]

        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Идентификаторы авторов не должны повторяться.")

        return authors

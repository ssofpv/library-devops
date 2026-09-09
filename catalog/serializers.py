from rest_framework import serializers

from .models import Author


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

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from catalog.models import Book

from .models import Branch, Copy


class BranchSerializer(serializers.ModelSerializer):
    name = serializers.CharField(
        max_length=200,
        allow_blank=False,
        trim_whitespace=True,
    )
    address = serializers.CharField(
        max_length=500,
        allow_blank=False,
        trim_whitespace=True,
    )

    class Meta:
        model = Branch
        fields = ["id", "name", "address"]
        read_only_fields = ["id"]


class CopySerializer(serializers.ModelSerializer):
    inventory_number = serializers.CharField(
        max_length=100,
        allow_blank=False,
        trim_whitespace=True,
        validators=[
            UniqueValidator(
                queryset=Copy.objects.all(),
                message="Экземпляр с таким инвентарным номером уже существует.",
            ),
        ],
    )
    book_id = serializers.PrimaryKeyRelatedField(
        source="book",
        queryset=Book.objects.all(),
    )
    branch_id = serializers.PrimaryKeyRelatedField(
        source="branch",
        queryset=Branch.objects.all(),
    )

    class Meta:
        model = Copy
        fields = ["id", "inventory_number", "book_id", "branch_id"]
        read_only_fields = ["id"]


class CopyFilterSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=9223372036854775807,
    )
    branch_id = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=9223372036854775807,
    )

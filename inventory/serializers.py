from rest_framework import serializers

from .models import Branch


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

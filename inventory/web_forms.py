from django import forms

from catalog.models import Book

from .models import Branch, Copy


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ["name", "address"]


class CopyForm(forms.ModelForm):
    class Meta:
        model = Copy
        fields = ["inventory_number", "book", "branch"]
        error_messages = {
            "inventory_number": {"unique": "Экземпляр с таким инвентарным номером уже существует."},
        }


class CopyFilterForm(forms.Form):
    book = forms.ModelChoiceField(
        label="Книга",
        queryset=Book.objects.all(),
        required=False,
        empty_label="Все книги",
    )
    branch = forms.ModelChoiceField(
        label="Филиал",
        queryset=Branch.objects.all(),
        required=False,
        empty_label="Все филиалы",
    )

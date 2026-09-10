from django import forms

from .models import Author, Book


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ["full_name"]


class BookForm(forms.ModelForm):
    publication_year = forms.IntegerField(
        label="Год издания",
        required=False,
        min_value=1,
        max_value=32767,
        help_text="Оставьте пустым, если год неизвестен.",
    )
    authors = forms.ModelMultipleChoiceField(
        label="Авторы",
        queryset=Author.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Можно выбрать несколько авторов или оставить книгу без автора.",
    )

    class Meta:
        model = Book
        fields = ["title", "publication_year", "authors"]

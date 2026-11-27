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
        fields = ["title", "description", "publication_year", "authors"]


class BookYearFilterForm(forms.Form):
    year = forms.TypedChoiceField(
        label="Год издания",
        required=False,
        coerce=int,
        empty_value=None,
        error_messages={"invalid_choice": "Выберите год из списка."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        years = (
            Book.objects.exclude(publication_year__isnull=True)
            .order_by("-publication_year")
            .values_list("publication_year", flat=True)
            .distinct()
        )
        self.fields["year"].choices = [("", "Все годы")] + [(year, str(year)) for year in years]

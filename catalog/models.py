from django.core.validators import MinValueValidator
from django.db import models


class Author(models.Model):
    full_name = models.CharField(
        max_length=200,
        verbose_name="Имя автора",
    )

    class Meta:
        ordering = ["full_name", "id"]
        verbose_name = "Автор"
        verbose_name_plural = "Авторы"

    def __str__(self):
        return self.full_name


class Book(models.Model):
    title = models.CharField(
        max_length=300,
        verbose_name="Название",
    )
    publication_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name="Год издания",
    )
    authors = models.ManyToManyField(
        Author,
        related_name="books",
        blank=True,
        verbose_name="Авторы",
    )

    class Meta:
        ordering = ["title", "id"]
        verbose_name = "Книга"
        verbose_name_plural = "Книги"

    def __str__(self):
        return self.title

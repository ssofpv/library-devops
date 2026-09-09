from django.test import TestCase

from .models import Author, Book


class CatalogModelTests(TestCase):
    def test_book_is_saved_with_authors(self):
        first_author = Author.objects.create(full_name="Илья Ильф")
        second_author = Author.objects.create(full_name="Евгений Петров")

        book = Book.objects.create(
            title="Двенадцать стульев",
            publication_year=1928,
        )
        book.authors.add(first_author, second_author)

        saved_book = Book.objects.get(pk=book.pk)

        self.assertEqual(saved_book.title, "Двенадцать стульев")
        self.assertEqual(saved_book.publication_year, 1928)
        self.assertSetEqual(
            set(saved_book.authors.values_list("id", flat=True)),
            {first_author.id, second_author.id},
        )

    def test_author_can_have_multiple_books(self):
        author = Author.objects.create(full_name="Александр Пушкин")
        first_book = Book.objects.create(title="Капитанская дочка")
        second_book = Book.objects.create(title="Евгений Онегин")

        first_book.authors.add(author)
        second_book.authors.add(author)

        self.assertSetEqual(
            set(author.books.values_list("id", flat=True)),
            {first_book.id, second_book.id},
        )

    def test_adding_same_author_does_not_duplicate_relationship(self):
        author = Author.objects.create(full_name="Михаил Булгаков")
        book = Book.objects.create(title="Мастер и Маргарита")

        book.authors.add(author)
        book.authors.add(author)

        self.assertEqual(book.authors.count(), 1)

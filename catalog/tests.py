from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

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


class AuthorAPITests(APITestCase):
    def test_create_author(self):
        response = self.client.post(
            reverse("author-list"),
            {"full_name": "  Михаил Булгаков  "},
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        author = Author.objects.get(pk=response.data["id"])
        self.assertEqual(author.full_name, "Михаил Булгаков")

    def test_invalid_names_are_rejected(self):
        invalid_data = [
            {},
            {"full_name": ""},
            {"full_name": "   "},
            {"full_name": "А" * 201},
        ]

        for data in invalid_data:
            with self.subTest(data=data):
                response = self.client.post(
                    reverse("author-list"),
                    data,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("full_name", response.data)

        self.assertEqual(Author.objects.count(), 0)

    def test_list_authors(self):
        author = Author.objects.create(full_name="Михаил Булгаков")

        response = self.client.get(reverse("author-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [{"id": author.id, "full_name": "Михаил Булгаков"}],
        )

    def test_get_author(self):
        author = Author.objects.create(full_name="Михаил Булгаков")

        response = self.client.get(reverse("author-detail", args=[author.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["full_name"], author.full_name)

    def test_update_author(self):
        author = Author.objects.create(full_name="Булгаков")

        response = self.client.patch(
            reverse("author-detail", args=[author.id]),
            {"full_name": "Михаил Булгаков"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        author.refresh_from_db()
        self.assertEqual(author.full_name, "Михаил Булгаков")

    def test_delete_author_without_books(self):
        author = Author.objects.create(full_name="Михаил Булгаков")

        response = self.client.delete(reverse("author-detail", args=[author.id]))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Author.objects.filter(pk=author.id).exists())

    def test_cannot_delete_author_with_books(self):
        author = Author.objects.create(full_name="Михаил Булгаков")
        book = Book.objects.create(title="Мастер и Маргарита")
        book.authors.add(author)

        response = self.client.delete(reverse("author-detail", args=[author.id]))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "author_has_books")
        self.assertTrue(Author.objects.filter(pk=author.id).exists())
        self.assertTrue(Book.objects.filter(pk=book.id).exists())
        self.assertTrue(book.authors.filter(pk=author.id).exists())

    def test_missing_author_returns_404(self):
        response = self.client.get(reverse("author-detail", args=[99999]))

        self.assertEqual(response.status_code, 404)

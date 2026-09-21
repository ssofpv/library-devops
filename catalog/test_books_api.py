from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Author, Book


class BookAPITests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="librarian")
        self.client.force_login(self.user)

    def test_create_book_with_authors(self):
        first_author = Author.objects.create(full_name="Илья Ильф")
        second_author = Author.objects.create(full_name="Евгений Петров")

        response = self.client.post(
            reverse("book-list"),
            {
                "title": "  Двенадцать стульев  ",
                "publication_year": 1928,
                "author_ids": [first_author.id, second_author.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        book = Book.objects.get(pk=response.data["id"])
        self.assertEqual(book.title, "Двенадцать стульев")
        self.assertEqual(book.publication_year, 1928)
        self.assertSetEqual(
            set(book.authors.values_list("id", flat=True)),
            {first_author.id, second_author.id},
        )

    def test_create_book_without_optional_fields(self):
        response = self.client.post(
            reverse("book-list"),
            {"title": "Книга без указания автора"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        book = Book.objects.get(pk=response.data["id"])
        self.assertIsNone(book.publication_year)
        self.assertEqual(book.authors.count(), 0)

    def test_invalid_data_is_rejected(self):
        cases = [
            ({}, "title"),
            ({"title": ""}, "title"),
            ({"title": "   "}, "title"),
            ({"title": "А" * 301}, "title"),
            (
                {"title": "Книга", "publication_year": 0},
                "publication_year",
            ),
            (
                {"title": "Книга", "publication_year": 32768},
                "publication_year",
            ),
            (
                {"title": "Книга", "publication_year": "не год"},
                "publication_year",
            ),
            (
                {"title": "Книга", "author_ids": [99999]},
                "author_ids",
            ),
        ]

        for data, field in cases:
            with self.subTest(data=data):
                response = self.client.post(
                    reverse("book-list"),
                    data,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

        self.assertEqual(Book.objects.count(), 0)

    def test_duplicate_authors_are_rejected(self):
        author = Author.objects.create(full_name="Михаил Булгаков")

        response = self.client.post(
            reverse("book-list"),
            {
                "title": "Мастер и Маргарита",
                "author_ids": [author.id, author.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("author_ids", response.data)
        self.assertEqual(Book.objects.count(), 0)

    def test_list_books(self):
        author = Author.objects.create(full_name="Михаил Булгаков")
        book = Book.objects.create(
            title="Мастер и Маргарита",
            publication_year=1967,
        )
        book.authors.add(author)

        response = self.client.get(reverse("book-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": book.id,
                    "title": "Мастер и Маргарита",
                    "publication_year": 1967,
                    "author_ids": [author.id],
                }
            ],
        )

    def test_get_book(self):
        book = Book.objects.create(title="Капитанская дочка")

        response = self.client.get(reverse("book-detail", args=[book.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], book.id)
        self.assertEqual(response.data["title"], "Капитанская дочка")

    def test_update_book_and_replace_authors(self):
        first_author = Author.objects.create(full_name="Первый автор")
        second_author = Author.objects.create(full_name="Второй автор")
        book = Book.objects.create(title="Первое название")
        book.authors.add(first_author)

        response = self.client.patch(
            reverse("book-detail", args=[book.id]),
            {
                "title": "Новое название",
                "publication_year": 2020,
                "author_ids": [second_author.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        book.refresh_from_db()
        self.assertEqual(book.title, "Новое название")
        self.assertEqual(book.publication_year, 2020)
        self.assertSetEqual(
            set(book.authors.values_list("id", flat=True)),
            {second_author.id},
        )

    def test_patch_title_preserves_authors(self):
        author = Author.objects.create(full_name="Михаил Булгаков")
        book = Book.objects.create(title="Черновое название")
        book.authors.add(author)

        response = self.client.patch(
            reverse("book-detail", args=[book.id]),
            {"title": "Мастер и Маргарита"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        book.refresh_from_db()
        self.assertEqual(book.title, "Мастер и Маргарита")
        self.assertTrue(book.authors.filter(pk=author.id).exists())

    def test_clear_optional_fields(self):
        author = Author.objects.create(full_name="Автор")
        book = Book.objects.create(
            title="Книга",
            publication_year=2020,
        )
        book.authors.add(author)

        response = self.client.patch(
            reverse("book-detail", args=[book.id]),
            {"publication_year": None, "author_ids": []},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        book.refresh_from_db()
        self.assertIsNone(book.publication_year)
        self.assertEqual(book.authors.count(), 0)

    def test_invalid_update_preserves_book_and_authors(self):
        author = Author.objects.create(full_name="Автор")
        book = Book.objects.create(title="Исходное название")
        book.authors.add(author)

        response = self.client.patch(
            reverse("book-detail", args=[book.id]),
            {
                "title": "Другое название",
                "author_ids": [99999],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        book.refresh_from_db()
        self.assertEqual(book.title, "Исходное название")
        self.assertTrue(book.authors.filter(pk=author.id).exists())

    def test_delete_book_preserves_author(self):
        author = Author.objects.create(full_name="Михаил Булгаков")
        book = Book.objects.create(title="Мастер и Маргарита")
        book.authors.add(author)

        response = self.client.delete(reverse("book-detail", args=[book.id]))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Book.objects.filter(pk=book.id).exists())
        self.assertTrue(Author.objects.filter(pk=author.id).exists())
        self.assertEqual(author.books.count(), 0)

    def test_missing_book_returns_404(self):
        response = self.client.get(reverse("book-detail", args=[99999]))

        self.assertEqual(response.status_code, 404)

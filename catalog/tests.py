from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.response import Response
from rest_framework.test import APITestCase

from .models import Author, Book
from .views import AuthorViewSet


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
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="librarian")
        self.client.force_login(self.user)

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


class BookDescriptionMigrationTests(TransactionTestCase):
    def test_existing_book_and_authors_survive_migration(self):
        old_target = [("catalog", "0001_initial")]
        new_target = [("catalog", "0002_book_description")]

        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()

        def restore_schema():
            MigrationExecutor(connection).migrate(latest_targets)

        self.addCleanup(restore_schema)
        executor.migrate(old_target)

        old_apps = executor.loader.project_state(old_target).apps
        OldAuthor = old_apps.get_model("catalog", "Author")
        OldBook = old_apps.get_model("catalog", "Book")

        author = OldAuthor.objects.create(full_name="Автор до миграции")
        book = OldBook.objects.create(
            title="Книга до миграции",
            publication_year=2000,
        )
        book.authors.add(author)
        book_id = book.pk
        author_id = author.pk

        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        new_apps = executor.loader.project_state(new_target).apps
        NewBook = new_apps.get_model("catalog", "Book")

        saved_book = NewBook.objects.get(pk=book_id)
        self.assertEqual(NewBook.objects.count(), 1)
        self.assertEqual(saved_book.title, "Книга до миграции")
        self.assertEqual(saved_book.publication_year, 2000)
        self.assertEqual(saved_book.description, "")
        self.assertEqual(
            list(saved_book.authors.values_list("pk", flat=True)),
            [author_id],
        )

        saved_book.description = "Описание после миграции"
        saved_book.save(update_fields=["description"])
        saved_book.refresh_from_db()
        self.assertEqual(saved_book.description, "Описание после миграции")


class AuthorDeletionUnitTests(SimpleTestCase):
    def test_author_with_books_is_not_deleted(self):
        author = Mock()
        author.books.exists.return_value = True
        view = AuthorViewSet()

        with (
            patch.object(view, "get_object", return_value=author),
            patch("rest_framework.mixins.DestroyModelMixin.destroy") as parent_destroy,
        ):
            response = view.destroy(None)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "author_has_books")
        parent_destroy.assert_not_called()

    def test_author_without_books_can_be_deleted(self):
        author = Mock()
        author.books.exists.return_value = False
        view = AuthorViewSet()
        expected_response = Response(status=204)

        with (
            patch.object(view, "get_object", return_value=author),
            patch(
                "rest_framework.mixins.DestroyModelMixin.destroy",
                return_value=expected_response,
            ) as parent_destroy,
        ):
            response = view.destroy(None)

        self.assertIs(response, expected_response)
        self.assertEqual(response.status_code, 204)
        parent_destroy.assert_called_once_with(None)

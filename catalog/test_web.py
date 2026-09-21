from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from inventory.models import Branch, Copy

from .models import Author, Book


class CatalogWebTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="librarian")
        self.client.force_login(self.user)
        self.author = Author.objects.create(full_name="Артур Конан Дойл")
        self.book = Book.objects.create(title="Собака Баскервилей", publication_year=1902)
        self.book.authors.add(self.author)

    def test_pages_show_existing_records(self):
        for route, text in [
            ("home", "Каждая книга"),
            ("authors", self.author.full_name),
            ("books", self.book.title),
        ]:
            with self.subTest(route=route):
                self.assertContains(self.client.get(reverse(f"library:{route}")), text)

    def test_empty_lists(self):
        self.book.delete()
        self.author.delete()
        self.assertContains(self.client.get(reverse("library:books")), "Здесь будут ваши книги")
        self.assertContains(self.client.get(reverse("library:authors")), "Добавьте первого автора")

    def test_author_create_and_edit(self):
        response = self.client.post(
            reverse("library:author-create"), {"full_name": "  Жюль Верн  "}
        )
        self.assertRedirects(response, reverse("library:authors"))
        author = Author.objects.get(full_name="Жюль Верн")
        self.client.post(
            reverse("library:author-edit", args=[author.pk]), {"full_name": "Жюль Габриэль Верн"}
        )
        author.refresh_from_db()
        self.assertEqual(author.full_name, "Жюль Габриэль Верн")

    def test_author_invalid_names(self):
        for value in ["", "   ", "А" * 201]:
            with self.subTest(value=value):
                response = self.client.post(reverse("library:author-create"), {"full_name": value})
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(Author.objects.count(), 1)

    def test_book_create_and_update_relations(self):
        url = reverse("library:book-create")
        response = self.client.post(
            url,
            {
                "title": "  Затерянный мир  ",
                "publication_year": "1912",
                "authors": [self.author.pk],
            },
        )
        self.assertRedirects(response, reverse("library:books"))
        book = Book.objects.get(title="Затерянный мир")
        self.assertEqual(list(book.authors.all()), [self.author])
        response = self.client.post(
            reverse("library:book-edit", args=[book.pk]),
            {"title": "Затерянный мир", "publication_year": ""},
        )
        self.assertRedirects(response, reverse("library:books"))
        book.refresh_from_db()
        self.assertIsNone(book.publication_year)
        self.assertFalse(book.authors.exists())

    def test_invalid_book_fields_preserve_data(self):
        for field, value in [
            ("title", "   "),
            ("title", "А" * 301),
            ("publication_year", "0"),
            ("publication_year", "32768"),
            ("publication_year", "1.5"),
            ("publication_year", "abc"),
            ("authors", [999999]),
        ]:
            with self.subTest(field=field, value=value):
                data = {
                    "title": "Другое название",
                    "publication_year": "1902",
                    "authors": [self.author.pk],
                }
                data[field] = value
                response = self.client.post(reverse("library:book-edit", args=[self.book.pk]), data)
                self.assertIn(field, response.context["form"].errors)
                self.book.refresh_from_db()
                self.assertEqual(self.book.title, "Собака Баскервилей")
                self.assertEqual(list(self.book.authors.all()), [self.author])

    def test_year_boundaries(self):
        for year in [1, 32767]:
            self.client.post(
                reverse("library:book-create"),
                {"title": f"Издание {year}", "publication_year": year},
            )
            self.assertTrue(Book.objects.filter(publication_year=year).exists())

    def test_delete_get_never_deletes(self):
        for kind, obj in [("author", self.author), ("book", self.book)]:
            response = self.client.get(reverse(f"library:{kind}-delete", args=[obj.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_author_with_books_cannot_be_deleted(self):
        response = self.client.post(reverse("library:author-delete", args=[self.author.pk]))
        self.assertContains(response, "Нельзя удалить автора", status_code=409)
        self.assertTrue(self.book.authors.filter(pk=self.author.pk).exists())

    def test_book_with_copy_cannot_be_deleted(self):
        branch = Branch.objects.create(name="Центральная", address="ул. Лесная, 10")
        copy = Copy.objects.create(inventory_number="LIB-001", book=self.book, branch=branch)
        response = self.client.post(reverse("library:book-delete", args=[self.book.pk]))
        self.assertContains(response, "Нельзя удалить книгу", status_code=409)
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())
        self.assertTrue(Copy.objects.filter(pk=copy.pk, book=self.book, branch=branch).exists())
        self.assertTrue(self.book.authors.filter(pk=self.author.pk).exists())

    def test_unlinked_records_can_be_deleted(self):
        response = self.client.post(reverse("library:book-delete", args=[self.book.pk]))
        self.assertRedirects(response, reverse("library:books"))
        self.assertFalse(Book.objects.filter(pk=self.book.pk).exists())
        response = self.client.post(reverse("library:author-delete", args=[self.author.pk]))
        self.assertRedirects(response, reverse("library:authors"))
        self.assertFalse(Author.objects.filter(pk=self.author.pk).exists())

    def test_csrf_required_and_valid_form_accepted(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse("library:author-create")
        self.assertEqual(client.post(url, {"full_name": "Жюль Верн"}).status_code, 403)
        client.get(url)
        response = client.post(
            url,
            {"full_name": "Жюль Верн", "csrfmiddlewaretoken": client.cookies["csrftoken"].value},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Author.objects.filter(full_name="Жюль Верн").exists())

    def test_missing_objects_return_404(self):
        for kind in ["author", "book"]:
            for action in ["edit", "delete"]:
                self.assertEqual(
                    self.client.get(reverse(f"library:{kind}-{action}", args=[999999])).status_code,
                    404,
                )

    def test_method_not_allowed(self):
        self.assertEqual(self.client.post(reverse("library:books")).status_code, 405)
        self.assertEqual(
            self.client.delete(reverse("library:book-delete", args=[self.book.pk])).status_code, 405
        )
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())

    def test_user_text_is_escaped(self):
        self.book.title = "<script>alert(1)</script>"
        self.book.save()
        response = self.client.get(reverse("library:books"))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_edit_form_displays_existing_selection(self):
        response = self.client.get(reverse("library:book-edit", args=[self.book.pk]))
        self.assertContains(response, "checked")
        self.assertContains(response, self.book.title)

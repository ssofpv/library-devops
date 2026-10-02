from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalog.models import Book

from .models import Branch, Copy


class InventoryWebTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="librarian")
        self.client.force_login(self.user)
        self.book = Book.objects.create(title="Затерянный мир")
        self.branch = Branch.objects.create(name="Центральная", address="Лесная, 10")
        self.copy = Copy.objects.create(
            inventory_number="LIB-001", book=self.book, branch=self.branch
        )

    def url(self, name, obj=None):
        return reverse(f"inventory-web:{name}", args=[obj.pk] if obj else [])

    def data(self, **changes):
        return {
            "inventory_number": "LIB-002",
            "book": self.book.pk,
            "branch": self.branch.pk,
            **changes,
        }

    def test_copy_forms_include_shelf_location(self):
        for url in [
            self.url("copy-create"),
            self.url("copy-edit", self.copy),
        ]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'name="shelf_location"')

    def test_shelf_location_create_edit_and_clear(self):
        response = self.client.post(
            self.url("copy-create"),
            self.data(shelf_location="Стеллаж 2, полка 3"),
        )
        self.assertRedirects(response, self.url("copies"))
        copy = Copy.objects.get(inventory_number="LIB-002")
        self.assertEqual(copy.shelf_location, "Стеллаж 2, полка 3")
        self.assertContains(self.client.get(self.url("copies")), "Стеллаж 2, полка 3")

        for value in ["Стеллаж 4", ""]:
            with self.subTest(shelf_location=value):
                response = self.client.post(
                    self.url("copy-edit", copy),
                    self.data(
                        inventory_number=copy.inventory_number,
                        shelf_location=value,
                    ),
                )
                self.assertRedirects(response, self.url("copies"))
                copy.refresh_from_db()
                self.assertEqual(copy.shelf_location, value)

        response = self.client.get(self.url("copies"))
        self.assertNotContains(response, "Стеллаж 2, полка 3")
        self.assertNotContains(response, "Стеллаж 4")

    def test_shelf_location_length_boundary_preserves_data(self):
        url = self.url("copy-edit", self.copy)
        response = self.client.post(
            url,
            self.data(
                inventory_number=self.copy.inventory_number,
                shelf_location="А" * 100,
            ),
        )
        self.assertRedirects(response, self.url("copies"))
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.shelf_location, "А" * 100)

        response = self.client.post(
            url,
            self.data(
                inventory_number=self.copy.inventory_number,
                shelf_location="А" * 101,
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("shelf_location", response.context["form"].errors)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.shelf_location, "А" * 100)
        self.assertEqual(self.copy.book_id, self.book.pk)
        self.assertEqual(self.copy.branch_id, self.branch.pk)

    def test_shelf_location_is_html_escaped(self):
        self.copy.shelf_location = "<script>alert('location')</script>"
        self.copy.save(update_fields=["shelf_location"])

        response = self.client.get(self.url("copies"))
        self.assertContains(response, "&lt;script&gt;")
        self.assertContains(response, "&lt;/script&gt;")
        self.assertNotContains(response, self.copy.shelf_location)

    def test_pages_and_navigation(self):
        self.assertContains(self.client.get(self.url("branches")), self.branch.address)
        self.assertContains(self.client.get(self.url("copies")), self.copy.inventory_number)
        self.assertContains(self.client.get(reverse("library:home")), self.url("branches"))
        self.assertContains(self.client.get(reverse("library:home")), self.url("copies"))

    def test_branch_create_edit(self):
        response = self.client.post(
            self.url("branch-create"), {"name": "  Южная  ", "address": "Полевая, 2"}
        )
        self.assertRedirects(response, self.url("branches"))
        obj = Branch.objects.get(name="Южная")
        self.client.post(self.url("branch-edit", obj), {"name": "Южная", "address": "Полевая, 4"})
        obj.refresh_from_db()
        self.assertEqual(obj.address, "Полевая, 4")

    def test_branch_invalid_fields(self):
        for field, value in [
            ("name", "  "),
            ("name", "А" * 201),
            ("address", ""),
            ("address", "  "),
            ("address", "А" * 501),
        ]:
            with self.subTest(field=field, value=value):
                data = {"name": "Южная", "address": "Полевая, 2", field: value}
                response = self.client.post(self.url("branch-create"), data)
                self.assertIn(field, response.context["form"].errors)
                self.assertEqual(Branch.objects.count(), 1)

    def test_copy_create_and_transfer(self):
        response = self.client.post(
            self.url("copy-create"), self.data(inventory_number="  LIB-002  ")
        )
        self.assertRedirects(response, self.url("copies"))
        obj = Copy.objects.get(inventory_number="LIB-002")
        target = Branch.objects.create(name="Южная", address="Полевая, 2")
        response = self.client.post(self.url("copy-edit", obj), self.data(branch=target.pk))
        self.assertRedirects(response, self.url("copies"))
        obj.refresh_from_db()
        self.assertEqual(obj.branch, target)
        self.assertEqual(obj.book, self.book)
        self.assertEqual(Copy.objects.count(), 2)

    def test_duplicate_number_rejected(self):
        response = self.client.post(
            self.url("copy-create"), self.data(inventory_number=" LIB-001 ")
        )
        self.assertIn("inventory_number", response.context["form"].errors)
        self.assertEqual(Copy.objects.count(), 1)

    def test_invalid_copy_fields(self):
        for field, value in [
            ("inventory_number", "  "),
            ("inventory_number", "А" * 101),
            ("book", ""),
            ("book", "abc"),
            ("book", 999999),
            ("branch", ""),
            ("branch", 999999),
        ]:
            with self.subTest(field=field, value=value):
                response = self.client.post(
                    self.url("copy-edit", self.copy), self.data(**{field: value})
                )
                self.assertIn(field, response.context["form"].errors)
                self.copy.refresh_from_db()
                self.assertEqual(self.copy.inventory_number, "LIB-001")
                self.assertEqual(self.copy.book, self.book)
                self.assertEqual(self.copy.branch, self.branch)

    def test_duplicate_on_edit_preserves_data(self):
        Copy.objects.create(inventory_number="LIB-002", book=self.book, branch=self.branch)
        response = self.client.post(self.url("copy-edit", self.copy), self.data())
        self.assertIn("inventory_number", response.context["form"].errors)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.inventory_number, "LIB-001")

    def test_independent_and_combined_filters(self):
        other_book = Book.objects.create(title="Таинственный остров")
        other_branch = Branch.objects.create(name="Южная", address="Полевая, 2")
        b = Copy.objects.create(inventory_number="LIB-002", book=other_book, branch=self.branch)
        c = Copy.objects.create(inventory_number="LIB-003", book=self.book, branch=other_branch)
        for query, expected in [
            ({"book": self.book.pk}, [self.copy, c]),
            ({"branch": self.branch.pk}, [self.copy, b]),
            ({"book": self.book.pk, "branch": self.branch.pk}, [self.copy]),
            ({"book": other_book.pk, "branch": other_branch.pk}, []),
            ({"book": "", "branch": ""}, [self.copy, b, c]),
        ]:
            with self.subTest(query=query):
                response = self.client.get(self.url("copies"), query)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context["copies"]), expected)

    def test_invalid_filters(self):
        for field in ["book", "branch"]:
            for value in ["abc", "-1", "999999", "9" * 100]:
                with self.subTest(field=field, value=value):
                    response = self.client.get(self.url("copies"), {field: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertFalse(response.context["copies"].exists())

    def test_branch_protection(self):
        response = self.client.post(self.url("branch-delete", self.branch))
        self.assertContains(response, "Нельзя удалить филиал", status_code=409)
        self.assertTrue(Branch.objects.filter(pk=self.branch.pk).exists())
        self.assertTrue(Copy.objects.filter(pk=self.copy.pk, branch=self.branch).exists())

    def test_get_delete_does_not_mutate(self):
        for kind, obj in [("branch", self.branch), ("copy", self.copy)]:
            self.assertEqual(self.client.get(self.url(f"{kind}-delete", obj)).status_code, 200)
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_delete_copy_then_branch(self):
        self.assertRedirects(
            self.client.post(self.url("copy-delete", self.copy)), self.url("copies")
        )
        self.assertFalse(Copy.objects.filter(pk=self.copy.pk).exists())
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())
        self.assertRedirects(
            self.client.post(self.url("branch-delete", self.branch)), self.url("branches")
        )
        self.assertFalse(Branch.objects.filter(pk=self.branch.pk).exists())

    def test_csrf_protects_mutations(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url("copy-delete", self.copy)).status_code, 403)
        self.assertTrue(Copy.objects.filter(pk=self.copy.pk).exists())
        client.get(self.url("copy-create"))
        response = client.post(
            self.url("copy-create"),
            self.data(csrfmiddlewaretoken=client.cookies["csrftoken"].value),
        )
        self.assertEqual(response.status_code, 302)

    def test_missing_records_and_wrong_methods(self):
        for route in ["branch-edit", "branch-delete", "copy-edit", "copy-delete"]:
            self.assertEqual(
                self.client.get(reverse(f"inventory-web:{route}", args=[999999])).status_code, 404
            )
        self.assertEqual(self.client.post(self.url("branches")).status_code, 405)
        self.assertEqual(self.client.delete(self.url("copy-delete", self.copy)).status_code, 405)

    def test_creation_forms_without_related_records(self):
        self.copy.delete()
        self.branch.delete()
        self.book.delete()
        self.assertContains(self.client.get(self.url("copies")), "Экземпляры не найдены")
        self.assertEqual(self.client.get(self.url("copy-create")).status_code, 200)
        response = self.client.post(self.url("copy-create"), {"inventory_number": "LIB-001"})
        self.assertIn("book", response.context["form"].errors)
        self.assertIn("branch", response.context["form"].errors)

    def test_labels_escaped_and_selection_preserved(self):
        self.branch.name = "<script>alert(1)</script>"
        self.branch.save()
        response = self.client.get(self.url("branches"))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        response = self.client.get(self.url("copy-edit", self.copy))
        self.assertContains(response, f'value="{self.book.pk}" selected')

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.urls import reverse
from rest_framework.test import APITestCase

from catalog.models import Author, Book

from .models import Branch, Copy


class CopyAPITests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="librarian")
        self.client.force_login(self.user)
        self.author = Author.objects.create(full_name="Михаил Булгаков")
        self.book = Book.objects.create(title="Мастер и Маргарита")
        self.book.authors.add(self.author)
        self.other_book = Book.objects.create(title="Другая книга")
        self.branch = Branch.objects.create(
            name="Центральный",
            address="ул. Ленина, 10",
        )
        self.other_branch = Branch.objects.create(
            name="Северный",
            address="ул. Мира, 5",
        )
        self.copy = Copy.objects.create(
            inventory_number="INV-001",
            book=self.book,
            branch=self.branch,
        )
        self.list_url = reverse("copy-list")
        self.detail_url = reverse("copy-detail", args=[self.copy.id])

    def payload(self, **changes):
        data = {
            "inventory_number": "INV-002",
            "book_id": self.book.id,
            "branch_id": self.branch.id,
        }
        data.update(changes)
        return data

    def assert_original_copy(self):
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.inventory_number, "INV-001")
        self.assertEqual(self.copy.book_id, self.book.id)
        self.assertEqual(self.copy.branch_id, self.branch.id)

    def test_create_copy(self):
        response = self.client.post(
            self.list_url,
            self.payload(inventory_number="  INV-002  "),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        copy = Copy.objects.get(pk=response.data["id"])
        self.assertEqual(copy.inventory_number, "INV-002")
        self.assertEqual(copy.book_id, self.book.id)
        self.assertEqual(copy.branch_id, self.branch.id)
        self.assertEqual(response.data["book_id"], self.book.id)
        self.assertEqual(response.data["branch_id"], self.branch.id)

    def test_invalid_create_preserves_database(self):
        cases = [
            ("inventory_number", ""),
            ("inventory_number", "   "),
            ("inventory_number", None),
            ("inventory_number", "A" * 101),
            ("inventory_number", "INV-001"),
            ("inventory_number", "  INV-001  "),
            ("book_id", None),
            ("book_id", 99999),
            ("book_id", "abc"),
            ("branch_id", None),
            ("branch_id", 99999),
            ("branch_id", "abc"),
        ]

        for field, value in cases:
            with self.subTest(field=field, value=value):
                response = self.client.post(
                    self.list_url,
                    self.payload(**{field: value}),
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
                self.assertEqual(Copy.objects.count(), 1)
                self.assert_original_copy()

    def test_required_fields(self):
        for field in ("inventory_number", "book_id", "branch_id"):
            with self.subTest(field=field):
                data = self.payload()
                del data[field]
                response = self.client.post(
                    self.list_url,
                    data,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
                self.assertEqual(Copy.objects.count(), 1)

    def test_list_and_retrieve(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": self.copy.id,
                    "inventory_number": "INV-001",
                    "book_id": self.book.id,
                    "branch_id": self.branch.id,
                },
            ],
        )

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.copy.id)

    def test_put_updates_copy(self):
        response = self.client.put(
            self.detail_url,
            self.payload(
                inventory_number="INV-003",
                book_id=self.other_book.id,
                branch_id=self.other_branch.id,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.inventory_number, "INV-003")
        self.assertEqual(self.copy.book_id, self.other_book.id)
        self.assertEqual(self.copy.branch_id, self.other_branch.id)

    def test_patch_moves_copy_and_preserves_other_fields(self):
        response = self.client.patch(
            self.detail_url,
            {"branch_id": self.other_branch.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.branch_id, self.other_branch.id)
        self.assertEqual(self.copy.book_id, self.book.id)
        self.assertEqual(self.copy.inventory_number, "INV-001")

    def test_invalid_patch_preserves_all_fields(self):
        response = self.client.patch(
            self.detail_url,
            {
                "inventory_number": "CHANGED",
                "branch_id": 99999,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assert_original_copy()

    def test_duplicate_update_is_rejected(self):
        Copy.objects.create(
            inventory_number="INV-002",
            book=self.other_book,
            branch=self.other_branch,
        )

        response = self.client.patch(
            self.detail_url,
            {"inventory_number": "INV-002"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("inventory_number", response.data)
        self.assert_original_copy()
        self.assertEqual(Copy.objects.count(), 2)

    def test_unchanged_inventory_number_is_allowed(self):
        response = self.client.patch(
            self.detail_url,
            {"inventory_number": "INV-001"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assert_original_copy()

    def test_filters(self):
        second = Copy.objects.create(
            inventory_number="INV-002",
            book=self.book,
            branch=self.other_branch,
        )
        third = Copy.objects.create(
            inventory_number="INV-003",
            book=self.other_book,
            branch=self.branch,
        )
        cases = [
            ({}, [self.copy.id, second.id, third.id]),
            ({"book_id": self.book.id}, [self.copy.id, second.id]),
            ({"branch_id": self.branch.id}, [self.copy.id, third.id]),
            (
                {
                    "book_id": self.book.id,
                    "branch_id": self.branch.id,
                },
                [self.copy.id],
            ),
            ({"book_id": 99999}, []),
            ({"branch_id": 99999}, []),
        ]

        for params, expected_ids in cases:
            with self.subTest(params=params):
                response = self.client.get(self.list_url, params)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    [item["id"] for item in response.json()],
                    expected_ids,
                )

    def test_invalid_filters(self):
        for field in ("book_id", "branch_id"):
            for value in ("abc", "0", "-1", "1.5", "", "9" * 30):
                with self.subTest(field=field, value=value):
                    response = self.client.get(
                        self.list_url,
                        {field: value},
                    )

                    self.assertEqual(response.status_code, 400)
                    self.assertIn(field, response.data)

    def test_delete_copy_preserves_book_and_branch(self):
        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Copy.objects.filter(pk=self.copy.id).exists())
        self.assertTrue(Book.objects.filter(pk=self.book.id).exists())
        self.assertTrue(Branch.objects.filter(pk=self.branch.id).exists())

    def test_missing_copy(self):
        url = reverse("copy-detail", args=[99999])

        for method in ("get", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 404)

    def test_protected_deletion_through_api_preserves_data(self):
        cases = [
            ("book-detail", self.book),
            ("branch-detail", self.branch),
        ]

        for route, obj in cases:
            with self.subTest(route=route):
                response = self.client.delete(
                    reverse(route, args=[obj.id]),
                )

                self.assertEqual(response.status_code, 409)
                self.assertTrue(
                    type(obj).objects.filter(pk=obj.id).exists(),
                )
                self.assert_original_copy()
                self.assertTrue(
                    self.book.authors.filter(pk=self.author.id).exists(),
                )

    def test_protected_deletion_through_orm(self):
        for obj in (self.book, self.branch):
            with self.subTest(model=type(obj).__name__):
                with self.assertRaises(ProtectedError):
                    obj.delete()

                self.assertTrue(
                    type(obj).objects.filter(pk=obj.id).exists(),
                )
                self.assert_original_copy()

    def test_inventory_number_is_unique_in_database(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Copy.objects.create(
                    inventory_number="INV-001",
                    book=self.other_book,
                    branch=self.other_branch,
                )

        self.assertEqual(Copy.objects.count(), 1)
        self.assert_original_copy()

    def test_book_and_branch_can_be_deleted_after_last_copy(self):
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, 204)

        response = self.client.delete(
            reverse("book-detail", args=[self.book.id]),
        )
        self.assertEqual(response.status_code, 204)
        self.assertTrue(Author.objects.filter(pk=self.author.id).exists())

        response = self.client.delete(
            reverse("branch-detail", args=[self.branch.id]),
        )
        self.assertEqual(response.status_code, 204)

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Branch


class BranchAPITests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="librarian")
        self.client.force_login(self.user)

    def test_create_branch(self):
        response = self.client.post(
            reverse("branch-list"),
            {
                "name": "  Центральный  ",
                "address": "  ул. Ленина, 10  ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        branch = Branch.objects.get(pk=response.data["id"])
        self.assertEqual(branch.name, "Центральный")
        self.assertEqual(branch.address, "ул. Ленина, 10")

    def test_invalid_fields_are_rejected(self):
        cases = [
            ("name", None),
            ("name", ""),
            ("name", "   "),
            ("name", "А" * 201),
            ("address", None),
            ("address", ""),
            ("address", "   "),
            ("address", "А" * 501),
        ]

        for field, value in cases:
            with self.subTest(field=field, value=value):
                data = {
                    "name": "Центральный",
                    "address": "ул. Ленина, 10",
                }

                if value is None:
                    del data[field]
                else:
                    data[field] = value

                response = self.client.post(
                    reverse("branch-list"),
                    data,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

        self.assertEqual(Branch.objects.count(), 0)

    def test_list_branches(self):
        branch = Branch.objects.create(
            name="Центральный",
            address="ул. Ленина, 10",
        )

        response = self.client.get(reverse("branch-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": branch.id,
                    "name": "Центральный",
                    "address": "ул. Ленина, 10",
                }
            ],
        )

    def test_get_branch(self):
        branch = Branch.objects.create(
            name="Центральный",
            address="ул. Ленина, 10",
        )

        response = self.client.get(reverse("branch-detail", args=[branch.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], branch.id)
        self.assertEqual(response.data["name"], "Центральный")
        self.assertEqual(response.data["address"], "ул. Ленина, 10")

    def test_update_branch_address(self):
        branch = Branch.objects.create(
            name="Центральный",
            address="ул. Ленина, 10",
        )

        response = self.client.patch(
            reverse("branch-detail", args=[branch.id]),
            {"address": "ул. Мира, 5"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        branch.refresh_from_db()
        self.assertEqual(branch.address, "ул. Мира, 5")
        self.assertEqual(branch.name, "Центральный")

    def test_invalid_update_preserves_data(self):
        branch = Branch.objects.create(
            name="Центральный",
            address="ул. Ленина, 10",
        )

        response = self.client.patch(
            reverse("branch-detail", args=[branch.id]),
            {"name": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        branch.refresh_from_db()
        self.assertEqual(branch.name, "Центральный")
        self.assertEqual(branch.address, "ул. Ленина, 10")

    def test_delete_branch(self):
        branch = Branch.objects.create(
            name="Центральный",
            address="ул. Ленина, 10",
        )

        response = self.client.delete(reverse("branch-detail", args=[branch.id]))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Branch.objects.filter(pk=branch.id).exists())

    def test_missing_branch_returns_404(self):
        response = self.client.get(reverse("branch-detail", args=[99999]))

        self.assertEqual(response.status_code, 404)


class CopyShelfLocationMigrationTests(TransactionTestCase):
    def test_existing_copy_and_relations_survive_migration(self):
        old_target = [
            ("catalog", "0002_book_description"),
            ("inventory", "0002_copy"),
        ]
        new_target = [
            ("catalog", "0002_book_description"),
            ("inventory", "0003_copy_shelf_location"),
        ]

        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()

        def restore_schema():
            MigrationExecutor(connection).migrate(latest_targets)

        self.addCleanup(restore_schema)
        executor.migrate(old_target)

        old_apps = executor.loader.project_state(old_target).apps
        OldBook = old_apps.get_model("catalog", "Book")
        OldBranch = old_apps.get_model("inventory", "Branch")
        OldCopy = old_apps.get_model("inventory", "Copy")

        book = OldBook.objects.create(
            title="Книга до миграции",
            description="Описание книги",
        )
        branch = OldBranch.objects.create(
            name="Филиал до миграции",
            address="Учебный адрес",
        )
        copy = OldCopy.objects.create(
            inventory_number="MIG-001",
            book=book,
            branch=branch,
        )
        copy_id = copy.pk
        book_id = book.pk
        branch_id = branch.pk

        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        new_apps = executor.loader.project_state(new_target).apps
        NewCopy = new_apps.get_model("inventory", "Copy")

        saved_copy = NewCopy.objects.get(pk=copy_id)
        self.assertEqual(NewCopy.objects.count(), 1)
        self.assertEqual(saved_copy.inventory_number, "MIG-001")
        self.assertEqual(saved_copy.shelf_location, "")
        self.assertEqual(saved_copy.book_id, book_id)
        self.assertEqual(saved_copy.branch_id, branch_id)
        self.assertEqual(saved_copy.book.title, "Книга до миграции")
        self.assertEqual(saved_copy.book.description, "Описание книги")
        self.assertEqual(saved_copy.branch.name, "Филиал до миграции")
        self.assertEqual(saved_copy.branch.address, "Учебный адрес")

        saved_copy.shelf_location = "Стеллаж после миграции"
        saved_copy.save(update_fields=["shelf_location"])
        saved_copy.refresh_from_db()
        self.assertEqual(saved_copy.shelf_location, "Стеллаж после миграции")


class CopyStatusMigrationTests(TransactionTestCase):
    def test_existing_copy_gets_status_and_preserves_data(self):
        old_target = [
            ("catalog", "0002_book_description"),
            ("inventory", "0003_copy_shelf_location"),
        ]
        new_target = [
            ("catalog", "0002_book_description"),
            ("inventory", "0004_copy_status"),
        ]

        executor = MigrationExecutor(connection)
        latest_targets = executor.loader.graph.leaf_nodes()

        def restore_schema():
            MigrationExecutor(connection).migrate(latest_targets)

        self.addCleanup(restore_schema)
        executor.migrate(old_target)

        old_apps = executor.loader.project_state(old_target).apps
        OldBook = old_apps.get_model("catalog", "Book")
        OldBranch = old_apps.get_model("inventory", "Branch")
        OldCopy = old_apps.get_model("inventory", "Copy")

        book = OldBook.objects.create(
            title="Книга до добавления статуса",
            description="Сохранённое описание",
        )
        branch = OldBranch.objects.create(
            name="Учебный филиал",
            address="Учебный адрес",
        )
        copy = OldCopy.objects.create(
            inventory_number="STATUS-001",
            shelf_location="Стеллаж 7",
            book=book,
            branch=branch,
        )
        copy_id = copy.pk
        book_id = book.pk
        branch_id = branch.pk

        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        new_apps = executor.loader.project_state(new_target).apps
        NewCopy = new_apps.get_model("inventory", "Copy")

        saved_copy = NewCopy.objects.get(pk=copy_id)
        self.assertEqual(NewCopy.objects.count(), 1)
        self.assertEqual(saved_copy.inventory_number, "STATUS-001")
        self.assertEqual(saved_copy.shelf_location, "Стеллаж 7")
        self.assertEqual(saved_copy.status, "available")
        self.assertEqual(saved_copy.book_id, book_id)
        self.assertEqual(saved_copy.branch_id, branch_id)
        self.assertEqual(saved_copy.book.title, "Книга до добавления статуса")
        self.assertEqual(saved_copy.book.description, "Сохранённое описание")
        self.assertEqual(saved_copy.branch.name, "Учебный филиал")
        self.assertEqual(saved_copy.branch.address, "Учебный адрес")

        saved_copy.status = "issued"
        saved_copy.save(update_fields=["status"])
        saved_copy.refresh_from_db()
        self.assertEqual(saved_copy.status, "issued")

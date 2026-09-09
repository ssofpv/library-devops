from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Branch


class BranchAPITests(APITestCase):
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

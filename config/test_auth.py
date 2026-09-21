from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from catalog.models import Author, Book
from inventory.models import Branch, Copy


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Test-only-long-password-947!"
        cls.user = get_user_model().objects.create_user(username="librarian", password=cls.password)
        cls.author = Author.objects.create(full_name="Тестовый автор")
        cls.book = Book.objects.create(title="Тестовая книга")
        cls.branch = Branch.objects.create(name="Филиал", address="Адрес")
        cls.copy = Copy.objects.create(inventory_number="AUTH-1", book=cls.book, branch=cls.branch)

    def login(self, client=None, **extra):
        return (client or self.client).post(
            "/accounts/login/",
            {"username": self.user.username, "password": self.password, **extra},
        )

    def test_login_page_is_public_and_russian(self):
        response = self.client.get("/accounts/login/")
        self.assertContains(response, "Вход в библиотеку")
        self.assertContains(response, 'type="password"')
        self.assertNotContains(response, 'href="/books/"')

    def test_all_html_routes_require_login(self):
        paths = ["/"]
        for section, obj in [
            ("authors", self.author),
            ("books", self.book),
            ("branches", self.branch),
            ("copies", self.copy),
        ]:
            paths.extend(
                [
                    f"/{section}/",
                    f"/{section}/new/",
                    f"/{section}/{obj.pk}/edit/",
                    f"/{section}/{obj.pk}/delete/",
                ]
            )
        for path in paths:
            for method in ["get", "post"]:
                with self.subTest(path=path, method=method):
                    response = getattr(self.client, method)(path)
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response.url.startswith("/accounts/login/?next="))
        self.assertEqual(Author.objects.count(), 1)
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(Branch.objects.count(), 1)
        self.assertEqual(Copy.objects.count(), 1)

    def test_all_api_resources_reject_anonymous_access(self):
        for section, obj in [
            ("authors", self.author),
            ("books", self.book),
            ("branches", self.branch),
            ("copies", self.copy),
        ]:
            for method, path in [
                ("get", f"/api/{section}/"),
                ("post", f"/api/{section}/"),
                ("get", f"/api/{section}/{obj.pk}/"),
                ("put", f"/api/{section}/{obj.pk}/"),
                ("patch", f"/api/{section}/{obj.pk}/"),
                ("delete", f"/api/{section}/{obj.pk}/"),
            ]:
                with self.subTest(path=path, method=method):
                    response = getattr(self.client, method)(path, content_type="application/json")
                    self.assertEqual(response.status_code, 403)
                    self.assertIn("detail", response.json())
        self.assertEqual(Copy.objects.count(), 1)
        self.assertEqual(Author.objects.count(), 1)
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(Branch.objects.count(), 1)

    def test_valid_login_opens_html_and_api_for_non_staff_user(self):
        self.assertFalse(self.user.is_staff)
        self.assertRedirects(self.login(), "/")
        self.assertContains(self.client.get("/"), "librarian")
        for resource in ["authors", "books", "branches", "copies"]:
            self.assertEqual(self.client.get(f"/{resource}/").status_code, 200)
            self.assertEqual(self.client.get(f"/api/{resource}/").status_code, 200)

    def test_wrong_or_missing_credentials_do_not_create_session(self):
        for credentials in [
            {"username": "librarian", "password": "wrong"},
            {"username": "unknown", "password": self.password},
            {},
        ]:
            with self.subTest(credentials=credentials.keys()):
                response = self.client.post("/accounts/login/", credentials)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertNotIn("_auth_user_id", self.client.session)
                self.assertEqual(self.client.get("/api/books/").status_code, 403)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        response = self.login()
        self.assertTrue(response.context["form"].errors)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_disabled_user_loses_existing_access(self):
        self.login()
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get("/api/books/").status_code, 403)
        self.assertEqual(self.client.get("/books/").status_code, 302)

    def test_safe_next_is_used_and_external_next_is_rejected(self):
        self.assertRedirects(self.login(next="/books/"), "/books/")
        for target in ["https://example.org/", "//example.org/"]:
            self.client.logout()
            self.assertRedirects(self.login(next=target), "/")

    def test_logout_requires_post_and_invalidates_old_session(self):
        self.login()
        old_cookie = self.client.cookies["sessionid"].value
        self.assertEqual(self.client.get("/accounts/logout/").status_code, 405)
        self.assertRedirects(self.client.post("/accounts/logout/"), "/accounts/login/")
        self.assertEqual(self.client.get("/api/books/").status_code, 403)
        self.assertEqual(self.client.get("/books/").status_code, 302)
        replay = Client()
        replay.cookies["sessionid"] = old_cookie
        self.assertEqual(replay.get("/api/books/").status_code, 403)

    def test_login_and_logout_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.login(client).status_code, 403)
        client.get("/accounts/login/")
        self.assertEqual(
            self.login(client, csrfmiddlewaretoken=client.cookies["csrftoken"].value).status_code,
            302,
        )
        self.assertEqual(client.post("/accounts/logout/").status_code, 403)
        self.assertEqual(client.get("/api/books/").status_code, 200)
        response = client.post(
            "/accounts/logout/", {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get("/api/books/").status_code, 403)

    def test_session_api_mutation_requires_csrf_and_preserves_data(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/accounts/login/")
        self.login(client, csrfmiddlewaretoken=client.cookies["csrftoken"].value)
        response = client.post(
            "/api/authors/", {"full_name": "Новый автор"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Author.objects.filter(full_name="Новый автор").exists())
        response = client.post(
            "/api/authors/",
            {"full_name": "Новый автор"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Author.objects.filter(full_name="Новый автор").exists())

    def test_password_is_hashed(self):
        self.assertNotEqual(self.user.password, self.password)
        self.assertTrue(self.user.check_password(self.password))

    def test_health_remains_public(self):
        self.assertEqual(self.client.get("/health/").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/health/").status_code, 200)
        self.assertEqual(self.client.post("/health/").status_code, 405)

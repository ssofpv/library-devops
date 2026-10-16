from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from config.middleware import InstanceHeaderMiddleware


class InstanceHeaderTests(SimpleTestCase):
    def test_configured_instance_id(self):
        with patch.dict("os.environ", {"APP_INSTANCE_ID": "app-1"}):
            middleware = InstanceHeaderMiddleware(lambda request: HttpResponse(status=503))

        response = middleware(RequestFactory().get("/health/"))

        self.assertEqual(response["X-App-Instance"], "app-1")
        self.assertEqual(response.status_code, 503)

    def test_hostname_fallback(self):
        with (
            patch.dict("os.environ", {"APP_INSTANCE_ID": ""}),
            patch("config.middleware.socket.gethostname", return_value="container-2"),
        ):
            middleware = InstanceHeaderMiddleware(lambda request: HttpResponse())

        response = middleware(RequestFactory().get("/"))

        self.assertEqual(response["X-App-Instance"], "container-2")

    def test_header_in_django_response(self):
        response = self.client.get("/instance-header-check-not-found/")

        self.assertEqual(response.status_code, 404)
        self.assertIn("X-App-Instance", response)
        self.assertTrue(response["X-App-Instance"])

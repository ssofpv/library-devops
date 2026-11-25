import json
from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse


class RequestLogTests(TestCase):
    def test_request_log_matches_response_id_and_excludes_request_data(self):
        with self.assertLogs("library.requests", level="INFO") as logs:
            response = self.client.get(
                reverse("health") + "?token=demo-query-value",
                headers={
                    "Authorization": "Bearer demo-auth-value",
                    "Cookie": "sessionid=demo-cookie-value",
                    "X-Request-ID": "demo-incoming-id",
                },
            )

        self.assertEqual(len(logs.records), 1)
        message = logs.records[0].getMessage()
        event = json.loads(message)
        self.assertEqual(event["event"], "http_request")
        self.assertEqual(event["level"], "INFO")
        self.assertEqual(event["route"], "/health/")
        self.assertEqual(event["status"], 200)
        self.assertRegex(event["timestamp"], r"^\d{4}-\d{2}-\d{2}T.*\+00:00$")
        self.assertRegex(event["request_id"], r"^[a-f0-9]{32}$")
        self.assertEqual(event["request_id"], response["X-Request-ID"])
        self.assertNotIn("demo-", message)

    def test_unknown_route_does_not_log_user_input(self):
        body_marker = "demo-body-value"
        with self.assertLogs("library.requests", level="WARNING") as logs:
            response = self.client.post("/demo-path-value/", {"password": body_marker})

        self.assertEqual(response.status_code, 404)
        message = logs.records[0].getMessage()
        self.assertEqual(json.loads(message)["route"], "unresolved")
        self.assertNotIn("demo-", message)

    def test_database_failure_is_logged_without_exception_details(self):
        with (
            patch(
                "config.views.connection.cursor",
                side_effect=OperationalError("demo-database-detail"),
            ),
            self.assertLogs("library.requests", level="ERROR") as logs,
        ):
            self.client.get(reverse("health"))

        message = logs.records[0].getMessage()
        self.assertEqual(json.loads(message)["status"], 503)
        self.assertNotIn("demo-", message)

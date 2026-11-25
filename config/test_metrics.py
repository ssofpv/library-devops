from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse
from prometheus_client.parser import text_string_to_metric_families

from catalog.models import Book
from inventory.models import Branch, Copy


class MetricsTests(TestCase):
    def read_samples(self):
        response = self.client.get(reverse("metrics"))
        self.assertEqual(response.status_code, 200)
        return [
            sample
            for family in text_string_to_metric_families(response.content.decode())
            for sample in family.samples
        ]

    @override_settings(METRICS_ENABLED=False)
    def test_metrics_disabled_by_default_on_deployed_environments(self):
        self.assertEqual(self.client.get(reverse("metrics")).status_code, 404)

    @override_settings(METRICS_ENABLED=True)
    def test_http_counts_latency_and_database_metrics(self):
        book = Book.objects.create(title="Monitoring book")
        branch = Branch.objects.create(name="Monitoring branch", address="Test address")
        Copy.objects.create(inventory_number="MON-01", book=book, branch=branch)
        Copy.objects.create(
            inventory_number="MON-02", book=book, branch=branch, status=Copy.Status.ISSUED
        )
        self.client.get(reverse("health") + "?token=demo-secret")
        with patch("config.views.connection.cursor", side_effect=OperationalError):
            self.client.get(reverse("health"))

        samples = self.read_samples()
        values = {sample.name: sample.value for sample in samples}
        statuses = {
            sample.labels["status_class"]
            for sample in samples
            if sample.name == "library_http_requests_total" and sample.labels["route"] == "/health/"
        }
        self.assertEqual(statuses, {"2xx", "5xx"})
        self.assertIn("library_http_request_duration_seconds_count", values)
        self.assertEqual(values["library_app_ready"], 1)
        self.assertEqual(values["library_available_copies"], 1)
        self.assertFalse(any("demo-secret" in str(s.labels) for s in samples))

    @override_settings(METRICS_ENABLED=True)
    def test_database_failure_preserves_http_metrics_and_omits_unknown_copy_count(self):
        with patch("config.metrics.Copy.objects.filter", side_effect=OperationalError):
            samples = self.read_samples()

        values = {sample.name: sample.value for sample in samples}
        self.assertEqual(values["library_app_ready"], 0)
        self.assertNotIn("library_available_copies", values)

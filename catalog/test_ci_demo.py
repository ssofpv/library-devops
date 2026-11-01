from django.test import SimpleTestCase


class CIDemonstrationTest(SimpleTestCase):
    def test_example_failure(self):
        self.assertTrue(False, "Учебная демонстрация ошибки теста")
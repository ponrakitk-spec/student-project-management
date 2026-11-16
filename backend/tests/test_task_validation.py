import unittest
from datetime import date
from backend.task_validation import task_name, task_description, task_due_date, task_status


class TaskValidationTests(unittest.TestCase):
    def test_name_trim_and_unicode_limit(self):
        self.assertEqual(task_name(" \tWork\n"), "Work")
        self.assertEqual(task_name("🌳" * 255), "🌳" * 255)

    def test_invalid_and_overlong_names(self):
        for value in (None, True, 12, [], {}, "", " \t\r\n", "x" * 256):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                task_name(value)

    def test_postgresql_invalid_text_is_rejected(self):
        for value in ("a\x00b", "\ud800", "\udfff"):
            for validator in (task_name, task_description):
                with self.assertRaises(ValueError):
                    validator(value)

    def test_optional_description_without_new_length_limit(self):
        self.assertIsNone(task_description(None))
        self.assertIsNone(task_description(" \t\n"))
        self.assertEqual(task_description("  Many\nwords  "), "Many\nwords")
        self.assertEqual(task_description("x" * 5000), "x" * 5000)

    def test_optional_due_date_and_leap_day(self):
        self.assertIsNone(task_due_date(None))
        self.assertEqual(task_due_date("2028-02-29"), date(2028, 2, 29))

    def test_invalid_dates_and_types(self):
        for value in (True, 20260101, "2026-02-29", "2026-13-01", "2026-1-01", "2026-01-01T00:00:00Z", " 2026-01-01", "0000-01-01"):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                task_due_date(value)

    def test_business_date_is_not_guessed_from_python_clock(self):
        self.assertEqual(task_due_date("2000-01-01"), date(2000, 1, 1))

    def test_status_values_are_strict_without_inferring_transitions(self):
        for value in ("not_started", "in_progress", "completed"):
            self.assertEqual(task_status(value), value)
        for value in (None, True, 1, "done", " completed "):
            with self.assertRaises(ValueError):
                task_status(value)


if __name__ == "__main__":
    unittest.main()

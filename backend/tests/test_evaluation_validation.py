"""Offline acceptance cases for the confirmed V1 score/comment rules."""

from decimal import Decimal
import unittest

from backend.evaluation_validation import validate_comment, validate_score


class EvaluationValidationTests(unittest.TestCase):
    def test_score_includes_zero_and_hundred(self):
        for score in (0, 1, 50, 99, 100):
            self.assertEqual(validate_score(score), score)

    def test_score_rejects_out_of_range_even_for_very_large_integers(self):
        for score in (-1, 101, -(10 ** 100), 10 ** 100):
            with self.assertRaisesRegex(ValueError, "^EVALUATION_SCORE_OUT_OF_RANGE$"):
                validate_score(score)

    def test_booleans_are_not_scores(self):
        for score in (True, False):
            with self.assertRaisesRegex(ValueError, "^EVALUATION_SCORE_INTEGER_REQUIRED$"):
                validate_score(score)

    def test_fractional_and_whole_valued_floats_are_not_coerced(self):
        for score in (0.0, 50.0, 50.5, 100.0, float("inf"), float("nan"), Decimal("80")):
            with self.assertRaisesRegex(ValueError, "^EVALUATION_SCORE_INTEGER_REQUIRED$"):
                validate_score(score)

    def test_strings_null_and_collections_are_not_coerced(self):
        for score in ("0", "100", "", None, [], {}, b"50"):
            with self.assertRaisesRegex(ValueError, "^EVALUATION_SCORE_INTEGER_REQUIRED$"):
                validate_score(score)

    def test_comment_matches_sql_ascii_trim_and_keeps_internal_text(self):
        self.assertEqual(validate_comment(" \t\r\n\f\v ผลงานดี\nควรปรับ\tส่วนทดสอบ \t"), "ผลงานดี\nควรปรับ\tส่วนทดสอบ")

    def test_empty_and_ascii_whitespace_only_comments_are_rejected(self):
        for comment in ("", " ", "\t\r\n\f\v", " \n  \t"):
            with self.assertRaisesRegex(ValueError, "^EVALUATION_COMMENT_REQUIRED$"):
                validate_comment(comment)

    def test_comment_must_be_text_and_cannot_be_null(self):
        for comment in (None, 0, True, [], {}, b"feedback"):
            with self.assertRaisesRegex(ValueError, "^EVALUATION_COMMENT_REQUIRED$"):
                validate_comment(comment)

    def test_nul_and_unencodable_surrogates_are_rejected_without_echo(self):
        for comment in ("PrivateFeedback\x00", "PrivateFeedback\ud800", "\udfffPrivateFeedback"):
            with self.assertRaises(ValueError) as error:
                validate_comment(comment)
            self.assertEqual(str(error.exception), "EVALUATION_COMMENT_INVALID")
            self.assertNotIn("PrivateFeedback", str(error.exception))

    def test_unicode_text_and_emoji_are_preserved(self):
        self.assertEqual(validate_comment("  อธิบายชัดเจน 👍  "), "อธิบายชัดเจน 👍")

    def test_no_unapproved_text_length_limit_is_added(self):
        comment = "ก" * 4096
        self.assertEqual(validate_comment(comment), comment)

    def test_unicode_whitespace_is_not_silently_normalized_beyond_sql(self):
        comment = "\u00a0ข้อความ\u00a0"
        self.assertEqual(validate_comment(comment), comment)


if __name__ == "__main__":
    unittest.main()

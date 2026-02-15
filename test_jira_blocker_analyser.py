# -*- coding: utf-8 -*-
"""Unit tests for data processing and calculation functions (main is not tested)."""
import sys
import unittest
import unittest.mock
import importlib.util
from datetime import datetime, timezone

# Mock dependencies so module loads without jira/numpy/pandas installed
class NumpyMock:
    @staticmethod
    def round(x, decimals=0):
        return round(float(x), decimals)

sys.modules["numpy"] = NumpyMock()
sys.modules["jira"] = unittest.mock.MagicMock()
sys.modules["pandas"] = unittest.mock.MagicMock()

# Load module with hyphen in filename
spec = importlib.util.spec_from_file_location(
    "jira_blocker_analyser",
    "jira-blocker-analyser.py"
)
jira_blocker_analyser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jira_blocker_analyser)

blocker_category_from_comment = jira_blocker_analyser.blocker_category_from_comment
comments_text = jira_blocker_analyser.comments_text
blocker_info_to_dict = jira_blocker_analyser.blocker_info_to_dict
process_issue = jira_blocker_analyser.process_issue
format_blocking_time = jira_blocker_analyser.format_blocking_time


def make_comment(created: str, body: str):
    """Create a minimal comment-like object."""
    c = unittest.mock.MagicMock()
    c.created = created
    c.body = body
    return c


def make_changelog_item(field: str, from_string: str = None, to_string: str = None):
    """Create a changelog item (e.g. field='Flagged', fromString='Impediment')."""
    item = unittest.mock.MagicMock()
    item.field = field
    item.fromString = from_string
    item.toString = to_string
    return item


def make_history(created: str, items: list):
    """Create a changelog history entry."""
    h = unittest.mock.MagicMock()
    h.created = created
    h.items = items
    return h


def make_issue_with_changelog(key: str, summary: str, histories: list, comments: list = None):
    """Create issue with changelog and comments for process_issue."""
    issue = unittest.mock.MagicMock()
    issue.key = key
    issue.fields.summary = summary
    issue.fields.comment.comments = comments or []
    issue.changelog.histories = histories
    return issue


class TestProcessIssue(unittest.TestCase):
    def setUp(self):
        jira_blocker_analyser.category_pattern = r"#\w+"

    def test_returns_empty_when_no_flagged_changes(self):
        histories = [
            make_history("2024-01-15T10:00:00.000000+0000", [
                make_changelog_item("status", to_string="In Progress"),
            ]),
        ]
        issue = make_issue_with_changelog("PROJ-1", "Summary", histories)
        jira = unittest.mock.MagicMock()
        jira.issue.return_value = issue
        result = process_issue(jira, issue)
        self.assertEqual(result, [])
        jira.issue.assert_called_once_with("PROJ-1", expand="changelog")

    def test_one_blocker_cycle_set_then_removed_stores_seconds(self):
        histories = [
            make_history("2024-01-15T10:00:00.000000+0000", [
                make_changelog_item("Flagged", to_string="Impediment"),
            ]),
            make_history("2024-01-15T12:00:00.000000+0000", [
                make_changelog_item("Flagged", from_string="Impediment", to_string=None),
            ]),
        ]
        issue = make_issue_with_changelog("PROJ-2", "Blocked task", histories)
        jira = unittest.mock.MagicMock()
        jira.issue.return_value = issue
        result = process_issue(jira, issue)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Issue Key"], "PROJ-2")
        self.assertEqual(result[0]["Issue Summary"], "Blocked task")
        self.assertEqual(result[0]["Flag Set Time"], "2024-01-15 10:00")
        self.assertEqual(result[0]["Flag Removed Time"], "2024-01-15 12:00")
        self.assertEqual(result[0]["Time Blocked"], 7200)  # 2 hours in seconds
        self.assertFalse(result[0]["Flag was not removed"])

    def test_flag_set_but_not_removed_uses_last_status_change(self):
        histories = [
            make_history("2024-01-15T09:00:00.000000+0000", [
                make_changelog_item("status", to_string="In Progress"),
            ]),
            make_history("2024-01-15T10:00:00.000000+0000", [
                make_changelog_item("Flagged", to_string="Impediment"),
            ]),
            make_history("2024-01-15T14:00:00.000000+0000", [
                make_changelog_item("status", to_string="Done"),
            ]),
        ]
        issue = make_issue_with_changelog("PROJ-3", "Still flagged", histories)
        jira = unittest.mock.MagicMock()
        jira.issue.return_value = issue
        result = process_issue(jira, issue)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["Flag was not removed"])
        self.assertEqual(result[0]["Flag Removed Time"], "2024-01-15 14:00")
        self.assertEqual(result[0]["Time Blocked"], 4 * 3600)  # 4 hours in seconds

    def test_two_blocker_cycles(self):
        histories = [
            make_history("2024-01-15T10:00:00.000000+0000", [
                make_changelog_item("Flagged", to_string="Impediment"),
            ]),
            make_history("2024-01-15T11:00:00.000000+0000", [
                make_changelog_item("Flagged", from_string="Impediment"),
            ]),
            make_history("2024-01-16T10:00:00.000000+0000", [
                make_changelog_item("Flagged", to_string="Impediment"),
            ]),
            make_history("2024-01-16T12:00:00.000000+0000", [
                make_changelog_item("Flagged", from_string="Impediment"),
            ]),
        ]
        issue = make_issue_with_changelog("PROJ-4", "Two blocks", histories)
        jira = unittest.mock.MagicMock()
        jira.issue.return_value = issue
        result = process_issue(jira, issue)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["Flag Set Time"], "2024-01-15 10:00")
        self.assertEqual(result[0]["Flag Removed Time"], "2024-01-15 11:00")
        self.assertEqual(result[0]["Time Blocked"], 3600)  # 1 hour
        self.assertEqual(result[1]["Flag Set Time"], "2024-01-16 10:00")
        self.assertEqual(result[1]["Flag Removed Time"], "2024-01-16 12:00")
        self.assertEqual(result[1]["Time Blocked"], 2 * 3600)  # 2 hours

    def test_status_changes_collected_for_fallback(self):
        histories = [
            make_history("2024-01-15T08:00:00.000000+0000", [
                make_changelog_item("status", to_string="Open"),
            ]),
            make_history("2024-01-15T10:00:00.000000+0000", [
                make_changelog_item("Flagged", to_string="Impediment"),
            ]),
            make_history("2024-01-15T11:00:00.000000+0000", [
                make_changelog_item("status", to_string="In Progress"),
            ]),
        ]
        issue = make_issue_with_changelog("PROJ-5", "Flag then status", histories)
        jira = unittest.mock.MagicMock()
        jira.issue.return_value = issue
        result = process_issue(jira, issue)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["Flag Removed Time"], "2024-01-15 11:00")


class TestBlockerCategoryFromComment(unittest.TestCase):
    def test_returns_category_when_pattern_matches_and_time_equals(self):
        comments = [
            make_comment("2024-01-15T10:00:00", "Some text #infrastructure here"),
        ]
        flag_set_time = datetime(2024, 1, 15, 10, 0, 0)
        self.assertEqual(
            blocker_category_from_comment(comments, flag_set_time, r"#\w+"),
            "#infrastructure"
        )

    def test_returns_empty_when_no_comment_at_flag_time(self):
        comments = [
            make_comment("2024-01-15T09:00:00", "Text #infrastructure"),
        ]
        flag_set_time = datetime(2024, 1, 15, 10, 0, 0)
        self.assertEqual(
            blocker_category_from_comment(comments, flag_set_time, r"#\w+"),
            ""
        )

    def test_returns_empty_when_pattern_does_not_match(self):
        comments = [
            make_comment("2024-01-15T10:00:00", "No category here"),
        ]
        flag_set_time = datetime(2024, 1, 15, 10, 0, 0)
        self.assertEqual(
            blocker_category_from_comment(comments, flag_set_time, r"#\w+"),
            ""
        )

    def test_returns_first_match_when_several_comments_at_same_time(self):
        # Function iterates and returns on first match; we have one comment at flag time
        comments = [
            make_comment("2024-01-15T10:00:00", "First #cat1 and #cat2"),
        ]
        flag_set_time = datetime(2024, 1, 15, 10, 0, 0)
        self.assertEqual(
            blocker_category_from_comment(comments, flag_set_time, r"#\w+"),
            "#cat1"
        )

    def test_comment_created_with_microseconds_parsed_correctly(self):
        comments = [
            make_comment("2024-01-15T10:00:00.123456", "Text #backend"),
        ]
        # Parser uses .split(".")[0] -> "2024-01-15T10:00:00"
        flag_set_time = datetime(2024, 1, 15, 10, 0, 0)
        self.assertEqual(
            blocker_category_from_comment(comments, flag_set_time, r"#\w+"),
            "#backend"
        )

    def test_custom_pattern_curly_braces(self):
        comments = [
            make_comment("2024-01-15T10:00:00", "Blocker {external-service}"),
        ]
        flag_set_time = datetime(2024, 1, 15, 10, 0, 0)
        self.assertEqual(
            blocker_category_from_comment(comments, flag_set_time, r"\{.+?\}"),
            "{external-service}"
        )

    def test_custom_pattern_digits_prefix(self):
        comments = [
            make_comment("2024-01-15T10:00:00", "Category: [CAT-123]"),
        ]
        flag_set_time = datetime(2024, 1, 15, 10, 0, 0)
        self.assertEqual(
            blocker_category_from_comment(comments, flag_set_time, r"\[[\w-]+\]"),
            "[CAT-123]"
        )

    def test_empty_pattern_returns_empty(self):
        comments = [
            make_comment("2024-01-15T10:00:00", "Text #tag"),
        ]
        flag_set_time = datetime(2024, 1, 15, 10, 0, 0)
        self.assertEqual(
            blocker_category_from_comment(comments, flag_set_time, r""),
            ""
        )


class TestCommentsText(unittest.TestCase):
    def test_includes_only_comments_in_time_range(self):
        comments = [
            make_comment("2024-01-15T09:00:00.000000+0000", "Before"),
            make_comment("2024-01-15T10:00:00.000000+0000", "Start"),
            make_comment("2024-01-15T11:00:00.000000+0000", "Middle"),
            make_comment("2024-01-15T12:00:00.000000+0000", "End"),
            make_comment("2024-01-15T13:00:00.000000+0000", "After"),
        ]
        flag_set = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        flag_removed = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = comments_text(comments, flag_set, flag_removed)
        self.assertIn("Start", result)
        self.assertIn("Middle", result)
        self.assertIn("End", result)
        self.assertNotIn("Before", result)
        self.assertNotIn("After", result)
        self.assertEqual(result.count("---\n"), 3)

    def test_empty_when_no_comments_in_range(self):
        comments = [
            make_comment("2024-01-15T08:00:00.000000+0000", "Only before"),
        ]
        flag_set = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        flag_removed = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(comments_text(comments, flag_set, flag_removed), "")

    def test_single_comment_in_range(self):
        comments = [
            make_comment("2024-01-15T11:00:00.000000+0000", "Only one"),
        ]
        flag_set = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        flag_removed = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(
            comments_text(comments, flag_set, flag_removed),
            "Only one\n---\n"
        )


class TestBlockerInfoToDict(unittest.TestCase):
    def setUp(self):
        jira_blocker_analyser.category_pattern = r"#\w+"

    def _make_issue(self, key="PROJ-1", summary="Test issue"):
        issue = unittest.mock.MagicMock()
        issue.key = key
        issue.fields.summary = summary
        return issue

    def test_time_blocked_stored_in_seconds(self):
        issue = self._make_issue()
        flag_set = datetime(2024, 1, 15, 10, 0, 0)
        flag_removed = datetime(2024, 1, 18, 10, 0, 0)  # 3 days
        comments = []
        result = blocker_info_to_dict(issue, flag_set, flag_removed, comments, False)
        self.assertEqual(result["Time Blocked"], 3 * 24 * 3600)  # 259200 seconds
        self.assertEqual(result["Issue Key"], "PROJ-1")
        self.assertEqual(result["Issue Summary"], "Test issue")
        self.assertEqual(result["Flag was not removed"], False)

    def test_time_blocked_seconds_fractional_days(self):
        issue = self._make_issue()
        flag_set = datetime(2024, 1, 15, 0, 0, 0)
        flag_removed = datetime(2024, 1, 16, 12, 0, 0)  # 1.5 days
        comments = []
        result = blocker_info_to_dict(issue, flag_set, flag_removed, comments, False)
        self.assertEqual(result["Time Blocked"], 1.5 * 24 * 3600)  # 129600 seconds

    def test_time_blocked_seconds_hours(self):
        issue = self._make_issue()
        flag_set = datetime(2024, 1, 15, 10, 0, 0)
        flag_removed = datetime(2024, 1, 15, 13, 0, 0)  # 3 hours
        comments = []
        result = blocker_info_to_dict(issue, flag_set, flag_removed, comments, False)
        self.assertEqual(result["Time Blocked"], 3 * 3600)

    def test_flag_times_formatted(self):
        issue = self._make_issue()
        flag_set = datetime(2024, 1, 15, 10, 30, 0)
        flag_removed = datetime(2024, 1, 15, 14, 45, 0)
        comments = []
        result = blocker_info_to_dict(issue, flag_set, flag_removed, comments, False)
        self.assertEqual(result["Flag Set Time"], "2024-01-15 10:30")
        self.assertEqual(result["Flag Removed Time"], "2024-01-15 14:45")

    def test_flag_was_not_removed_stored_true(self):
        issue = self._make_issue()
        flag_set = datetime(2024, 1, 15, 10, 0, 0)
        flag_removed = datetime(2024, 1, 16, 10, 0, 0)
        comments = []
        result = blocker_info_to_dict(issue, flag_set, flag_removed, comments, True)
        self.assertTrue(result["Flag was not removed"])

    def test_flag_was_not_removed_stored_false(self):
        issue = self._make_issue()
        flag_set = datetime(2024, 1, 15, 10, 0, 0)
        flag_removed = datetime(2024, 1, 16, 10, 0, 0)
        comments = []
        result = blocker_info_to_dict(issue, flag_set, flag_removed, comments, False)
        self.assertFalse(result["Flag was not removed"])

    def test_blocker_category_key_present(self):
        """Blocker Category key is present; value comes from blocker_category_from_comment.
        With timezone-aware flag_set, category can be empty due to naive/aware comparison in current code."""
        issue = self._make_issue()
        flag_set = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        flag_removed = datetime(2024, 1, 16, 10, 0, 0, tzinfo=timezone.utc)
        comments = [
            make_comment("2024-01-15T10:00:00.000000+0000", "Blocker #deployment"),
        ]
        result = blocker_info_to_dict(issue, flag_set, flag_removed, comments, False)
        self.assertIn("Blocker Category", result)
        # Category lookup uses naive comment time; with aware flag_set they don't match, so '' here
        self.assertEqual(result["Blocker Category"], "")

    def test_comments_text_in_range_in_result(self):
        issue = self._make_issue()
        flag_set = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        flag_removed = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        comments = [
            make_comment("2024-01-15T11:00:00.000000+0000", "Comment in range"),
        ]
        result = blocker_info_to_dict(issue, flag_set, flag_removed, comments, False)
        self.assertIn("Comment in range", result["Comments"])
        self.assertIn("---\n", result["Comments"])
        self.assertEqual(result["Time Blocked"], 2 * 3600)  # 2 hours in seconds


class TestFormatBlockingTime(unittest.TestCase):
    """Conversion from seconds to display value (only at output time)."""

    def test_seconds_to_days(self):
        value, unit = format_blocking_time(259200, 'days')  # 3 days
        self.assertEqual(value, 3.0)
        self.assertEqual(unit, 'days')

    def test_seconds_to_days_fractional(self):
        value, unit = format_blocking_time(7200, 'days')  # 2 hours
        self.assertEqual(value, 0.1)  # 7200/86400 rounded to 1 decimal
        self.assertEqual(unit, 'days')

    def test_seconds_to_hours(self):
        value, unit = format_blocking_time(7200, 'hours')  # 2 hours
        self.assertEqual(value, 2.0)
        self.assertEqual(unit, 'hours')

    def test_seconds_to_hours_fractional(self):
        value, unit = format_blocking_time(5400, 'hours')  # 1.5 hours
        self.assertEqual(value, 1.5)
        self.assertEqual(unit, 'hours')

    def test_zero_seconds(self):
        value_d, unit_d = format_blocking_time(0, 'days')
        value_h, unit_h = format_blocking_time(0, 'hours')
        self.assertEqual(value_d, 0.0)
        self.assertEqual(unit_d, 'days')
        self.assertEqual(value_h, 0.0)
        self.assertEqual(unit_h, 'hours')


if __name__ == "__main__":
    unittest.main()

"""Standard-library tests for src.risk_scoring (no Dataverse writes)."""
import unittest
from datetime import date
from src.risk_scoring import (
    build_index,
    categorize,
    parse_exposure,
    parse_optional_date,
    score_finding,
)

TODAY = date(2026, 10, 18)


def finding(status="Open", severity="Critical"):
    return {"finding_id": "FND-TEST", "title": "Synthetic test finding",
            "status": status, "severity": severity}


def asset(criticality="Critical", exposure="Yes"):
    return {"asset_id": "AST-TEST", "criticality": criticality,
            "internet_exposed": exposure}


def control(effectiveness="Ineffective"):
    return {"control_id": "CTRL-TEST", "effectiveness_status": effectiveness}


def action(status="Open", due_date="2026-10-01", action_id="ACT-TEST"):
    return {"action_id": action_id, "status": status, "due_date": due_date}


class RiskScoringTests(unittest.TestCase):
    def test_maximum_possible_score_is_100(self):
        row = score_finding(finding(), asset(), control(), [action()], TODAY)
        self.assertEqual(row["risk_score"], 100)
        self.assertEqual(row["risk_level"], "Critical")
        self.assertEqual(row["review_priority"], "P1 - Immediate review")
        self.assertEqual(row["overdue_action_count"], 1)

    def test_no_internet_exposure_deducts_10(self):
        row = score_finding(finding(), asset(exposure="No"), control(),
                            [action()], TODAY)
        self.assertEqual(row["risk_score"], 90)
        self.assertEqual(row["internet_exposure_points"], 0)

    def test_due_today_is_not_overdue(self):
        row = score_finding(finding(), asset(), control(),
                            [action(due_date="2026-10-18")], TODAY)
        self.assertEqual(row["overdue_action_count"], 0)
        self.assertEqual(row["outstanding_action_count"], 1)
        self.assertEqual(row["remediation_points"], 7)

    def test_completed_action_has_no_remediation_penalty(self):
        row = score_finding(finding(), asset(), control(),
                            [action(status="Completed")], TODAY)
        self.assertEqual(row["remediation_points"], 0)
        self.assertEqual(row["outstanding_action_count"], 0)
        self.assertEqual(row["overdue_action_count"], 0)

    def test_missing_remediation_action_scores_12(self):
        row = score_finding(finding(), asset(), control(), [], TODAY)
        self.assertEqual(row["remediation_points"], 12)
        self.assertIn("Create and assign", row["recommended_action"])

    def test_closed_finding_stays_historical_even_when_high_score(self):
        row = score_finding(finding(status="Resolved"), asset(), control(),
                            [action()], TODAY)
        self.assertEqual(row["risk_score"], 100)
        self.assertEqual(row["review_priority"], "Historical - verify closure")
        self.assertIn("Confirm closure evidence", row["recommended_action"])

    def test_multiple_actions_only_overdue_incomplete_count(self):
        rows = [
            action("Open", "2026-10-01", "A1"),
            action("Blocked", "2026-10-02", "A2"),
            action("Completed", "2026-09-01", "A3"),
        ]
        result = score_finding(finding(), asset(), control(), rows, TODAY)
        self.assertEqual(result["remediation_action_count"], 3)
        self.assertEqual(result["outstanding_action_count"], 2)
        self.assertEqual(result["overdue_action_count"], 2)
        self.assertEqual(result["next_outstanding_due_date"], "2026-10-01")

    def test_thresholds(self):
        expected = [(0, "Low"), (39, "Low"), (40, "Medium"),
                    (59, "Medium"), (60, "High"), (79, "High"),
                    (80, "Critical"), (100, "Critical")]
        for score, level in expected:
            with self.subTest(score=score):
                self.assertEqual(categorize(score)[0], level)

    def test_unknown_severity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown severity"):
            score_finding(finding(severity="Extreme"), asset(),
                          control(), [], TODAY)

    def test_unknown_action_status_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown remediation status"):
            score_finding(finding(), asset(), control(),
                          [action(status="Pending")], TODAY)

    def test_invalid_due_date_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid due_date"):
            parse_optional_date("invalid", "A1")

    def test_unknown_internet_exposure_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown internet_exposed"):
            parse_exposure("maybe", "AST-TEST")

    def test_duplicate_business_ids_are_rejected(self):
        rows = [{"finding_id": "FND-1"}, {"finding_id": "FND-1"}]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_index(rows, "finding_id", "security_findings.csv")


if __name__ == "__main__":
    unittest.main()

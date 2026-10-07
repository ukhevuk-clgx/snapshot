import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from xml.etree import ElementTree

from cleanup_advisor import advise_cleanup, main
from collectors.custom_fields import CustomFieldsCollector
from collectors.usage import FieldUsageCollector
from collectors.workflows import WorkflowsCollector


def snapshot(version="6", data=None, relations=None, coverage=None):
    return {
        "metadata": {
            "snapshotVersion": version,
            "site": "https://example.atlassian.net",
            "created": "2026-10-07T10:00:00Z",
            "coverage": coverage or {},
        },
        "data": data or {},
        "relations": relations or {},
    }


class FakeClient:
    def get_paginated(self, endpoint, values_key="values", params=None):
        return [{
            "id": "customfield_10000",
            "name": "Référence",
            "lastUsed": {"type": "NOT_TRACKED"},
            "screensCount": 0,
            "contextsCount": 0,
            "projectsCount": 0,
        }]


class Stage7AdvisorTests(unittest.TestCase):
    def test_missing_usage_counts_are_partial_coverage(self):
        coverage = FieldUsageCollector.coverage([{
            "fieldId": "customfield_1", "lastUsedType": "TRACKED",
            "screensCount": 0, "contextsCount": 0,
        }])
        self.assertEqual(coverage["status"], "partial")
        self.assertEqual(coverage["fieldsWithIncompleteCounts"], 1)

    def test_malformed_snapshot_rows_are_rejected(self):
        with self.assertRaises(ValueError):
            advise_cleanup(snapshot(data={"screens": [None]}))

    def test_custom_field_usage_is_preserved_as_evidence_and_coverage(self):
        fields = CustomFieldsCollector(FakeClient()).collect()
        usage = FieldUsageCollector(None).collect(fields)
        coverage = FieldUsageCollector.coverage(usage)
        self.assertEqual(fields[0]["lastUsedType"], "NOT_TRACKED")
        self.assertEqual(usage[0]["fieldId"], "customfield_10000")
        self.assertEqual(coverage["status"], "available")
        self.assertEqual(coverage["untrackedFields"], 1)

    def test_workflow_transition_screen_identifiers_are_collected(self):
        collector = WorkflowsCollector(None)
        row = collector.map_item({
            "id": "workflow-id",
            "name": "Example",
            "transitions": [
                {"id": "1", "screen": {"id": 100}},
                {"id": "2", "actions": [{"screenId": "200"}]},
            ],
        })
        self.assertEqual(row["transitionScreenIds"], ["100", "200"])

    def test_duplicate_statuses_are_scoped_by_category_and_project(self):
        data = {"statuses": [
            {"id": "1", "name": "In Progress", "scopeType": "GLOBAL", "statusCategoryKey": "indeterminate"},
            {"id": "2", "name": " in   progress ", "scopeType": "GLOBAL", "statusCategoryKey": "indeterminate"},
            {"id": "3", "name": "In Progress", "scopeType": "PROJECT", "scopeProjectId": "7", "statusCategoryKey": "indeterminate"},
            {"id": "4", "name": "In Progress", "scopeType": "GLOBAL", "statusCategoryKey": "done"},
        ]}
        report = advise_cleanup(snapshot(data=data))
        candidates = [row for row in report["recommendations"] if row["category"] == "duplicate_status_candidate"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["target"], "1,2")
        self.assertEqual(candidates[0]["action"], "review_only")

    def test_priorities_and_custom_field_candidate_are_cautious(self):
        data = {
            "priorities": [{"id": "1", "name": "High"}, {"id": "2", "name": " high "}],
            "customFields": [{
                "id": "customfield_1", "name": "Candidate", "isLocked": False, "isManaged": False,
            }],
            "fieldUsage": [{
                "fieldId": "customfield_1", "lastUsedType": "NOT_TRACKED",
                "screensCount": 0, "contextsCount": 0, "projectsCount": 0,
            }],
        }
        report = advise_cleanup(snapshot(data=data, coverage={"customFieldUsage": {"status": "available"}}))
        categories = [row["category"] for row in report["recommendations"]]
        self.assertIn("duplicate_priority_candidate", categories)
        field_advice = next(row for row in report["recommendations"] if row["category"] == "custom_field_review_candidate")
        self.assertEqual(field_advice["confidence"], "low")
        self.assertIn("does not mean the field has never been used", " ".join(field_advice["limitations"]))
        data["customFields"][0]["isLocked"] = None
        protected_report = advise_cleanup(snapshot(
            data=data, coverage={"customFieldUsage": {"status": "available"}},
        ))
        self.assertNotIn(
            "custom_field_review_candidate",
            {row["category"] for row in protected_report["recommendations"]},
        )

    def test_orphan_candidates_require_stage7_and_are_not_deletion_advice(self):
        data = {
            "workflows": [{"id": "workflow-1", "name": "Unused", "isActive": False}],
            "workflowSchemes": [{"id": "1"}],
            "screens": [{"id": "9", "name": "Unlinked"}],
            "screenSchemes": [{"id": "1"}],
        }
        report = advise_cleanup(snapshot(
            data=data,
            relations={"workflowSchemeMappings": []},
            coverage={
                "screenReferences": {"status": "partial"},
                "workflowScreenReferences": {"status": "best_effort"},
            },
        ))
        categories = {row["category"] for row in report["recommendations"]}
        self.assertIn("workflow_review_candidate", categories)
        screen = next(row for row in report["recommendations"] if row["category"] == "screen_review_candidate")
        self.assertEqual(screen["action"], "review_only")
        self.assertTrue(any("not proof" in item for item in screen["limitations"]))

        legacy = advise_cleanup(snapshot(
            version="5", data=data, relations={"workflowSchemeMappings": []},
        ))
        legacy_categories = {row["category"] for row in legacy["recommendations"]}
        self.assertNotIn("workflow_review_candidate", legacy_categories)
        self.assertNotIn("screen_review_candidate", legacy_categories)
        self.assertTrue(any("insufficient" in item for item in legacy["coverage"]["globalLimitations"]))
        self.assertEqual(legacy["coverage"]["relations"]["workflowSchemeMappings"]["status"], "insufficient_legacy_snapshot")

        undocumented = advise_cleanup(snapshot(data=data))
        self.assertNotIn(
            "screen_review_candidate",
            {row["category"] for row in undocumented["recommendations"]},
        )

    def test_governance_risks_distinguish_anonymous_and_authenticated(self):
        relations = {
            "permissionSchemeGrants": [
                {"permissionSchemeId": "10", "grantId": "1", "permission": "BROWSE_PROJECTS", "holderType": "anyone"},
                {"permissionSchemeId": "11", "grantId": "2", "permission": "BROWSE_PROJECTS", "holderType": "group", "holderParameter": "jira-software-users"},
            ],
            "projectPermissionSchemeMappings": [
                {"permissionSchemeId": "10", "projectKey": "PUB"},
            ],
        }
        report = advise_cleanup(snapshot(relations=relations))
        anonymous = next(row for row in report["recommendations"] if row["category"] == "anonymous_permission_grant")
        broad = next(row for row in report["recommendations"] if row["category"] == "broad_authenticated_group_grant")
        self.assertEqual(anonymous["severity"], "high")
        self.assertEqual(anonymous["evidence"]["projectsUsingScheme"][0]["projectKey"], "PUB")
        self.assertIn("do not imply anonymous", " ".join(broad["limitations"]))
        self.assertIn("unknown", broad["evidence"]["projectAssignmentEvidence"])

    def test_cli_writes_utf8_json_and_formula_safe_excel(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "cleanup_advisor.file_timestamp", return_value="20261007_120000",
        ):
            folder = Path(directory)
            source = folder / "snapshot.json"
            source.write_text(json.dumps(snapshot(data={
                "priorities": [{"id": "1", "name": "=1+1"}, {"id": "2", "name": "=1+1"}],
            })), encoding="utf-8")
            report = main(["--input", str(source), "--output-dir", str(folder)])
            json_path = folder / "cleanup_advice_20261007_120000.json"
            excel_path = folder / "cleanup_advice_20261007_120000.xlsx"
            self.assertTrue(json_path.exists())
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), report)
            self.assertIn("example.atlassian.net", json_path.read_text(encoding="utf-8"))
            with zipfile.ZipFile(excel_path) as archive:
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for name in archive.namelist():
                    if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                        sheet = ElementTree.fromstring(archive.read(name))
                        self.assertEqual(sheet.findall(".//s:f", ns), [])
                shared = archive.read("xl/sharedStrings.xml").decode("utf-8")
                self.assertIn("=1+1", shared)

    def test_default_input_path_is_relative_to_script(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "cleanup_advisor.__file__", str(Path(directory) / "cleanup_advisor.py"),
        ), patch("cleanup_advisor.file_timestamp", return_value="default"):
            folder = Path(directory) / "snapshots"
            folder.mkdir()
            (folder / "snapshot_b.json").write_text(json.dumps(snapshot()), encoding="utf-8")
            report = main([])
            self.assertEqual(report["metadata"]["snapshotVersion"], "6")
            self.assertTrue((folder / "cleanup_advice_default.xlsx").exists())

    def test_positional_input_path_is_supported(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "cleanup_advisor.file_timestamp", return_value="positional",
        ):
            folder = Path(directory)
            source = folder / "input.json"
            source.write_text(json.dumps(snapshot()), encoding="utf-8")
            report = main([str(source), "--output-dir", str(folder)])
            self.assertEqual(report["summary"]["recommendationCount"], 0)
            self.assertTrue((folder / "cleanup_advice_positional.json").exists())

    def test_output_collision_and_export_failure_are_reported_without_partial_reports(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "cleanup_advisor.file_timestamp", return_value="failure",
        ):
            folder = Path(directory)
            source = folder / "input.json"
            source.write_text(json.dumps(snapshot()), encoding="utf-8")
            collision = folder / "cleanup_advice_failure.json"
            collision.write_text("preserve", encoding="utf-8")
            with self.assertRaises(SystemExit) as error:
                main([str(source), "--output-dir", str(folder)])
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(collision.read_text(encoding="utf-8"), "preserve")

            collision.unlink()
            with patch("cleanup_advisor.export_advice_excel", side_effect=OSError("disk unavailable")):
                with self.assertRaises(SystemExit) as error:
                    main([str(source), "--output-dir", str(folder)])
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(list(folder.glob("cleanup_advice_failure.*")), [])


if __name__ == "__main__":
    unittest.main()

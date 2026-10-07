import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from xml.etree import ElementTree

from compare_snapshots import main
from diff_engine import RELATION_KEYS, compare_snapshots, load_snapshot
from output.excel_exporter import SHEETS


def snapshot(data=None, relations=None):
    return {
        "metadata": {
            "site": "https://example.atlassian.net/", "snapshotVersion": "5",
            "created": "2026-10-07T10:00:00Z", "capabilities": {"fieldSchemesApi": True},
        },
        "data": data or {}, "relations": relations or {},
    }


class DiffEngineTests(unittest.TestCase):
    def test_all_inventory_collections_are_compared(self):
        data = {key: [{"id": "1", "name": key}] for _, key in SHEETS}
        data["workflows"][0]["id"] = {"entityId": "uuid", "name": "workflows"}
        before = snapshot({key: [] for key in data})
        after = snapshot(data)
        report = compare_snapshots(before, after)
        self.assertEqual(report["totals"]["objects"]["added"], len(SHEETS))
        self.assertEqual(set(report["objects"]), set(data))
        self.assertTrue(all(value["status"] == "compared" for value in report["summary"]["objects"].values()))

    def test_added_removed_changed_and_same_name_new_id(self):
        before = snapshot({"statuses": [
            {"id": 1, "name": "Open"}, {"id": 2, "name": "Old"}, {"id": 3, "name": "Keep"},
        ]})
        after = snapshot({"statuses": [
            {"id": "1", "name": "Renamed"}, {"id": "3", "name": "Keep"}, {"id": 4, "name": "Keep"},
        ]})
        report = compare_snapshots(before, after)
        changes = report["objects"]["statuses"]
        self.assertEqual(report["totals"]["objects"], {"added": 1, "removed": 1, "changed": 1})
        self.assertEqual(changes["added"][0]["identity"], {"id": "4"})
        self.assertEqual(changes["removed"][0]["identity"], {"id": "2"})
        self.assertEqual(list(changes["changed"][0]["fields"]), ["name"])
        self.assertEqual(changes["changed"][0]["fields"]["name"]["before"], "Open")

    def test_order_ids_metadata_and_nested_key_order_do_not_change_objects(self):
        before = snapshot({"screens": [
            {"id": 1, "name": "A", "nested": {"x": 1, "projectId": 2}},
            {"id": 3, "name": "B"},
        ]})
        original = copy.deepcopy(before)
        after = snapshot({"screens": [
            {"name": "B", "id": "3"},
            {"nested": {"projectId": "2", "x": 1}, "name": "A", "id": "1"},
        ]})
        after["metadata"]["created"] = "2026-10-08T10:00:00Z"
        after["metadata"]["site"] = "https://EXAMPLE.atlassian.net"
        report = compare_snapshots(before, after)
        self.assertEqual(report["totals"]["objects"], {"added": 0, "removed": 0, "changed": 0})
        self.assertEqual(before, original)

    def test_null_missing_false_and_number_are_distinct(self):
        before = snapshot({"projects": [{"id": 1, "missing": None, "flag": False}]})
        after = snapshot({"projects": [{"id": 1, "flag": 0, "new": None}]})
        fields = compare_snapshots(before, after)["objects"]["projects"]["changed"][0]["fields"]
        self.assertEqual(set(fields), {"missing", "flag", "new"})
        self.assertTrue(fields["missing"]["beforePresent"])
        self.assertFalse(fields["missing"]["afterPresent"])
        self.assertTrue(fields["new"]["afterPresent"])

    def test_workflow_entity_id_survives_rename(self):
        before = snapshot({"workflows": [{"id": {"entityId": "uuid", "name": "Old"}, "name": "Old"}]})
        after = snapshot({"workflows": [{"id": {"entityId": "uuid", "name": "New"}, "name": "New"}]})
        changes = compare_snapshots(before, after)["objects"]["workflows"]
        self.assertEqual(len(changes["changed"]), 1)
        self.assertEqual(changes["added"], [])
        self.assertEqual(changes["removed"], [])

    def test_legacy_workflow_fallback_warns_and_distinguishes_draft(self):
        rows = [{"id": {"name": "Workflow", "draft": draft}} for draft in (False, True)]
        report = compare_snapshots(snapshot({"workflows": rows}), snapshot({"workflows": rows[::-1]}))
        self.assertEqual(report["totals"]["objects"]["changed"], 0)
        self.assertTrue(any("Legacy workflows" in warning for warning in report["warnings"]))

    def test_all_relation_keys_preserve_identity_when_target_changes(self):
        for name, keys in RELATION_KEYS.items():
            with self.subTest(name=name):
                old = {key: i + 1 for i, key in enumerate(keys)}
                new = {key: str(i + 1) for i, key in enumerate(keys)}
                old["description"] = "Before"
                new["description"] = "After"
                report = compare_snapshots(snapshot(relations={name: [old]}), snapshot(relations={name: [new]}))
                self.assertEqual(report["totals"]["relations"], {"added": 0, "removed": 0, "changed": 1})

    def test_relation_addition_removal_and_default_mapping(self):
        before = snapshot(relations={"workflowSchemeMappings": [
            {"workflowSchemeId": 1, "issueTypeId": None, "workflowName": "Default"},
            {"workflowSchemeId": 1, "issueTypeId": 2, "workflowName": "Old"},
        ]})
        after = snapshot(relations={"workflowSchemeMappings": [
            {"workflowSchemeId": "1", "issueTypeId": None, "workflowName": "New default"},
            {"workflowSchemeId": 1, "issueTypeId": 3, "workflowName": "New"},
        ]})
        self.assertEqual(compare_snapshots(before, after)["totals"]["relations"],
                         {"added": 1, "removed": 1, "changed": 1})

    def test_archiving_does_not_report_governance_mapping_removal(self):
        before = snapshot({"projects": [{"id": 1, "archived": False}]},
                          {"projectPermissionSchemeMappings": [{"projectId": 1, "permissionSchemeId": 2}]})
        after = snapshot({"projects": [{"id": "1", "archived": True}]},
                         {"projectPermissionSchemeMappings": []})
        report = compare_snapshots(before, after)
        self.assertEqual(report["totals"]["relations"]["removed"], 0)
        self.assertEqual(report["totals"]["objects"]["changed"], 1)
        self.assertTrue(any("archived" in text for text in report["warnings"]))
        reverse = compare_snapshots(after, before)
        self.assertEqual(reverse["totals"]["relations"]["added"], 0)

    def test_missing_collection_and_unavailable_api_are_skipped(self):
        before = snapshot({"projects": [{"id": 1}], "fieldSchemes": [{"id": 2}]})
        after = snapshot({"fieldSchemes": []})
        after["metadata"]["capabilities"]["fieldSchemesApi"] = False
        report = compare_snapshots(before, after)
        self.assertEqual(report["summary"]["objects"]["projects"]["status"], "skipped")
        self.assertEqual(report["summary"]["objects"]["fieldSchemes"]["status"], "skipped")
        self.assertEqual(report["totals"]["objects"]["removed"], 0)

    def test_different_site_is_rejected(self):
        after = snapshot()
        after["metadata"]["site"] = "https://different.atlassian.net"
        with self.assertRaisesRegex(ValueError, "same Jira site"):
            compare_snapshots(snapshot(), after)

    def test_duplicate_or_invalid_identity_is_rejected(self):
        for rows in ([{"id": 1}, {"id": "1"}], [{"name": "No ID"}], [{"id": True}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                compare_snapshots(snapshot({"screens": rows}), snapshot({"screens": []}))
        with self.assertRaisesRegex(ValueError, "Unsupported relation"):
            compare_snapshots(snapshot(relations={"unknown": [{"id": 1}]}),
                              snapshot(relations={"unknown": []}))

    def test_malformed_snapshots_are_rejected(self):
        for payload in ([], {}, {"metadata": {}, "data": [], "relations": {}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                compare_snapshots(payload, snapshot())
        invalid = snapshot()
        invalid["data"]["projects"] = [None]
        with self.assertRaises(ValueError):
            compare_snapshots(invalid, snapshot())


class DiffReportTests(unittest.TestCase):
    def test_no_arguments_use_default_files_relative_to_script(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "compare_snapshots.__file__", str(Path(directory) / "compare_snapshots.py"),
        ), patch("compare_snapshots.file_timestamp", return_value="defaults"):
            folder = Path(directory) / "snapshots"
            folder.mkdir()
            for name in ("snapshot_a.json", "snapshot_b.json"):
                with (folder / name).open("w", encoding="utf-8") as stream:
                    json.dump(snapshot({"screens": [{"id": 1}]}), stream)
            report = main([])
            self.assertEqual(report["totals"]["objects"], {"added": 0, "removed": 0, "changed": 0})
            self.assertEqual(report["metadata"]["sourceA"], str((folder / "snapshot_a.json").resolve()))
            self.assertTrue((folder / "snapshot_diff_defaults.xlsx").exists())

    def test_one_argument_is_rejected(self):
        with self.assertRaises(SystemExit) as error:
            main(["before.json.gz"])
        self.assertEqual(error.exception.code, 2)

    def test_cli_exports_complete_json_and_excel_without_formulas(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "compare_snapshots.file_timestamp", return_value="20261007_120000",
        ):
            folder = Path(directory)
            before = snapshot({"screens": [{"id": 1, "name": "Old"}]})
            after = snapshot({"screens": [{"id": 1, "name": "New"}, {"id": 2, "name": "=1+1"}]})
            a, b = folder / "before.json", folder / "after.json.gz"
            a.write_text(json.dumps(before), encoding="utf-8")
            with gzip.open(b, "wt", encoding="utf-8") as stream:
                json.dump(after, stream)
            self.assertEqual(load_snapshot(a), before)
            self.assertEqual(load_snapshot(b), after)
            report = main([str(a), str(b), "--output-dir", str(folder)])
            outputs = list(folder.glob("snapshot_diff_*.json"))
            self.assertEqual(len(outputs), 1)
            with outputs[0].open("r", encoding="utf-8") as stream:
                self.assertEqual(json.load(stream), report)
            excel = next(folder.glob("snapshot_diff_*.xlsx"))
            with zipfile.ZipFile(excel) as archive:
                workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                names = [sheet.attrib["name"] for sheet in workbook.findall("s:sheets/s:sheet", ns)]
                self.assertEqual(names, [
                    "Summary", "Metadata", "Warnings", "Objects Added", "Objects Removed",
                    "Objects Changed", "Relations Added", "Relations Removed", "Relations Changed",
                ])
                for path in archive.namelist():
                    if path.startswith("xl/worksheets/sheet") and path.endswith(".xml"):
                        sheet = ElementTree.fromstring(archive.read(path))
                        self.assertEqual(sheet.findall(".//s:f", ns), [])
                shared = archive.read("xl/sharedStrings.xml").decode("utf-8")
                self.assertIn("=1+1", shared)
                self.assertIn("New", shared)
            with self.assertRaises(FileExistsError):
                main([str(a), str(b), "--output-dir", str(folder)])

    def test_invalid_cli_input_returns_nonzero(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{}", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(root / "compare_snapshots.py"), str(path), str(path)],
                capture_output=True, text=True, cwd=root,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("error:", result.stderr)
            self.assertEqual(list(Path(directory).glob("snapshot_diff_*")), [])


if __name__ == "__main__":
    unittest.main()

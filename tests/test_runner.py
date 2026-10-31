import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        self.mission = {"mission_id": "TEST-1", "site": "SYNTHETIC-A",
                        "requirements": ["power", "connectivity", "access"],
                        "evidence_files": ["primary.json"], "supplemental_file": None,
                        "max_recovery_lookups": 1}
        self.records = [{"record_id": "R-" + key, "site": "SYNTHETIC-A",
                         "requirement": key, "ready": True}
                        for key in self.mission["requirements"]]

    def execute(self, mission=None, records=None, supplemental=None):
        (self.root / "mission.json").write_text(json.dumps(self.mission if mission is None else mission))
        (self.root / "primary.json").write_text(json.dumps({"records": self.records if records is None else records}))
        if supplemental is not None:
            (self.root / "supplemental.json").write_text(json.dumps({"records": supplemental}))
        return runner.run(self.root / "mission.json")

    def test_five_acceptance_fixtures(self):
        expected = {"complete": ("READY", 0), "missing": ("BLOCKED", 0),
                    "conflict": ("REVIEW_REQUIRED", 0), "recovery": ("READY", 1),
                    "invalid": ("INVALID_INPUT", 0)}
        for name, (state, recoveries) in expected.items():
            with self.subTest(scenario=name):
                report = runner.run(Path(runner.__file__).parent / "fixtures" / name / "mission.json")
                self.assertEqual(report["disposition"], state)
                self.assertEqual(report["counts"]["recovery_lookups"], recoveries)
                self.assertEqual(report["validation"], "NOT_COMPLETED" if name == "invalid" else "PASSED")
                if name == "invalid":
                    self.assertEqual(report["counts"]["evidence_file_reads"], 0)

    def test_negative_evidence_blocks_readiness(self):
        self.records[0]["ready"] = False
        self.assertEqual(self.execute()["disposition"], "BLOCKED")

    def test_conflict_preserves_both_references(self):
        self.records.append(dict(self.records[0], record_id="R-conflict", ready=False))
        result = self.execute()
        self.assertEqual(result["disposition"], "REVIEW_REQUIRED")
        self.assertEqual({row["record_id"] for row in result["requirements"][0]["evidence"]}, {"R-power", "R-conflict"})

    def test_wrong_site_cannot_satisfy_requirement(self):
        self.records[1]["site"] = "OTHER-SITE"
        self.assertEqual(self.execute()["disposition"], "BLOCKED")

    def test_recovery_does_not_repeat_when_gap_remains(self):
        self.mission["supplemental_file"] = "supplemental.json"
        result = self.execute(records=self.records[:1], supplemental=[])
        self.assertEqual(result["disposition"], "BLOCKED")
        self.assertEqual(result["counts"]["recovery_lookups"], 1)
        self.assertEqual(result["counts"]["evidence_file_reads"], 2)

    def test_zero_budget_prevents_supplement_read(self):
        self.mission.update(supplemental_file="absent.json", max_recovery_lookups=0)
        result = self.execute(records=self.records[:1])
        self.assertEqual(result["disposition"], "BLOCKED")
        self.assertEqual(result["counts"]["evidence_file_reads"], 1)

    def test_complete_primary_does_not_read_supplement(self):
        self.mission["supplemental_file"] = "absent.json"
        self.assertEqual(self.execute()["disposition"], "READY")

    def test_duplicate_record_ids_rejected(self):
        self.assertEqual(self.execute(records=self.records + [self.records[0]])["disposition"], "INVALID_INPUT")

    def test_string_boolean_rejected(self):
        self.records[0]["ready"] = "true"
        self.assertEqual(self.execute()["disposition"], "INVALID_INPUT")

    def test_path_escape_stops_before_evidence_read(self):
        self.mission["evidence_files"] = ["../outside.json"]
        report = self.execute()
        self.assertEqual(report["disposition"], "INVALID_INPUT")
        self.assertEqual(report["counts"]["evidence_file_reads"], 0)

    def test_symlink_rejected(self):
        self.execute()
        (self.root / "alias.json").symlink_to(self.root / "primary.json")
        self.mission["evidence_files"] = ["alias.json"]
        self.assertEqual(self.execute()["disposition"], "INVALID_INPUT")

    def test_missing_file_fails_closed(self):
        self.mission["evidence_files"] = ["absent.json"]
        self.assertEqual(self.execute()["disposition"], "INVALID_INPUT")

    def test_duplicate_json_keys_rejected(self):
        path = self.root / "mission.json"
        path.write_text('{"mission_id":"one","mission_id":"two"}')
        self.assertEqual(runner.run(path)["disposition"], "INVALID_INPUT")

    def test_oversized_input_rejected(self):
        path = self.root / "mission.json"
        path.write_bytes(b" " * (runner.MAX_BYTES + 1))
        self.assertEqual(runner.run(path)["disposition"], "INVALID_INPUT")

    def test_repeated_runs_preserve_decision_and_input_hashes(self):
        first = self.execute()
        second = self.execute()
        for field in ("disposition", "inputs", "requirements", "counts"):
            self.assertEqual(first[field], second[field])

    def test_forged_evidence_reference_rejected(self):
        report = self.execute()
        rows = [dict(row, source_file="primary.json") for row in self.records]
        forged = copy.deepcopy(report["requirements"])
        forged[0]["evidence"][0]["record_id"] = "invented"
        with self.assertRaises(runner.InvalidInput):
            runner.validate_result(self.mission, rows, forged, report)


if __name__ == "__main__":
    unittest.main()

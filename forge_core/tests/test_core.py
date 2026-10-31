import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("forge_core_under_test", str(Path(__file__).resolve().parents[1] / "core.py"))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "brief.json"
        self.brief = json.loads((core.HOME / "briefs" / "readiness.json").read_text())

    def dispatch(self, brief=None):
        self.path.write_text(json.dumps(self.brief if brief is None else brief))
        return core.execute(self.path)

    def result_for(self, scenario):
        return json.loads(core.launch(scenario, 5).stdout)

    def test_five_mission_outcomes(self):
        states = {"complete": "READY_FOR_REVIEW", "missing": "BLOCKED",
                  "conflict": "REVIEW_REQUIRED", "recovery": "READY_FOR_REVIEW", "invalid": "INVALID_INPUT"}
        for scenario, expected in states.items():
            with self.subTest(scenario=scenario):
                self.brief.update(scenario=scenario, expected_mission_id="WR-" + scenario.upper())
                report = self.dispatch()
                self.assertEqual(report["execution_state"], "COMPLETED")
                self.assertEqual(report["reconciliation_state"], "ACCEPTED")
                self.assertEqual(report["mission_state"], expected)
                self.assertEqual(report["dispatch_attempts"], 1)
                self.assertEqual(report["human_decision"], "PENDING_ACTUAL")
                self.assertEqual(report["requested_end_state_met"], expected == "READY_FOR_REVIEW")

    def test_unknown_executor_never_dispatched(self):
        self.brief["executor"] = "unapproved"
        with patch.object(core, "launch") as launcher:
            report = self.dispatch()
            launcher.assert_not_called()
        self.assertEqual(report["mission_state"], "INVALID_BRIEF")

    def test_extra_dispatch_attempt_rejected(self):
        self.brief["limits"]["dispatch_attempts"] = 2
        self.assertEqual(self.dispatch()["dispatch_attempts"], 0)

    def test_boolean_limit_rejected(self):
        self.brief["limits"]["dispatch_attempts"] = True
        self.assertEqual(self.dispatch()["dispatch_attempts"], 0)

    def test_arbitrary_path_scenario_rejected(self):
        self.brief["scenario"] = "../elsewhere"
        self.assertEqual(self.dispatch()["dispatch_attempts"], 0)

    def test_executor_identity_mismatch_prevents_dispatch(self):
        with patch.object(core, "EXECUTOR_SHA256", "0" * 64), patch.object(core, "launch") as launcher:
            report = self.dispatch()
            launcher.assert_not_called()
        self.assertEqual(report["dispatch_attempts"], 0)

    def test_timeout_does_not_retry(self):
        with patch.object(core, "launch", side_effect=subprocess.TimeoutExpired("executor", 5)) as launcher:
            report = self.dispatch()
            self.assertEqual(launcher.call_count, 1)
        self.assertEqual(report["execution_state"], "TIMED_OUT")
        self.assertEqual(report["mission_state"], "EXECUTION_FAILED")

    def test_process_failure_is_not_mission_success(self):
        with patch.object(core, "launch", return_value=subprocess.CompletedProcess([], 1, "", "failure")):
            report = self.dispatch()
        self.assertEqual(report["execution_state"], "FAILED")
        self.assertFalse(report["requested_end_state_met"])

    def test_zero_exit_with_bad_json_is_rejected(self):
        with patch.object(core, "launch", return_value=subprocess.CompletedProcess([], 0, "not JSON", "")):
            report = self.dispatch()
        self.assertEqual(report["execution_state"], "COMPLETED")
        self.assertEqual(report["reconciliation_state"], "REJECTED")

    def test_wrong_mission_result_is_rejected(self):
        result = self.result_for("recovery")
        result["mission_id"] = "WR-OTHER"
        with patch.object(core, "launch", return_value=subprocess.CompletedProcess([], 0, json.dumps(result), "")):
            report = self.dispatch()
        self.assertEqual(report["reconciliation_state"], "REJECTED")

    def test_forged_input_hash_is_rejected(self):
        result = self.result_for("recovery")
        result["inputs"][0]["sha256"] = "0" * 64
        with patch.object(core, "launch", return_value=subprocess.CompletedProcess([], 0, json.dumps(result), "")):
            report = self.dispatch()
        self.assertEqual(report["reconciliation_state"], "REJECTED")

    def test_forged_ready_disposition_is_rejected(self):
        self.brief.update(scenario="missing", expected_mission_id="WR-MISSING")
        result = self.result_for("missing")
        result["disposition"] = "READY"
        with patch.object(core, "launch", return_value=subprocess.CompletedProcess([], 0, json.dumps(result), "")):
            report = self.dispatch()
        self.assertEqual(report["reconciliation_state"], "REJECTED")

    def test_forged_evidence_reference_is_rejected(self):
        result = self.result_for("recovery")
        result["requirements"][0]["evidence"][0]["record_id"] = "invented"
        with patch.object(core, "launch", return_value=subprocess.CompletedProcess([], 0, json.dumps(result), "")):
            report = self.dispatch()
        self.assertEqual(report["reconciliation_state"], "REJECTED")

    def test_changed_input_snapshot_is_rejected(self):
        initial = core.snapshot("recovery")
        changed = dict(initial, **{"primary.json": "0" * 64})
        response = subprocess.CompletedProcess([], 0, json.dumps(self.result_for("recovery")), "")
        with patch.object(core, "snapshot", side_effect=[initial, changed]), patch.object(core, "launch", return_value=response):
            report = self.dispatch()
        self.assertEqual(report["reconciliation_state"], "REJECTED")

    def test_duplicate_brief_keys_rejected(self):
        self.path.write_text('{"brief_id":"one","brief_id":"two"}')
        self.assertEqual(core.execute(self.path)["dispatch_attempts"], 0)


if __name__ == "__main__":
    unittest.main()

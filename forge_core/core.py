"""FORGE Core v0.1: one human-directed brief, one executor, one reconciliation."""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HOME = Path(__file__).resolve().parent
EXECUTOR = HOME.parent / "runner.py"
EXECUTOR_SHA256 = "26fa3707f48fea4861372c1491a09412a73543ec632eacd71f62e56baa40aeef"
SCENARIOS = {"complete", "missing", "conflict", "recovery", "invalid"}
STATES = {"READY", "BLOCKED", "REVIEW_REQUIRED", "INVALID_INPUT"}
MAX_BYTES = 65536


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def object_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "Duplicate JSON key")
        value[key] = item
    return value


def parse(raw):
    return json.loads(raw, object_pairs_hook=object_pairs)


def read_file(path):
    require(path.is_file() and not path.is_symlink(), "Expected regular input file")
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, "Input exceeds 64 KiB")
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def bounded_text(value):
    return isinstance(value, str) and 0 < len(value) <= 240 and not any(
        ord(char) < 32 or ord(char) == 127 for char in value)


def validate_brief(brief):
    fields = {"schema_version", "brief_id", "objective", "executor", "scenario",
              "expected_mission_id", "expected_site", "limits", "requested_end_state"}
    require(isinstance(brief, dict) and set(brief) == fields, "Brief fields do not match contract")
    require(brief["schema_version"] == "1.0", "Unsupported brief version")
    require(bounded_text(brief["brief_id"]) and bounded_text(brief["objective"]), "Invalid brief identity or objective")
    require(brief["executor"] == "white_rabbit_v0_1", "Executor is not allowlisted")
    require(isinstance(brief["scenario"], str) and brief["scenario"] in SCENARIOS, "Scenario is not allowlisted")
    require(brief["expected_mission_id"] == "WR-" + brief["scenario"].upper(), "Mission identity does not match scenario")
    require(brief["expected_site"] == "SYNTHETIC-ALPHA", "Unexpected site")
    limits = brief["limits"]
    require(isinstance(limits, dict) and set(limits) == {"dispatch_attempts", "timeout_seconds"}, "Invalid limits")
    require(type(limits["dispatch_attempts"]) is int and limits["dispatch_attempts"] == 1,
            "Exactly one dispatch is permitted")
    require(type(limits["timeout_seconds"]) is int and limits["timeout_seconds"] == 5,
            "Executor timeout must be five seconds")
    require(brief["requested_end_state"] == "READY_FOR_REVIEW", "Unsupported end state")


def snapshot(scenario):
    root = EXECUTOR.parent / "fixtures" / scenario
    require(not root.is_symlink() and not root.parent.is_symlink(), "Symlink fixture directory prohibited")
    names = ["mission.json", "primary.json"]
    if scenario == "recovery":
        names.append("supplemental.json")
    return {name: digest(read_file(root / name)) for name in names}


def launch(scenario, timeout):
    return subprocess.run([sys.executable, "-B", str(HOME / "core.py"), "--worker", scenario],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                          timeout=timeout, check=False)


def worker(scenario):
    require(EXECUTOR.is_file() and not EXECUTOR.is_symlink(), "Expected sibling executor not found")
    require(digest(EXECUTOR.read_bytes()) == EXECUTOR_SHA256, "Executor hash does not match accepted baseline")
    spec = importlib.util.spec_from_file_location("forge_white_rabbit_executor", str(EXECUTOR))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run(EXECUTOR.parent / "fixtures" / scenario / "mission.json")
    print(json.dumps(result))


def reconcile(brief, result, initial_snapshot):
    require(isinstance(result, dict), "Executor result must be an object")
    require(result.get("schema_version") == "1.0", "Unexpected executor schema")
    state = result.get("disposition")
    require(isinstance(state, str) and state in STATES, "Unknown executor disposition")
    inputs = result.get("inputs")
    require(isinstance(inputs, list) and 1 <= len(inputs) <= 3, "Invalid input receipt")
    observed = {}
    for item in inputs:
        require(isinstance(item, dict) and set(item) == {"role", "file", "sha256"}, "Invalid input receipt entry")
        name = item["file"]
        require(isinstance(name, str) and name in initial_snapshot and name not in observed, "Unexpected or duplicate input receipt")
        require(item["sha256"] == initial_snapshot[name], "Input receipt hash mismatch")
        require(item["role"] == ("mission" if name == "mission.json" else "evidence"), "Input role mismatch")
        observed[name] = item["sha256"]
    require("mission.json" in observed, "Missing mission receipt")
    counts = result.get("counts")
    require(isinstance(counts, dict) and set(counts) == {"evidence_file_reads", "records_examined", "recovery_lookups"}, "Invalid executor counts")
    require(all(type(value) is int and value >= 0 for value in counts.values()), "Executor counts must be nonnegative integers")
    require(counts["recovery_lookups"] <= 1 and counts["evidence_file_reads"] <= 3, "Executor exceeded input or recovery limit")
    require(isinstance(result.get("issues"), list) and all(isinstance(item, str) for item in result["issues"]), "Invalid issue list")
    if state == "INVALID_INPUT":
        require(result.get("validation") == "NOT_COMPLETED" and result.get("requirements") == [], "Invalid input was promoted to validated evaluation")
        require(brief["scenario"] == "invalid" and counts["evidence_file_reads"] == 0
                and counts["recovery_lookups"] == 0, "Unexpected invalid-input result")
        return state
    require(result.get("mission_id") == brief["expected_mission_id"], "Executor mission identity mismatch")
    require(result.get("site") == brief["expected_site"], "Executor site mismatch")
    require(result.get("validation") == "PASSED", "Executor validation did not pass")
    require("primary.json" in observed, "Missing primary evidence receipt")
    require(counts["evidence_file_reads"] == len(observed) - 1, "Evidence read count mismatch")
    require(counts["recovery_lookups"] == int("supplemental.json" in observed), "Recovery receipt mismatch")
    root = EXECUTOR.parent / "fixtures" / brief["scenario"]
    mission = parse(read_file(root / "mission.json"))
    results = result.get("requirements")
    require(isinstance(results, list) and len(results) == len(mission["requirements"]), "Requirement coverage mismatch")
    source_records = []
    for name in observed:
        if name != "mission.json":
            for record in parse(read_file(root / name))["records"]:
                source_records.append(dict(record, source_file=name))
    states = []
    for expected, row in zip(mission["requirements"], results):
        require(isinstance(row, dict) and set(row) == {"requirement", "state", "evidence"}
                and row["requirement"] == expected, "Unexpected requirement result")
        matching = [record for record in source_records if record["site"] == brief["expected_site"]
                    and record["requirement"] == expected]
        references = [{"record_id": record["record_id"], "source_file": record["source_file"],
                       "ready": record["ready"]} for record in matching]
        require(row["evidence"] == references, "Evidence references differ from source records")
        values = {record["ready"] for record in matching}
        expected_state = ("MISSING" if not matching else "CONFLICT" if len(values) > 1
                          else "SATISFIED" if values == {True} else "NOT_READY")
        require(row["state"] == expected_state, "Requirement state differs from evidence")
        states.append(expected_state)
    expected_disposition = ("REVIEW_REQUIRED" if "CONFLICT" in states else "READY"
                            if all(value == "SATISFIED" for value in states) else "BLOCKED")
    require(state == expected_disposition, "Disposition differs from requirement evidence")
    return state


def execute(brief_path):
    start = time.perf_counter()
    record = {"schema_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
              "brief_id": None, "brief_sha256": None, "objective": None,
              "scenario": None, "permitted_source": None, "requested_end_state": None,
              "executor": "white_rabbit_v0_1", "executor_sha256": EXECUTOR_SHA256,
              "input_snapshot": {}, "dispatch_attempts": 0,
              "execution_state": "NOT_STARTED", "reconciliation_state": "NOT_PERFORMED",
              "mission_state": "INVALID_BRIEF", "requested_end_state_met": False,
              "human_decision": "PENDING_ACTUAL", "issues": [], "executor_result": None}
    try:
        raw = read_file(Path(brief_path))
        record["brief_sha256"] = digest(raw)
        brief = parse(raw)
        validate_brief(brief)
        record.update(brief_id=brief["brief_id"], objective=brief["objective"],
                      scenario=brief["scenario"],
                      permitted_source="fixtures/" + brief["scenario"],
                      requested_end_state=brief["requested_end_state"], mission_state="PRECHECK_FAILED")
        require(EXECUTOR.is_file() and not EXECUTOR.is_symlink(), "Expected sibling WHITE RABBIT executor not found")
        require(digest(EXECUTOR.read_bytes()) == EXECUTOR_SHA256, "Executor differs from accepted baseline")
        before = snapshot(brief["scenario"])
        record["input_snapshot"] = before
        record["dispatch_attempts"] = 1
        record["execution_state"] = "FAILED"
        record["mission_state"] = "EXECUTION_FAILED"
        response = launch(brief["scenario"], brief["limits"]["timeout_seconds"])
        require(response.returncode == 0, "Executor returned nonzero exit status")
        record["execution_state"] = "COMPLETED"
        record["mission_state"] = "RECONCILIATION_FAILED"
        record["reconciliation_state"] = "REJECTED"
        require(len(response.stdout.encode("utf-8")) <= 262144, "Executor result exceeds size limit")
        require(snapshot(brief["scenario"]) == before, "Mission inputs changed during execution")
        result = parse(response.stdout)
        state = reconcile(brief, result, before)
        require(snapshot(brief["scenario"]) == before, "Mission inputs changed during reconciliation")
        require(digest(EXECUTOR.read_bytes()) == EXECUTOR_SHA256, "Executor changed during execution")
        record["executor_result"] = result
        record["reconciliation_state"] = "ACCEPTED"
        record["mission_state"] = "READY_FOR_REVIEW" if state == "READY" else state
        record["requested_end_state_met"] = state == "READY"
        record["issues"] = list(result["issues"])
    except subprocess.TimeoutExpired:
        record["execution_state"] = "TIMED_OUT"
        record["issues"].append("Executor exceeded five-second timeout; no retry permitted")
    except (ContractError, OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        record["issues"].append(str(exc))
    record["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    return record


def markdown(record):
    return "\n".join([
        "# FORGE Core — Nexus reconciliation SITREP", "",
        "Brief: " + str(record["brief_id"]), "Objective: " + str(record["objective"]),
        "Scenario: " + str(record["scenario"]), "Permitted source: " + str(record["permitted_source"]),
        "Execution: " + record["execution_state"], "Reconciliation: " + record["reconciliation_state"],
        "Mission: " + record["mission_state"], "Requested end state met: " + str(record["requested_end_state_met"]),
        "Human decision: " + record["human_decision"], "Dispatch attempts: " + str(record["dispatch_attempts"]),
        "Brief SHA-256: " + str(record["brief_sha256"]),
        "Executor SHA-256: " + record["executor_sha256"], "",
        "Issues: " + ("; ".join(record["issues"]) or "None"), "",
        "Next action: Actual reviews the result and decides whether to proceed, request evidence, or hold.",
        "No real deployment, send, publication, or external write is authorized by this result.", "",
        "See nexus_record.json for the input snapshot and reconciled executor result.", ""])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--brief", type=Path, default=HOME / "briefs" / "readiness.json")
    group.add_argument("--worker", choices=sorted(SCENARIOS), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return 0
    record = execute(args.brief)
    output = HOME / ".runs"
    output.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="nexus-", dir=str(output)))
    (destination / "nexus_record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (destination / "SITREP.md").write_text(markdown(record), encoding="utf-8")
    print("Execution: " + record["execution_state"])
    print("Reconciliation: " + record["reconciliation_state"])
    print("Mission: " + record["mission_state"])
    print("Human decision: " + record["human_decision"])
    print("Dispatch attempts: " + str(record["dispatch_attempts"]))
    print("SITREP: " + str(destination / "SITREP.md"))
    return 0 if record["reconciliation_state"] == "ACCEPTED" else 2


if __name__ == "__main__":
    sys.exit(main())

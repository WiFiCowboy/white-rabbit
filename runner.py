"""Original offline readiness demonstration. Python 3.8+, standard library only."""
import argparse
import hashlib
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES = 65536
MAX_RECORDS = 128
MAX_REQUIREMENTS = 16
SCENARIOS = ("complete", "missing", "conflict", "recovery", "invalid")


class InvalidInput(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidInput(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def load_json(path, role, report):
    require(path.is_file() and not path.is_symlink(), role + " must be a regular file")
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, role + " exceeds 64 KiB")
    report["inputs"].append({"role": role, "file": path.name,
                             "sha256": hashlib.sha256(raw).hexdigest()})
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise InvalidInput(role + " is not valid UTF-8 JSON") from exc


def text(value):
    return isinstance(value, str) and 0 < len(value) <= 120 and not any(
        ord(char) < 32 or ord(char) == 127 for char in value)


def validate_mission(mission):
    fields = {"mission_id", "site", "requirements", "evidence_files",
              "supplemental_file", "max_recovery_lookups"}
    require(isinstance(mission, dict) and set(mission) == fields,
            "Mission must contain exactly the documented fields")
    require(text(mission["mission_id"]) and text(mission["site"]),
            "Mission ID and site must be nonempty bounded text")
    requirements = mission["requirements"]
    require(isinstance(requirements, list) and 1 <= len(requirements) <= MAX_REQUIREMENTS
            and all(text(item) for item in requirements), "Invalid requirements")
    require(len(set(requirements)) == len(requirements), "Duplicate requirement")
    files = mission["evidence_files"]
    require(isinstance(files, list) and 1 <= len(files) <= 2
            and all(text(item) for item in files), "List one or two evidence files")
    require(len(set(files)) == len(files), "Duplicate evidence filename")
    supplement = mission["supplemental_file"]
    require(supplement is None or text(supplement), "Invalid supplemental filename")
    require(supplement not in files, "Supplemental file duplicates primary evidence")
    budget = mission["max_recovery_lookups"]
    require(type(budget) is int and budget in (0, 1), "Recovery budget must be 0 or 1")


def evidence_path(root, name):
    relative = Path(name)
    require(not relative.is_absolute() and relative.suffix == ".json"
            and ".." not in relative.parts, "Evidence path must be a local JSON path")
    current = root
    for part in relative.parts:
        current = current / part
        require(not current.is_symlink(), "Symlink evidence paths are prohibited")
    resolved = current.resolve()
    require(root in resolved.parents, "Evidence path escapes mission directory")
    return resolved


def read_records(root, filename, mission, report, seen):
    path = evidence_path(root, filename)
    report["counts"]["evidence_file_reads"] += 1
    data = load_json(path, "evidence", report)
    require(isinstance(data, dict) and set(data) == {"records"}, "Invalid evidence document")
    records = data["records"]
    require(isinstance(records, list) and len(records) <= MAX_RECORDS,
            "Evidence must contain at most 128 records")
    checked = []
    for record in records:
        require(isinstance(record, dict) and set(record) ==
                {"record_id", "site", "requirement", "ready"}, "Invalid evidence record")
        require(all(text(record[key]) for key in ("record_id", "site", "requirement"))
                and type(record["ready"]) is bool, "Invalid evidence field type")
        require(record["record_id"] not in seen, "Duplicate evidence record ID")
        seen.add(record["record_id"])
        report["counts"]["records_examined"] += 1
        if record["site"] == mission["site"] and record["requirement"] in mission["requirements"]:
            checked.append(dict(record, source_file=filename))
    return checked


def evaluate(mission, records):
    results = []
    for requirement in mission["requirements"]:
        matches = [row for row in records if row["requirement"] == requirement]
        values = {row["ready"] for row in matches}
        state = ("MISSING" if not matches else "CONFLICT" if len(values) > 1 else
                 "SATISFIED" if True in values else "NOT_READY")
        results.append({"requirement": requirement, "state": state,
                        "evidence": [{"record_id": row["record_id"],
                                      "source_file": row["source_file"],
                                      "ready": row["ready"]} for row in matches]})
    return results


def disposition(results):
    if any(row["state"] == "CONFLICT" for row in results):
        return "REVIEW_REQUIRED"
    if any(row["state"] != "SATISFIED" for row in results):
        return "BLOCKED"
    return "READY"


def validate_result(mission, records, results, report):
    require([row["requirement"] for row in results] == mission["requirements"],
            "Result requirements do not match mission")
    index = {row["record_id"]: row for row in records}
    for result in results:
        relevant = [row for row in records if row["requirement"] == result["requirement"]]
        require({row["record_id"] for row in result["evidence"]} ==
                {row["record_id"] for row in relevant}, "Evidence coverage failed validation")
        values = {row["ready"] for row in relevant}
        required_state = ("MISSING" if not values else "CONFLICT" if len(values) > 1
                          else "SATISFIED" if values == {True} else "NOT_READY")
        require(result["state"] == required_state, "Requirement state failed validation")
        for reference in result["evidence"]:
            source = index.get(reference["record_id"])
            require(source is not None and source["requirement"] == result["requirement"]
                    and source["site"] == mission["site"]
                    and source["source_file"] == reference["source_file"]
                    and source["ready"] is reference["ready"], "Evidence reference failed validation")
    require(report["counts"]["recovery_lookups"] <= mission["max_recovery_lookups"],
            "Recovery limit exceeded")
    require(report["counts"]["evidence_file_reads"] <= 3, "File read limit exceeded")


def run(mission_path):
    start = time.perf_counter()
    report = {"schema_version": "1.0", "mission_id": None, "site": None,
              "generated_at": datetime.now(timezone.utc).isoformat(),
              "disposition": "INVALID_INPUT", "validation": "NOT_COMPLETED",
              "inputs": [], "requirements": [], "issues": [], "events": [],
              "counts": {"evidence_file_reads": 0, "records_examined": 0,
                         "recovery_lookups": 0},
              "scope": "Synthetic offline demonstration; human dispatch; deterministic runner"}
    try:
        path = Path(mission_path).absolute()
        mission = load_json(path, "mission", report)
        validate_mission(mission)
        report.update(mission_id=mission["mission_id"], site=mission["site"])
        root = path.parent.resolve()
        # Validate all declared paths before reading any evidence.
        for filename in mission["evidence_files"]:
            evidence_path(root, filename)
        if mission["supplemental_file"] is not None:
            evidence_path(root, mission["supplemental_file"])
        records, seen = [], set()
        for filename in mission["evidence_files"]:
            records.extend(read_records(root, filename, mission, report, seen))
        results = evaluate(mission, records)
        missing = any(row["state"] == "MISSING" for row in results)
        if missing and mission["supplemental_file"] and mission["max_recovery_lookups"]:
            report["counts"]["recovery_lookups"] += 1
            report["events"].append("Missing evidence triggered the single permitted supplemental lookup")
            records.extend(read_records(root, mission["supplemental_file"], mission, report, seen))
            results = evaluate(mission, records)
        validate_result(mission, records, results, report)
        report["requirements"] = results
        report["disposition"] = disposition(results)
        report["validation"] = "PASSED"
        report["issues"] = [row["requirement"] + ": " + row["state"] for row in results
                            if row["state"] != "SATISFIED"]
    except (InvalidInput, OSError, ValueError) as exc:
        report["issues"].append(str(exc))
    report["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    return report


def markdown(report):
    lines = ["# WHITE RABBIT SITREP", "", "Mission: " + str(report["mission_id"]),
             "Site: " + str(report["site"]), "Disposition: " + report["disposition"],
             "Validation: " + report["validation"], "", report["scope"], ""]
    for row in report["requirements"]:
        refs = ", ".join(ref["source_file"] + "#" + ref["record_id"] for ref in row["evidence"])
        lines.append("- " + row["requirement"] + ": " + row["state"] + " | " + (refs or "No evidence"))
    lines.extend(["", "Issues: " + ("; ".join(report["issues"]) or "None"),
                  "Recovery lookups: " + str(report["counts"]["recovery_lookups"]),
                  "Evidence file reads: " + str(report["counts"]["evidence_file_reads"]),
                  "Elapsed seconds: " + str(report["elapsed_seconds"]),
                  "", "Input SHA-256:"])
    lines.extend("- " + item["role"] + " " + item["file"] + ": " + item["sha256"]
                 for item in report["inputs"])
    lines.extend(["", "Operator action: Review the evidence and disposition; no deployment is authorized.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--suite", action="store_true", help="Run five synthetic scenarios")
    group.add_argument("--mission", type=Path, help="Evaluate a mission JSON file")
    args = parser.parse_args()
    home = Path(__file__).resolve().parent
    missions = [(name, home / "fixtures" / name / "mission.json") for name in SCENARIOS] if args.suite else [("mission", args.mission)]
    output = home / ".runs"
    output.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="run-", dir=str(output)))
    invalid = False
    for name, path in missions:
        report = run(path)
        (destination / (name + ".json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (destination / (name + ".md")).write_text(markdown(report), encoding="utf-8")
        print("{}: {} | validation={} | recovery={}".format(name, report["disposition"], report["validation"], report["counts"]["recovery_lookups"]))
        invalid = invalid or report["disposition"] == "INVALID_INPUT"
    print("SITREPs: " + str(destination))
    # Suite includes an intentionally invalid fixture. Tests verify its expected result.
    return 0 if args.suite or not invalid else 2


if __name__ == "__main__":
    sys.exit(main())

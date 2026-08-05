from __future__ import annotations

import csv
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
import duckdb
import pytest
import requests


BASE_URL = "http://127.0.0.1:7070"
CURRENT_KEY_URL = f"{BASE_URL}/v1/signing-key/current"
PUBLICATION_URL = f"{BASE_URL}/v1/publications"


APP_ROOT = Path("/app")
PUBLISHER_PATH = APP_ROOT / "publisher" / "release-publisher.mjs"
MANIFEST_PATH = APP_ROOT / "fixtures" / "build_manifest.csv"
DATABASE_PATH = APP_ROOT / "releases.duckdb"


MANIFEST_COLUMNS = ("entry_id", "bundle_id", "component_id", "version", "size_bytes", "record_type", "supersedes_id", "recorded_at")
REQUIRED_STATE_COLUMNS = {"bundle_id", "request_token", "publication_id", "status", "key_id", "descriptor"}


SIGNED_LINE_PATTERN = re.compile(r"^BUNDLE (?P<bundle_id>\S+) SIGNED KEY=(?P<key_id>\S+)$")

PUBLISHED_LINE_PATTERN = re.compile(r"^BUNDLE (?P<bundle_id>\S+) PUBLISHED RECEIPT=(?P<publication_id>\S+) TOKEN=(?P<request_token>\S+) STATUS=(?P<status>PUBLISHED)$")


# Run publisher and capture output
def run_publisher(*arguments: str) -> subprocess.CompletedProcess[str]:
    command = ["node", str(PUBLISHER_PATH), *arguments]

    return subprocess.run(command, cwd=APP_ROOT, text=True, capture_output=True, check=False, timeout=60)


def compute_expected_bundles():
    with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as manifest_file:
        reader = csv.DictReader(manifest_file)

        actual_columns = tuple(reader.fieldnames or ())
        assert actual_columns == MANIFEST_COLUMNS, f"Unexpected manifest columns.\nExpected: {MANIFEST_COLUMNS}\nActual:   {actual_columns}"

        unique_rows = {}

        for row in reader:
            row_identity = tuple(
                row[column]
                for column in MANIFEST_COLUMNS
            )

            unique_rows.setdefault(row_identity, row)

    deduplicated_rows = list(unique_rows.values())

    withdrawn_entry_ids = {
        row["supersedes_id"]
        for row in deduplicated_rows
        if row["record_type"] == "WITHDRAWAL"
        and row["supersedes_id"]
    }

    bundle_totals = defaultdict(lambda: {"artifact_count": 0, "total_bytes": 0})


    for row in deduplicated_rows:
        if row["record_type"] != "BUILD":
            continue

        if row["entry_id"] in withdrawn_entry_ids:
            continue

        totals = bundle_totals[row["bundle_id"]]
        totals["artifact_count"] += 1
        totals["total_bytes"] += int(row["size_bytes"])


    return [{
        "bundle_id": bundle_id,
        "artifact_count": totals["artifact_count"],
        "total_bytes": totals["total_bytes"],
    } for bundle_id, totals in sorted(bundle_totals.items())]



def canonical_descriptor(bundle):
    return json.dumps(
        {
            "artifact_count": bundle["artifact_count"],
            "bundle_id": bundle["bundle_id"],
            "total_bytes": bundle["total_bytes"],
        },
        sort_keys=True, 
        separators=(",", ":")
    )



def parse_report(stdout):
    lines = stdout.splitlines()

    assert lines, "Publisher produced empty report."
    assert len(lines) % 2 == 0, f"Report must contain two lines per bundle.\nActual output: {stdout}"

    publications: list[dict[str, str]] = []

    for index in range(0, len(lines), 2):
        signed_line = lines[index]
        published_line = lines[index + 1]

        signed_match = SIGNED_LINE_PATTERN.fullmatch(signed_line)
        published_match = PUBLISHED_LINE_PATTERN.fullmatch(published_line)

        assert signed_match is not None, f"Invalid SIGNED line: {signed_line!r}"
        assert published_match is not None, f"Invalid PUBLISHED line: {published_line!r}"
        
        signed_values = signed_match.groupdict()
        published_values = published_match.groupdict()

        assert signed_values["bundle_id"] == published_values["bundle_id"], "SIGNED and PUBLISHED lines refer to different bundles."

        publications.append(
            {
                "bundle_id": signed_values["bundle_id"],
                "key_id": signed_values["key_id"],
                "publication_id": published_values["publication_id"],
                "request_token": published_values["request_token"],
                "status": published_values["status"],
            }
        )

    return publications



def find_state_tables(connection: duckdb.DuckDBPyConnection):
    rows = connection.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'main'
        ORDER BY table_name, ordinal_position"""
    ).fetchall()

    columns_by_table: dict[str, set[str]] = defaultdict(set)

    for table_name, column_name in rows:
        columns_by_table[table_name].add(column_name)

    return [table_name for table_name, columns in columns_by_table.items() if REQUIRED_STATE_COLUMNS.issubset(columns)]


def quote_identifier(identifier):

    return (
        '"'
        + identifier.replace('"', '""')
        + '"'
    )


# Fixtures...
@pytest.fixture(scope="session")
def expected_bundles():
    bundles = compute_expected_bundles()

    assert bundles, "Manifest produced no publishable bundles."

    return bundles


@pytest.fixture(scope="session")
def current_key_metadata():
    response = requests.get(CURRENT_KEY_URL, timeout=10)

    assert response.status_code == 200, f"Current-key endpoint failed.\nStatus: {response.status_code}\nBody: {response.text}"
    
    payload = response.json()

    assert payload.get("key_id"), "Current-key response is missing: key_id."
    assert payload.get("algorithm"), "Current-key response is missing: algorithm."

    assert payload.get("certificate_ref"), "Current-key response is missing: certificate_ref."
    assert payload.get("status") == "current", "Current-key response is missing: status."


    return payload



@pytest.fixture(scope="session")
def first_run():
    result = run_publisher("--report")

    assert result.returncode == 0, f"Publisher --report command failed.\nExit code: {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"

    return result



@pytest.fixture(scope="session")
def first_report(first_run):

    return parse_report(first_run.stdout)


@pytest.fixture(scope="session")
def second_run(first_run):
    result = run_publisher("--report")

    assert result.returncode == 0, f"Publisher second run failed.\nExit code: {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"

    return result



@pytest.fixture(scope="session")
def second_report(second_run):
    return parse_report(second_run.stdout)



def test_publisher_file_exists():
    assert PUBLISHER_PATH.exists(), (f"Publisher does not exist: {PUBLISHER_PATH}")

    assert PUBLISHER_PATH.is_file(), f"Publisher path is not a regular file: {PUBLISHER_PATH}"
    

def test_report_command_succeeds(first_run):
    assert first_run.stdout, "Publisher succeeded but produced no output."
    
    assert first_run.stderr == "", f"Successful publisher execution wrote to stderr.\nstderr:\n{first_run.stderr}"

    
    
def test_missing_argument_is_rejected():
    result = run_publisher()

    assert "MODULE_NOT_FOUND" not in result.stderr, "Publisher couldn't be loaded, so missing-argument behavior wasn't actually tested."
    assert result.returncode != 0, "Publisher accepted a missing argument."

    assert result.stdout == "", f"Invalid command wrote report data to stdout.\nstdout:\n{result.stdout}"
    assert result.stderr.strip(), "Publisher rejected the command but didn't explain error."


def test_unknown_argument_is_rejected():
    result = run_publisher("--wrong")

    assert "MODULE_NOT_FOUND" not in result.stderr, "Publisher couldn't be loaded, so unknown argument behavior wasn't actually tested."
    assert result.returncode != 0, "Publisher accepted unsupported argument."

    assert result.stdout == "", f"Invalid command wrote report data to stdout.\nstdout: {result.stdout}"
    assert result.stderr.strip(), "Publisher rejected command but didn't explain the error."



def test_extra_argument_is_rejected():
    result = run_publisher("--report", "extra")

    assert "MODULE_NOT_FOUND" not in result.stderr, "Publisher could not be loaded, so extra-argument behavior was not actually tested."
    assert result.returncode != 0, "Publisher accepted an additional argument."

    assert result.stdout == "", f"Invalid command wrote report data to stdout.\nstdout: {result.stdout}"
    assert result.stderr.strip(), "Publisher rejected the command but did not explain the error."



def test_report_has_two_lines_per_bundle(first_run, expected_bundles):
    actual_lines = first_run.stdout.splitlines()
    expected_line_count = 2 * len(expected_bundles)

    assert len(actual_lines) == expected_line_count, f"Publisher produced missing or extra report lines.\nExpected: {expected_line_count}\nActual: {len(actual_lines)}\nstdout:\n{first_run.stdout}"


def test_report_contains_expected_bundles_in_order(first_report, expected_bundles):
    expected_bundle_ids = [
        bundle["bundle_id"]
        for bundle in expected_bundles
    ]

    actual_bundle_ids = [
        publication["bundle_id"]
        for publication in first_report
    ]

    assert actual_bundle_ids == expected_bundle_ids, f"Reported bundle set/ordering incorrect.\nExpected: {expected_bundle_ids}\nActual:   {actual_bundle_ids}"
    
    assert len(actual_bundle_ids) == len(set(actual_bundle_ids)), "A bundle appeared more than once in report"
    


def test_report_uses_current_key_and_deterministic_tokens(first_report, current_key_metadata):
    expected_key_id = current_key_metadata["key_id"]

    for publication in first_report:
        bundle_id = publication["bundle_id"]

        assert publication["key_id"] == expected_key_id, f"{bundle_id} reported wrong signing-key ID."
        assert publication["request_token"] == f"token-{bundle_id}", f"{bundle_id} used incorrect request-token."

        assert publication["publication_id"], f"{bundle_id} has empty publication receipts."
        assert publication["status"] == "PUBLISHED"



def test_reported_receipts_exist_on_gateway(first_report):
    for publication in first_report:
        response = requests.post(PUBLICATION_URL, json={"descriptor": "{}", "signature": "intentionally-invalid-signature", "request_token": publication["request_token"]}, timeout=10)

        assert response.status_code == 200, f"Gateway didn't recognize reported request-token.\nBundle: {publication['bundle_id']}\nStatus: {response.status_code}\nBody: {response.text}"

        replay = response.json()

        assert replay.get("publication_id") == publication["publication_id"], "Publisher receipt doesn't match gateway receipts."
        assert replay.get("request_token") == publication["request_token"], "Publisher response doesn't match gateway token."
        assert replay.get("status") == "PUBLISHED", "Publisher status doesn't match gateway status."



def test_database_exists(first_run):
    assert DATABASE_PATH.exists(), f"Publisher did not create {DATABASE_PATH}."
    assert DATABASE_PATH.is_file(), f"{DATABASE_PATH} is not regular file."
    assert DATABASE_PATH.stat().st_size > 0, "Publisher database exists but empty."



def test_persisted_publications_match(second_run, expected_bundles, first_report, current_key_metadata):
    expected_by_bundle = {bundle["bundle_id"]: bundle for bundle in expected_bundles}

    report_by_bundle = {publication["bundle_id"]: publication for publication in first_report}

    connection = duckdb.connect(str(DATABASE_PATH), read_only=True)

    try:
        matching_tables = find_state_tables(connection)
        assert matching_tables, f"No publication-state table exposes all required persisted columns"

        expected_bundle_ids = list(expected_by_bundle)
        valid_states: list[tuple[str, list[tuple]]] = []

        for table_name in matching_tables:
            quoted_table = quote_identifier(table_name)

            rows = connection.execute(f"""
                SELECT bundle_id, request_token, publication_id, status, key_id, descriptor
                FROM {quoted_table}
                WHERE status = 'PUBLISHED'
                ORDER BY bundle_id"""
            ).fetchall()

            row_bundle_ids = [
                row[0]
                for row in rows
            ]

            if (row_bundle_ids == expected_bundle_ids and len(rows) == len(expected_bundles)):
                valid_states.append((table_name, rows))


        assert valid_states, "No publication-state table contains exactly one successful row..."

        _, rows = valid_states[0]

    finally:
        connection.close()


    for (bundle_id, request_token, publication_id, status, key_id, descriptor) in rows:
        expected_bundle = expected_by_bundle[bundle_id]
        reported_publication = report_by_bundle[bundle_id]

        assert request_token == f"token-{bundle_id}"
        assert publication_id == reported_publication["publication_id"]
        assert status == "PUBLISHED"
        assert key_id == current_key_metadata["key_id"]
        assert descriptor == canonical_descriptor(expected_bundle)


def test_second_run_is_byte_identical(first_run, second_run):
    assert second_run.stderr == "", f"Second full run wrote stderr.\nstderr:\n{second_run.stderr}"
    assert second_run.stdout == first_run.stdout, f"Repeated publisher execution produces different output.\nFirst run: {first_run.stdout}\nSecond run: {second_run.stdout}"



def test_second_run_reuses_receipts(first_report, second_report):
    first_receipts = {publication["bundle_id"]: publication["publication_id"] for publication in first_report}

    second_receipts = {publication["bundle_id"]: publication["publication_id"] for publication in second_report}

    assert second_receipts == first_receipts, f"Second run didn't re-use original gateway receipts."




    
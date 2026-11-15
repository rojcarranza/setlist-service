"""setlist_step.py: the pure parts. Run with `pytest ci`."""

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import setlist_step as s

GO_RUN = [
    {"Action": "run", "Package": "p", "Test": "TestA"},
    {"Action": "output", "Package": "p", "Test": "TestA", "Output": "    a_test.go:9: boom\n"},
    {"Action": "fail", "Package": "p", "Test": "TestA", "Elapsed": 0.01},
    {"Action": "run", "Package": "p", "Test": "TestB"},
    {"Action": "pass", "Package": "p", "Test": "TestB", "Elapsed": 0.02},
    {"Action": "fail", "Package": "p", "Elapsed": 0.1},
]


def lines(events):
    return [json.dumps(e) for e in events]


def test_the_script_is_executable():
    assert os.access(Path(s.__file__), os.X_OK)


def test_junit_marks_the_failing_test_with_its_message():
    root = ET.fromstring(s.junit_xml(s.parse_go_events(lines(GO_RUN))))
    assert root.get("tests") == "2" and root.get("failures") == "1"
    failed = root.find("testcase[@name='TestA']/failure")
    assert failed.get("message") == "a_test.go:9: boom"


def test_a_compile_error_is_one_failed_build_case():
    events = [
        {"Action": "output", "Package": "q", "Output": "q.go:3: undefined: x\n"},
        {"Action": "fail", "Package": "q", "Elapsed": 0.0},
    ]
    cases = s.parse_go_events(lines(events))
    assert [(c["name"], c["status"]) for c in cases] == [("build", "fail")]
    assert "undefined: x" in cases[0]["output"]


def test_non_json_lines_are_ignored():
    assert s.parse_go_events(["FAIL q [build failed]", ""]) == []


def test_every_fourth_build_fails_its_first_attempt_only():
    assert [s.should_fail_first_attempt(n, False) for n in (1, 2, 3, 4, 5, 8)] == [
        False, False, False, True, False, True]
    assert s.should_fail_first_attempt(4, True) is False


def test_marker_older_than_a_day_does_not_count(tmp_path):
    marker = tmp_path / "SETLIST-IT-4"
    assert not s.marker_is_fresh(marker)
    marker.touch()
    assert s.marker_is_fresh(marker)
    assert not s.marker_is_fresh(marker, now=marker.stat().st_mtime + s.MARKER_MAX_AGE_SECONDS + 1)


def test_manifest_targets_the_environment_namespace():
    doc = json.loads(s.manifest("staging", "1.4.0", "eu", 3, "hunter2"))
    kinds = {i["kind"]: i for i in doc["items"]}
    assert kinds["Namespace"]["metadata"]["name"] == "setlist-staging"
    dep = kinds["Deployment"]
    assert dep["spec"]["replicas"] == 3
    container = dep["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "setlist:1.4.0"
    assert {"name": "SETLIST_REGION", "value": "eu"} in container["env"]


def test_the_password_only_lives_in_the_secret():
    doc = s.manifest("dev", "1.0.0", "us", 1, "hunter2")
    assert doc.count("hunter2") == 1
    assert json.loads(doc)["items"][1]["stringData"] == {"password": "hunter2"}


def test_deploy_validation_names_every_problem():
    assert s.validate_deploy("dev", "1.0.0", "eu", "2", "x") == []
    problems = s.validate_deploy("qa", "", "asia", "9", "")
    assert len(problems) == 5 and "environment must be one of dev, staging, prod" in problems[0]


def test_only_node_containers_need_an_image_load():
    assert s.shared_node_containers(["kind-control-plane"], ["kind-control-plane", "db"]) == ["kind-control-plane"]
    assert s.shared_node_containers(["lima-rancher"], ["db"]) == []


def test_p95():
    assert s.p95([]) == 0.0
    assert s.p95(list(map(float, range(1, 101)))) == 95.0


def test_smoke_checks_report_an_unreachable_service():
    results = s.smoke_checks("http://127.0.0.1:1", "")
    assert [(n, ok) for n, ok, _ in results] == [("health", False), ("setlists", False)]

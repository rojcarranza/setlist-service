#!/usr/bin/env python3
"""The one step every SETLIST Bamboo job runs.

forge-lab's SETLIST-* plans (project "setlist") check this repository out and
call one subcommand each:

    unit          go vet + unit tests, JUnit results
    integration   end-to-end tests; fails the first attempt of every 4th build
    package       versioned linux binary as a tarball
    deploy        build the image, roll it out to namespace setlist-<environment>
    smoke         check /health and /api/setlists on a deployed environment
    load          hold the service under load for a few minutes

Standard library only: the host agent has no virtualenv. Parsing and rendering
are pure functions; everything that shells out goes through run().
"""

import argparse
import json
import math
import os
import socket
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ENVIRONMENTS = ("dev", "staging", "prod")
REGIONS = ("eu", "us")
FLAKY_EVERY = 4
MARKER_MAX_AGE_SECONDS = 24 * 60 * 60
DEFAULT_STATE_DIR = Path.home() / ".setlist-demo" / "attempts"
NOTIFY_DELAY_MS_WHEN_FLAKY = "900"
P95_LIMIT_MS = 250


class StepError(Exception):
    """A failure with a message worth showing; main() turns it into exit 1."""


def run(argv, *, cwd=None, env=None, stdin=None, capture=False):
    result = subprocess.run(
        argv, cwd=cwd, env=env, input=stdin, text=True, check=False,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    return result


def run_ok(argv, **kwargs):
    result = run(argv, **kwargs)
    if result.returncode != 0:
        raise StepError(f"{' '.join(map(str, argv))} exited {result.returncode}")
    return result


# ---- JUnit from `go test -json` -------------------------------------------

def parse_go_events(lines):
    """Fold `go test -json` events into [{package, name, status, seconds, output}].

    A package that fails without running a test (a compile error) becomes one
    failed case named "build" so the failure is visible in Bamboo's test tab.
    """
    cases, order, package_output, package_ran = {}, [], {}, set()
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        pkg, test, action = event.get("Package", ""), event.get("Test"), event.get("Action")
        if not pkg:
            continue
        if test is None:
            if action == "output":
                package_output.setdefault(pkg, []).append(event.get("Output", ""))
            elif action == "fail" and pkg not in package_ran:
                cases[(pkg, "build")] = {
                    "package": pkg, "name": "build", "status": "fail",
                    "seconds": event.get("Elapsed", 0.0),
                    "output": "".join(package_output.get(pkg, [])),
                }
                order.append((pkg, "build"))
            continue
        package_ran.add(pkg)
        key = (pkg, test)
        case = cases.get(key)
        if case is None:
            case = cases[key] = {"package": pkg, "name": test, "status": "run",
                                 "seconds": 0.0, "output": ""}
            order.append(key)
        if action == "output":
            case["output"] += event.get("Output", "")
        elif action in ("pass", "fail", "skip"):
            case["status"] = action
            case["seconds"] = event.get("Elapsed", 0.0)
    return [cases[k] for k in order]


def junit_xml(cases, suite="setlist"):
    failures = sum(1 for c in cases if c["status"] == "fail")
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name={quoteattr(suite)} tests="{len(cases)}" failures="{failures}">',
    ]
    for c in cases:
        head = (f'  <testcase classname={quoteattr(c["package"])} '
                f'name={quoteattr(c["name"])} time="{c["seconds"]}"')
        if c["status"] == "fail":
            tail = "".join(c["output"].splitlines(keepends=True)[-12:])
            message = next((s.strip() for s in reversed(c["output"].splitlines())
                            if s.strip() and not s.startswith(("---", "=== "))), "failed")
            out.append(f'{head}><failure message={quoteattr(message)}>{escape(tail)}</failure></testcase>')
        elif c["status"] == "skip":
            out.append(f"{head}><skipped/></testcase>")
        else:
            out.append(f"{head}/>")
    out.append("</testsuite>")
    return "\n".join(out) + "\n"


def run_go_tests(app, argv, env, junit_dir):
    """Run go test -json, echo readable output, write JUnit. Returns go's code."""
    proc = subprocess.Popen(argv, cwd=app, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    lines = []
    for line in proc.stdout:
        lines.append(line)
        try:
            event = json.loads(line)
        except ValueError:
            print(line, end="", flush=True)
            continue
        if event.get("Action") == "output":
            print(event.get("Output", ""), end="", flush=True)
    code = proc.wait()
    Path(junit_dir).mkdir(parents=True, exist_ok=True)
    (Path(junit_dir) / "results.xml").write_text(junit_xml(parse_go_events(lines)))
    return code


# ---- the flaky integration rule ------------------------------------------

def is_flaky_build(build_number):
    return build_number > 0 and build_number % FLAKY_EVERY == 0


def should_fail_first_attempt(build_number, marker_exists):
    """Every 4th build fails its first attempt; a restart of the same build
    finds its marker and passes."""
    return is_flaky_build(build_number) and not marker_exists


def marker_is_fresh(marker, now=None):
    if not marker.is_file():
        return False
    return (now or time.time()) - marker.stat().st_mtime < MARKER_MAX_AGE_SECONDS


# ---- k8s manifest -----------------------------------------------------------

def manifest(environment, version, region, replicas, db_password):
    """Namespace + secret + deployment + service as one JSON document list.

    JSON is valid YAML, so kubectl applies it, and no YAML library is needed.
    """
    ns, app = f"setlist-{environment}", "setlist"
    labels = {"app": app}
    items = [
        {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": ns}},
        {"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
         "metadata": {"name": "setlist-db", "namespace": ns},
         "stringData": {"password": db_password}},
        {"apiVersion": "apps/v1", "kind": "Deployment",
         "metadata": {"name": app, "namespace": ns, "labels": labels},
         "spec": {
             "replicas": replicas, "selector": {"matchLabels": labels},
             "template": {"metadata": {"labels": {**labels, "version": version}}, "spec": {"containers": [{
                 "name": app, "image": f"setlist:{version}", "imagePullPolicy": "IfNotPresent",
                 "ports": [{"containerPort": 8080}],
                 "env": [
                     {"name": "SETLIST_REGION", "value": region},
                     {"name": "SETLIST_DB_PASSWORD",
                      "valueFrom": {"secretKeyRef": {"name": "setlist-db", "key": "password"}}},
                 ],
                 "readinessProbe": {"httpGet": {"path": "/health", "port": 8080},
                                    "periodSeconds": 2},
             }]}}}},
        {"apiVersion": "v1", "kind": "Service",
         "metadata": {"name": app, "namespace": ns},
         "spec": {"selector": labels, "ports": [{"port": 80, "targetPort": 8080}]}},
    ]
    return json.dumps({"apiVersion": "v1", "kind": "List", "items": items}, indent=2)


def validate_deploy(environment, version, region, replicas, db_password):
    problems = []
    if environment not in ENVIRONMENTS:
        problems.append(f"environment must be one of {', '.join(ENVIRONMENTS)}, got {environment!r}")
    if not version:
        problems.append("version is required, for example 1.4.0")
    if region not in REGIONS:
        problems.append(f"region must be one of {', '.join(REGIONS)}, got {region!r}")
    if not (replicas.isdigit() and 1 <= int(replicas) <= 5):
        problems.append(f"replicas must be 1 to 5, got {replicas!r}")
    if not db_password:
        problems.append("db_password is required")
    return problems


def shared_node_containers(nodes, containers):
    """Cluster nodes that are docker containers (kind): images must be loaded
    into them. Empty when the cluster shares the host's image store."""
    return [n for n in nodes if n in containers]


# ---- subcommands ----------------------------------------------------------

def cmd_unit(args):
    app = args.app
    for tool in (["gofmt", "-l", "."], ["go", "vet", "./..."]):
        result = run(tool, cwd=app, capture=True)
        if tool[0] == "gofmt" and result.stdout.strip():
            raise StepError(f"gofmt: unformatted files:\n{result.stdout}")
        if tool[0] == "go" and result.returncode != 0:
            print(result.stdout)
            raise StepError("go vet failed")
    code = run_go_tests(app, ["go", "test", "-json", "-count=1", "./..."], os.environ.copy(), args.junit_dir)
    if code != 0:
        raise StepError("unit tests failed")


def cmd_integration(args):
    build = int(os.environ.get("bamboo_buildNumber", "0"))
    result_key = os.environ.get("bamboo_buildResultKey", f"local-{build}")
    marker = Path(args.state_dir) / result_key
    flake = should_fail_first_attempt(build, marker_is_fresh(marker))
    env = os.environ.copy()
    if flake:
        env["SETLIST_NOTIFY_DELAY_MS"] = NOTIFY_DELAY_MS_WHEN_FLAKY
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        print(f"setlist: build {build} is a {FLAKY_EVERY}th build; the chat service is slow on this first attempt")
    code = run_go_tests(args.app, ["go", "test", "-json", "-count=1", "-tags", "integration", "./integration/"],
                        env, args.junit_dir)
    if code != 0:
        raise StepError("integration tests failed")


def cmd_package(args):
    build = os.environ.get("bamboo_buildNumber", "0")
    version = args.version or f"1.0.{build}"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    binary = out / "setlist"
    env = {**os.environ, "CGO_ENABLED": "0", "GOOS": "linux"}
    run_ok(["go", "build", "-ldflags", f"-X main.version={version}", "-o", str(binary.resolve()), "./cmd/setlist"],
           cwd=args.app, env=env)
    tarball = out / f"setlist-{version}-linux.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(binary, arcname="setlist")
    binary.unlink()
    print(f"setlist: packaged {tarball} ({tarball.stat().st_size // 1024} KiB), version {version}")


def cmd_deploy(args):
    env_name, version = args.environment, args.version
    problems = validate_deploy(env_name, version, args.region, args.replicas, args.db_password)
    if problems:
        raise StepError("; ".join(problems))
    image = f"setlist:{version}"
    print(f"setlist: building {image}")
    run_ok(["docker", "build", "-q", "--build-arg", f"VERSION={version}", "-t", image, "."], cwd=args.app)
    load_image(image)
    ns = f"setlist-{env_name}"
    print(f"setlist: rolling out {image} to {ns} (region {args.region}, {args.replicas} replicas)")
    run_ok(["kubectl", "apply", "-f", "-"], stdin=manifest(env_name, version, args.region, args.replicas, args.db_password),
           capture=False)
    run_ok(["kubectl", "-n", ns, "rollout", "status", "deployment/setlist", "--timeout=120s"])
    print(f"setlist: {version} is live in {ns}")


def load_image(image):
    nodes = run(["kubectl", "get", "nodes", "-o", "name"], capture=True).stdout.split()
    nodes = [n.split("/", 1)[-1] for n in nodes]
    containers = run(["docker", "ps", "--format", "{{.Names}}"], capture=True).stdout.split()
    for node in shared_node_containers(nodes, containers):
        print(f"setlist: loading {image} into node {node}")
        save = subprocess.Popen(["docker", "save", image], stdout=subprocess.PIPE)
        load = subprocess.run(["docker", "exec", "-i", node, "ctr", "-n", "k8s.io", "images", "import", "-"],
                              stdin=save.stdout, check=False)
        save.stdout.close()
        save.wait()
        if load.returncode != 0:
            raise StepError(f"could not load {image} into node {node}")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http_get(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.read().decode()


def smoke_checks(base, expected_version):
    """[(name, ok, detail)] for /health and /api/setlists."""
    results = []
    try:
        status, body = http_get(f"{base}/health")
        health = json.loads(body)
        ok = status == 200 and health.get("status") == "ok"
        if ok and expected_version and health.get("version") != expected_version:
            ok = False
        results.append(("health", ok, f"{status} version={health.get('version')}"))
    except (OSError, ValueError) as err:
        results.append(("health", False, str(err)))
    try:
        status, body = http_get(f"{base}/api/setlists")
        count = len(json.loads(body))
        results.append(("setlists", status == 200 and count > 0, f"{status} {count} setlists"))
    except (OSError, ValueError) as err:
        results.append(("setlists", False, str(err)))
    return results


def cmd_smoke(args):
    ns = f"setlist-{args.environment}"
    port = free_port()
    forward = subprocess.Popen(["kubectl", "-n", ns, "port-forward", "svc/setlist", f"{port}:80"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = f"http://127.0.0.1:{port}"
        deadline = time.time() + 30
        results = []
        while time.time() < deadline:
            results = smoke_checks(base, args.version)
            if all(ok for _, ok, _ in results):
                break
            time.sleep(1)
    finally:
        forward.terminate()
    cases = []
    for name, ok, detail in results:
        print(f"setlist: smoke {args.environment} {name}: {'ok' if ok else 'FAILED'} ({detail})")
        cases.append({"package": f"smoke.{args.environment}", "name": name, "status": "pass" if ok else "fail",
                      "seconds": 0.1, "output": detail})
    Path(args.junit_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.junit_dir) / "results.xml").write_text(junit_xml(cases, "smoke"))
    if not all(ok for _, ok, _ in results):
        raise StepError(f"smoke test failed in {ns}")


def p95(samples):
    ordered = sorted(samples)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)] if ordered else 0.0


def cmd_load(args):
    run_ok(["go", "build", "-o", "setlist-load", "./cmd/setlist"], cwd=args.app)
    port = free_port()
    server = subprocess.Popen([str(Path(args.app) / "setlist-load")],
                              env={**os.environ, "SETLIST_ADDR": f"127.0.0.1:{port}"},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    lock, window, totals = threading.Lock(), [], {"requests": 0, "errors": 0}
    stop = threading.Event()
    paths = ["/health", "/api/setlists", "/api/setlists/sunday?transpose=2"]

    def worker(n):
        i = n
        while not stop.is_set():
            started = time.perf_counter()
            try:
                http_get(f"http://127.0.0.1:{port}{paths[i % len(paths)]}")
                failed = False
            except OSError:
                failed = True
            took = (time.perf_counter() - started) * 1000
            with lock:
                totals["requests"] += 1
                totals["errors"] += failed
                window.append(took)
            i += 1
            time.sleep(0.01)

    try:
        time.sleep(1)
        threads = [threading.Thread(target=worker, args=(n,), daemon=True) for n in range(args.workers)]
        for t in threads:
            t.start()
        worst = 0.0
        for tick in range(1, args.seconds // args.report + 1):
            time.sleep(args.report)
            with lock:
                sample, window[:] = list(window), []
            worst = max(worst, p95(sample))
            print(f"setlist: load t={tick * args.report}s requests={totals['requests']} "
                  f"rps={len(sample) / args.report:.0f} p95={p95(sample):.1f}ms errors={totals['errors']}", flush=True)
    finally:
        stop.set()
        server.terminate()
        (Path(args.app) / "setlist-load").unlink(missing_ok=True)
    if totals["errors"]:
        raise StepError(f"{totals['errors']} requests failed under load")
    if worst > P95_LIMIT_MS:
        raise StepError(f"p95 {worst:.1f}ms is over the {P95_LIMIT_MS}ms limit")
    print(f"setlist: load passed, worst p95 {worst:.1f}ms")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--app", default=".", help="the checked-out repository (default: .)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("unit", "integration", "smoke"):
        p = sub.add_parser(name)
        p.add_argument("--junit-dir", default="test-results")
        if name == "integration":
            p.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
        if name == "smoke":
            p.add_argument("--environment", required=True)
            p.add_argument("--version", default="")
    p = sub.add_parser("package")
    p.add_argument("--version", default="")
    p.add_argument("--out", default="dist")
    p = sub.add_parser("deploy")
    for flag in ("environment", "version", "region", "replicas", "db-password"):
        p.add_argument(f"--{flag}", required=True)
    p = sub.add_parser("load")
    p.add_argument("--seconds", type=int, default=180)
    p.add_argument("--report", type=int, default=15)
    p.add_argument("--workers", type=int, default=8)
    return parser


def main(argv):
    args = build_parser().parse_args(argv)
    handler = {"unit": cmd_unit, "integration": cmd_integration, "package": cmd_package,
               "deploy": cmd_deploy, "smoke": cmd_smoke, "load": cmd_load}[args.command]
    try:
        handler(args)
    except StepError as err:
        print(f"ERROR setlist: {err}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

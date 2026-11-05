"""Measures how long the API calls behind each page take against a RUNNING
backend, and checks the STU-NF-001 target: 95% of page loads within 3 seconds.

Run from the repo root with the backend already running:
    python perf/page_load_check.py --login-id PES2UG24CS000
Uses only the Python standard library. The password is read from the
PERF_PASSWORD environment variable, or asked for if it is not set.
"""
import argparse
import json
import math
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from getpass import getpass

LIMIT_SECONDS = 3.0

# Page -> the API call that loads its data (student account).
PAGES = [
    ("Dashboard (results)", "/api/student/results"),
    ("Dashboard (GPA)", "/api/student/gpa"),
    ("Profile", "/api/students/me"),
    ("Course list", "/api/courses"),
    ("Transcript (PDF)", "/api/students/me/transcript"),
]


def p95(values):
    """95th percentile, nearest-rank method."""
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def call(base_url, path, token=None, body=None):
    """Returns (http_status, seconds)."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        base_url + path, data=data, headers=headers, method="POST" if data else "GET"
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        error.read()
        status = error.code
    return status, time.perf_counter() - start


def login(base_url, login_id, password):
    request = urllib.request.Request(
        base_url + "/api/auth/login",
        data=json.dumps({"login_id": login_id, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


def measure(base_url, path, token, requests, concurrency):
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(lambda _: call(base_url, path, token), range(requests)))
    statuses = {status for status, _ in results}
    return statuses, [seconds for _, seconds in results]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--login-id", required=True, help="a student account")
    parser.add_argument("--requests", type=int, default=50, help="requests per page")
    parser.add_argument("--concurrency", type=int, default=5, help="simultaneous users")
    parser.add_argument("--markdown", action="store_true", help="also print a Markdown table")
    args = parser.parse_args()

    password = os.environ.get("PERF_PASSWORD") or getpass("Password: ")
    try:
        token = login(args.base_url, args.login_id, password)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"ERROR: login failed (HTTP {error.code}). Check the login ID and password.")
    except urllib.error.URLError:
        raise SystemExit(
            f"ERROR: cannot reach the backend at {args.base_url}. "
            "Start it first (python run.py inside backend/)."
        )

    # Login itself is a page load too (it includes password hashing).
    login_times = []
    for _ in range(10):
        start = time.perf_counter()
        login(args.base_url, args.login_id, password)
        login_times.append(time.perf_counter() - start)

    rows = [("Login", "/api/auth/login", len(login_times), login_times, "OK")]
    for name, path in PAGES:
        call(args.base_url, path, token)  # warm-up request, not counted
        statuses, times = measure(args.base_url, path, token, args.requests, args.concurrency)
        if statuses == {404}:
            note = "NO DATA (404): run seed_demo.py"
        elif statuses != {200}:
            note = f"ERRORS: statuses {sorted(statuses)}"
        else:
            note = "OK"
        rows.append((name, path, len(times), times, note))

    print(f"\nServer: {args.base_url}   requests/page: {args.requests}   "
          f"simultaneous users: {args.concurrency}   limit: {LIMIT_SECONDS:.1f}s (p95)\n")
    header = f"{'Page':<22}{'Calls':>6}{'Avg s':>9}{'p95 s':>9}{'Max s':>9}   Result"
    print(header)
    print("-" * len(header))
    passed = True
    table = []
    for name, path, count, times, note in rows:
        average, slow95, slowest = sum(times) / len(times), p95(times), max(times)
        ok = note == "OK" and slow95 <= LIMIT_SECONDS
        passed = passed and ok
        verdict = "PASS" if ok else (note if note != "OK" else "FAIL (p95 over limit)")
        print(f"{name:<22}{count:>6}{average:>9.3f}{slow95:>9.3f}{slowest:>9.3f}   {verdict}")
        table.append((name, path, count, average, slow95, slowest, verdict))
    print(f"\nOVERALL: {'PASS' if passed else 'FAIL'}")

    if args.markdown:
        print("\n| Page | Endpoint | Calls | Avg (s) | p95 (s) | Max (s) | Result |")
        print("|---|---|---|---|---|---|---|")
        for name, path, count, average, slow95, slowest, verdict in table:
            print(f"| {name} | `{path}` | {count} | {average:.3f} | {slow95:.3f} | "
                  f"{slowest:.3f} | {verdict} |")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
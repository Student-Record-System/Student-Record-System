"""STU-NF-001: 95% of page loads must finish within 3 seconds (TC-Perf-01).

These tests time the API calls behind each page inside the test client, so they
measure server work only (no network, SQLite). The same targets are measured on
a running server by perf/page_load_check.py; see docs/performance/.
"""
import math
import time
from datetime import date

import pytest

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import STUDENT
from app.course.models import Course
from app.enrollment.models import COMPLETED, Enrollment
from app.extensions import db
from app.grades.models import StudentMark
from app.profile import repository as profile_repository
from app.profile.models import StudentProfile

LIMIT_SECONDS = 3.0
SAMPLES = 30
PASSWORD = "Passw0rd!"
SRN = "PES2UG24CS252"

# Page -> the API call that loads its data.
PAGES = {
    "dashboard-results": "/api/student/results",
    "dashboard-gpa": "/api/student/gpa",
    "profile": "/api/students/me",
    "course-list": "/api/courses",
    "transcript": "/api/students/me/transcript",
}


def p95(values):
    """95th percentile, nearest-rank method."""
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def seed_student():
    auth_repository.add_user(User(
        login_id=SRN, password_hash=hash_password(PASSWORD), role=STUDENT, is_active=True,
    ))
    profile_repository.add(StudentProfile(
        srn=SRN, full_name="Perf Student", email="perf@example.com",
        phone="9876543210", date_of_birth=date(2005, 1, 1), gender="Female",
        program="B.Tech", branch="Computer Science", semester=3,
    ))
    for index in range(1, 7):  # six published results across two semesters
        code = f"CS{100 + index}"
        semester = 1 if index <= 3 else 2
        db.session.add(Course(
            code=code, title=f"Course {code}", credits=4,
            semester=semester, department="Computer Science",
        ))
        db.session.add(Enrollment(srn=SRN, course_code=code, semester=semester, status=COMPLETED))
        db.session.add(StudentMark(
            course_code=code, srn=SRN, internal_marks=70 + index,
            end_semester_marks=75 + index, status="Approved", submitted_by=1,
        ))
    db.session.commit()


def timed(call, samples):
    durations = []
    for _ in range(samples):
        start = time.perf_counter()
        response = call()
        durations.append(time.perf_counter() - start)
        assert response.status_code == 200
    return durations


def test_p95_uses_the_nearest_rank_method():
    assert p95([1]) == 1
    assert p95(list(range(1, 101))) == 95
    assert p95(list(range(100, 0, -1))) == 95  # order does not matter
    assert p95([0.1] * 19 + [5.0]) == 0.1       # 1 slow call in 20 is inside the 95%
    assert p95([0.1] * 18 + [5.0, 5.0]) == 5.0  # 2 slow calls in 20 are not


@pytest.mark.parametrize("page", PAGES)
def test_page_data_loads_within_three_seconds_for_95_percent_of_calls(client, page):  # TC-Perf-01
    seed_student()
    login = client.post("/api/auth/login", json={"login_id": SRN, "password": PASSWORD})
    headers = {"Authorization": f"Bearer {login.get_json()['access_token']}"}
    path = PAGES[page]
    client.get(path, headers=headers)  # warm-up call, not counted

    durations = timed(lambda: client.get(path, headers=headers), SAMPLES)

    assert p95(durations) <= LIMIT_SECONDS, f"{page}: p95 {p95(durations):.3f}s"


def test_login_completes_within_three_seconds_for_95_percent_of_calls(client):  # TC-Perf-01
    seed_student()

    durations = timed(
        lambda: client.post("/api/auth/login", json={"login_id": SRN, "password": PASSWORD}),
        10,  # password hashing makes each login slower, so fewer samples
    )

    assert p95(durations) <= LIMIT_SECONDS, f"login: p95 {p95(durations):.3f}s"
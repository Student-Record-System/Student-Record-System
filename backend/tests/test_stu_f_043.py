from datetime import date
from io import BytesIO

import pytest
from pypdf import PdfReader

from app.auth import repository as auth_repository
from app.auth.models import User
from app.auth.service import hash_password
from app.common.roles import ADMIN, FACULTY, STUDENT
from app.course.models import Course
from app.enrollment.models import COMPLETED, Enrollment
from app.extensions import db
from app.grades.models import PENDING_APPROVAL, StudentMark
from app.profile import repository as profile_repository
from app.profile.models import StudentProfile
from app.reports.pdf import INSTITUTION_NAME

PASSWORD = "Passw0rd!"
SRN = "PES2UG24CS252"
OTHER_SRN = "PES2UG24CS999"


def make_user(login_id, role):
    return auth_repository.add_user(User(
        login_id=login_id,
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=True,
    ))


def make_profile(srn=SRN, full_name="Divya Dharshini"):
    return profile_repository.add(StudentProfile(
        srn=srn, full_name=full_name, email="student@example.com",
        phone="9876543210", date_of_birth=date(2005, 1, 1), gender="Female",
        program="B.Tech", branch="Computer Science", semester=5,
    ))


def headers_for(client, login_id):
    response = client.post(
        "/api/auth/login", json={"login_id": login_id, "password": PASSWORD}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['access_token']}"}


def add_result(course_code, title, semester, credits, internal, end_sem,
               status="Approved", srn=SRN):
    db.session.add(Course(
        code=course_code, title=title, credits=credits,
        semester=semester, department="Computer Science",
    ))
    db.session.add(Enrollment(
        srn=srn, course_code=course_code, semester=semester, status=COMPLETED,
    ))
    db.session.add(StudentMark(
        course_code=course_code, srn=srn, internal_marks=internal,
        end_semester_marks=end_sem, status=status, submitted_by=1,
    ))
    db.session.commit()


def pdf_text(response):
    reader = PdfReader(BytesIO(response.data))
    return "\n".join(page.extract_text() for page in reader.pages)


@pytest.fixture()
def student(client):
    make_user(SRN, STUDENT)
    make_profile()
    return headers_for(client, SRN)


def test_student_downloads_own_mark_sheet_as_pdf(client, student):  # TC-Grd-04
    add_result("CS301", "Database Management Systems", 1, 4, 80, 90)

    response = client.get(f"/api/students/{SRN}/transcript", headers=student)

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    disposition = response.headers["Content-Disposition"]
    assert "attachment" in disposition
    assert f"marksheet_{SRN}.pdf" in disposition


def test_pdf_has_letterhead_student_details_and_published_grades(client, student):  # TC-Grd-04
    add_result("CS301", "Database Management Systems", 1, 4, 80, 90)

    text = pdf_text(client.get(f"/api/students/{SRN}/transcript", headers=student))

    assert INSTITUTION_NAME in text
    assert "Divya Dharshini" in text
    assert SRN in text
    lines = text.splitlines()
    row = lines.index("CS301")
    # code, title, credits, internal, end-sem, total (80 + 90) / 2, grade, grade points
    assert lines[row:row + 8] == [
        "CS301", "Database Management Systems", "4", "80", "90", "85", "A", "9",
    ]


def test_pdf_gpa_and_cgpa_match_the_gpa_endpoint(client, student):  # TC-Grd-04
    add_result("CS301", "Course One", 1, 3, 90, 100)
    add_result("CS302", "Course Two", 1, 1, 80, 90)
    add_result("CS401", "Course Three", 2, 2, 70, 80)
    expected = client.get("/api/student/gpa", headers=student).get_json()

    text = pdf_text(client.get(f"/api/students/{SRN}/transcript", headers=student))

    assert expected["cgpa"] == 9.17
    assert f"{expected['cgpa']:.2f}" in text
    for item in expected["semester_gpa"]:
        assert f"{item['gpa']:.2f}" in text


def test_pending_marks_are_not_on_the_mark_sheet(client, student):
    add_result("CS301", "Published Course", 1, 4, 80, 90)
    add_result("CS302", "Unpublished Course", 1, 3, 70, 70, status=PENDING_APPROVAL)

    text = pdf_text(client.get(f"/api/students/{SRN}/transcript", headers=student))

    assert "CS301" in text
    assert "CS302" not in text
    assert "Unpublished Course" not in text


def test_semester_filter_shows_only_that_semester(client, student):
    add_result("CS301", "First Semester Course", 1, 4, 80, 90)
    add_result("CS401", "Second Semester Course", 2, 4, 70, 80)

    response = client.get(f"/api/students/{SRN}/transcript?semester=2", headers=student)
    text = pdf_text(response)

    assert response.status_code == 200
    assert "CS401" in text
    assert "CS301" not in text
    assert "Semester 2" in text
    assert f"marksheet_{SRN}_sem2.pdf" in response.headers["Content-Disposition"]


@pytest.mark.parametrize("value", ["0", "9", "abc", "-1", "2.5"])
def test_invalid_semester_is_rejected(client, student, value):
    add_result("CS301", "Course", 1, 4, 80, 90)

    response = client.get(f"/api/students/{SRN}/transcript?semester={value}", headers=student)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "ERR_VALIDATION"


def test_student_with_no_published_results_gets_not_found(client, student):
    response = client.get(f"/api/students/{SRN}/transcript", headers=student)

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ERR_NO_RESULTS"


def test_semester_without_results_gets_not_found(client, student):
    add_result("CS301", "Course", 1, 4, 80, 90)

    response = client.get(f"/api/students/{SRN}/transcript?semester=3", headers=student)

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "ERR_NO_RESULTS"


def test_student_cannot_download_another_students_mark_sheet(client, student):
    make_profile(OTHER_SRN, "Someone Else")
    add_result("CS301", "Course", 1, 4, 80, 90, srn=OTHER_SRN)

    response = client.get(f"/api/students/{OTHER_SRN}/transcript", headers=student)

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "ERR_FORBIDDEN"


def test_student_gets_same_error_for_unknown_and_existing_srn(client, student):
    make_profile(OTHER_SRN, "Someone Else")

    existing = client.get(f"/api/students/{OTHER_SRN}/transcript", headers=student)
    unknown = client.get("/api/students/UNKNOWN/transcript", headers=student)

    assert existing.status_code == unknown.status_code == 403


def test_me_means_the_logged_in_student(client, student):
    add_result("CS301", "Course", 1, 4, 80, 90)

    response = client.get("/api/students/me/transcript", headers=student)

    assert response.status_code == 200
    assert f"marksheet_{SRN}.pdf" in response.headers["Content-Disposition"]


def test_admin_can_download_any_students_mark_sheet(client):
    make_user("admin", ADMIN)
    make_profile()
    add_result("CS301", "Course", 1, 4, 80, 90)
    admin = headers_for(client, "admin")

    response = client.get(f"/api/students/{SRN}/transcript", headers=admin)

    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")


def test_admin_gets_not_found_for_unknown_student(client):
    make_user("admin", ADMIN)
    admin = headers_for(client, "admin")

    response = client.get("/api/students/UNKNOWN/transcript", headers=admin)

    assert response.status_code == 404


def test_faculty_cannot_download_mark_sheets(client):
    make_user("faculty", FACULTY)
    make_profile()
    add_result("CS301", "Course", 1, 4, 80, 90)

    response = client.get(
        f"/api/students/{SRN}/transcript", headers=headers_for(client, "faculty")
    )

    assert response.status_code == 403


def test_mark_sheet_requires_login(client):
    response = client.get(f"/api/students/{SRN}/transcript")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "ERR_AUTH_FAILED"


def test_names_with_markup_characters_do_not_break_the_pdf(client):
    make_user(SRN, STUDENT)
    make_profile(full_name="A & B <Dharshini>")
    add_result("CS301", "Data & <Structures>", 1, 4, 80, 90)
    headers = headers_for(client, SRN)

    response = client.get(f"/api/students/{SRN}/transcript", headers=headers)

    assert response.status_code == 200
    text = pdf_text(response)
    assert "A & B <Dharshini>" in text
    assert "Data & <Structures>" in text
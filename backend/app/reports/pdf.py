"""Draws the mark sheet PDF. This file only draws: it receives ready-made data
and returns PDF bytes, so it can be tested without a database."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

# Letterhead text. Change these two lines to change the header of every mark sheet.
INSTITUTION_NAME = "PES University"
DOCUMENT_TITLE = "Student Record System - Official Mark Sheet"

_styles = getSampleStyleSheet()
_title = ParagraphStyle("Title", parent=_styles["Title"], fontSize=18, spaceAfter=2)
_subtitle = ParagraphStyle(
    "Subtitle", parent=_styles["Normal"], fontSize=11, alignment=1, spaceAfter=8
)
_heading = ParagraphStyle(
    "Heading", parent=_styles["Heading3"], spaceBefore=10, spaceAfter=4
)
_cell = ParagraphStyle("Cell", parent=_styles["Normal"], fontSize=9, leading=11)
_note = ParagraphStyle(
    "Note", parent=_styles["Normal"], fontSize=8, textColor=colors.grey, spaceBefore=12
)


def _text(value):
    """Escape user data: Paragraph treats < and & as markup and would fail or garble."""
    return escape(str(value))


def _number(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _grid(extra=()):
    return TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            *extra,
        ]
    )


def render_marksheet(student, results, gpa, semester=None, generated_at=None):
    """student: profile dict; results: list of result dicts (with course_title);
    gpa: {"semester_gpa": [...], "cgpa": float}; semester: int or None (all)."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"Mark sheet {student['srn']}",
        author=INSTITUTION_NAME,
    )

    story = [
        Paragraph(_text(INSTITUTION_NAME), _title),
        Paragraph(_text(DOCUMENT_TITLE), _subtitle),
    ]

    scope = f"Semester {semester}" if semester else "All semesters"
    details = [
        ["Name", _text(student["full_name"]), "SRN", _text(student["srn"])],
        ["Program", _text(student["program"]), "Branch", _text(student["branch"])],
        ["Current semester", str(student["semester"]), "Showing", scope],
    ]
    details_table = Table(
        [[Paragraph(cell, _cell) for cell in row] for row in details],
        colWidths=[32 * mm, 52 * mm, 25 * mm, 61 * mm],
    )
    details_table.setStyle(
        _grid([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
               ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold")])
    )
    story += [details_table, Paragraph("Published results", _heading)]

    header = ["Sem", "Code", "Course title", "Credits", "Internal", "End-sem",
              "Total", "Grade", "Points"]
    rows = [header]
    for result in results:
        rows.append([
            str(result["semester"]),
            result["course_code"],
            Paragraph(_text(result["course_title"]), _cell),
            str(result["credits"]),
            _number(result["internal_marks"]),
            _number(result["end_semester_marks"]),
            _number(result["total_marks"]),
            result["grade"],
            str(result["grade_points"]),
        ])
    results_table = Table(
        rows,
        colWidths=[10 * mm, 22 * mm, 56 * mm, 15 * mm, 16 * mm, 16 * mm,
                   12 * mm, 11 * mm, 12 * mm],
        repeatRows=1,
    )
    results_table.setStyle(_grid([("ALIGN", (3, 0), (-1, -1), "CENTER")]))
    story.append(results_table)

    story.append(Paragraph("Grade point average", _heading))
    gpa_rows = [["Semester", "GPA"]]
    wanted = [item for item in gpa["semester_gpa"]
              if semester is None or item["semester"] == semester]
    for item in wanted:
        gpa_rows.append([f"Semester {item['semester']}", f"{item['gpa']:.2f}"])
    gpa_rows.append(["CGPA (all published semesters)", f"{gpa['cgpa']:.2f}"])
    gpa_table = Table(gpa_rows, colWidths=[70 * mm, 30 * mm])
    gpa_table.setStyle(_grid([("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    story.append(gpa_table)

    if generated_at is not None:
        stamp = generated_at.strftime("%d-%m-%Y %H:%M")
        story.append(Paragraph(
            f"Generated on {stamp} UTC. This is a computer-generated document.", _note
        ))

    document.build(story)
    return buffer.getvalue()
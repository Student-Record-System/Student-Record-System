cat > docs/performance/STU-NF-001-page-load.md <<'EOF'
# STU-NF-001: page-load performance

**Requirement:** 95% of page loads (dashboard, profile, course list, transcript)
complete within 3 seconds under normal load (SRS section 5, test case TC-Perf-01).

**Result:** PASS for the conditions measured (see "Limits of this measurement").

## How it was measured

1. **Automated, in CI:** `backend/tests/test_stu_nf_001.py` times each page's API
   call 30 times inside the test client (login 10 times) and fails if the 95th
   percentile is over 3 seconds. It measures server work only.
2. **Running server over HTTP:** `perf/page_load_check.py` made 50 requests per
   page with 5 simultaneous users (login: 10 requests one after another) and
   reported the average, p95 and slowest time.

The 95th percentile uses the nearest-rank method: sort the timings and take the
value at position ceil(0.95 x n).

## Environment

- Date: 05-11-2026
- Machine: 12th Gen Intel(R) Core(TM) i5-1235U, 8 GB RAM, Microsoft Windows 11 Home Single Language
- Backend: Flask development server, Python 3.13.5
- Database: SQLite file (dev.db)
- Data: one demo student, three courses, three published results
  (`backend/seed_demo.py`)

## Results

### API calls behind each page (`perf/page_load_check.py`)

| Page | Endpoint | Calls | Avg (s) | p95 (s) | Max (s) | Result |
|---|---|---|---|---|---|---|
| Login | `/api/auth/login` | 10 | 0.543 | 0.776 | 0.776 | PASS |
| Dashboard (results) | `/api/student/results` | 50 | 0.043 | 0.094 | 0.126 | PASS |
| Dashboard (GPA) | `/api/student/gpa` | 50 | 0.069 | 0.106 | 0.124 | PASS |
| Profile | `/api/students/me` | 50 | 0.071 | 0.117 | 0.140 | PASS |
| Course list | `/api/courses` | 50 | 0.044 | 0.068 | 0.076 | PASS |
| Transcript (PDF) | `/api/students/me/transcript` | 50 | 0.110 | 0.142 | 0.172 | PASS |

## Conclusion

All six measured calls finished well inside the 3-second target. The slowest
p95 was login at 0.776 s, which is expected because password hashing is slow by
design. The slowest page-data call was the transcript PDF at 0.142 s, about 5%
of the limit. STU-NF-001 is met for the conditions listed below.

## Limits of this measurement

- Only the API calls behind the pages were measured. The time the browser takes
  to draw each page was not measured.
- Everything ran on one machine, so there was no network delay between the
  browser and the server.
- 5 simultaneous users is not production load. STU-NF-003 (3,000 users) is a
  separate requirement and was not verified here.
- The Flask development server and a SQLite database are not a production
  setup. Results with MySQL may differ.
- Login was measured with only 10 requests, so its p95 equals its slowest
  sample.
- The React app has no course-list or transcript page yet, so those two were
  measured at the API call that will feed them. The dashboard makes no data
  call of its own, so its data calls are measured as "Dashboard (results)" and
  "Dashboard (GPA)".
EOF
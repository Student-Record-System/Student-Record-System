import { useState } from "react";
import { api, apiForm, download } from "../api.js";
import { useAuth } from "../auth.jsx";

const initialValue = (fields) => Object.fromEntries(fields.map((field) => [field.name, field.defaultValue ?? ""]));

function ActionCard({ title, description, method = "GET", path, fields = [], buildPath, buildBody, downloadName, multipart = false }) {
  const [values, setValues] = useState(() => initialValue(fields));
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError(""); setResult(null);
    try {
      const resolvedPath = buildPath ? buildPath(values) : path;
      if (downloadName) {
        await download(resolvedPath, downloadName(values));
        setResult({ message: "Download started." });
      } else if (multipart) {
        const data = new FormData();
        fields.forEach((field) => {
          const value = values[field.name];
          if (field.type === "file") data.append(field.name, value);
          else if (value !== "") data.append(field.name, value);
        });
        setResult(await apiForm(resolvedPath, data, { method }));
      } else {
        setResult(await api(resolvedPath, { method, body: buildBody ? buildBody(values) : undefined }));
      }
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <article className="action-card">
    <h3>{title}</h3>
    {description && <p>{description}</p>}
    <form onSubmit={submit}>
      {fields.map((field) => <label key={field.name}>{field.label}
        {field.type === "textarea" ? <textarea required={field.required !== false} value={values[field.name]} placeholder={field.placeholder} onChange={(e) => setValues({ ...values, [field.name]: e.target.value })} />
          : field.type === "file" ? <input required type="file" accept={field.accept} onChange={(e) => setValues({ ...values, [field.name]: e.target.files[0] })} />
          : <input required={field.required !== false} type={field.type || "text"} value={values[field.name]} placeholder={field.placeholder} onChange={(e) => setValues({ ...values, [field.name]: e.target.value })} />}
      </label>)}
      <button disabled={busy}>{busy ? "Working..." : method === "GET" ? "Load" : "Submit"}</button>
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    {result && <pre className="result">{JSON.stringify(result, null, 2)}</pre>}
  </article>;
}

const courseFields = [
  { name: "code", label: "Course code" }, { name: "title", label: "Title" },
  { name: "credits", label: "Credits", type: "number" }, { name: "semester", label: "Semester", type: "number" },
  { name: "department", label: "Department" },
];
const jsonBody = (fields) => (values) => Object.fromEntries(fields.map((field) => [field, Number.isNaN(Number(values[field])) || values[field] === "" ? values[field] : Number(values[field]) ]));

function StudentWorkspace({ user }) {
  return <section><h2>Student portal</h2><div className="action-grid">
    <ActionCard title="My profile" path="/students/me" />
    <ActionCard title="Request profile change" method="PATCH" path="/students/me" fields={[{ name: "changes", label: "Changes as JSON", type: "textarea", placeholder: '{"phone":"9876543210"}' }]} buildBody={(v) => JSON.parse(v.changes)} />
    <ActionCard title="Course catalogue" path="/courses" />
    <ActionCard title="Enroll in a course" method="POST" path="/enrollments" fields={[{ name: "course_code", label: "Course code" }]} buildBody={(v) => ({ course_code: v.course_code })} />
    <ActionCard title="My current enrollment" path="/enrollments/current" />
    <ActionCard title="Attendance summary" path="/students/me/attendance" />
    <ActionCard title="Attendance records" path="/students/me/attendance/records" />
    <ActionCard title="Published results" path="/student/results" />
    <ActionCard title="GPA and CGPA" path="/student/gpa" />
    <ActionCard title="Download transcript" fields={[{ name: "semester", label: "Semester (optional)", required: false }]} buildPath={(v) => `/students/me/transcript${v.semester ? `?semester=${encodeURIComponent(v.semester)}` : ""}`} downloadName={() => "transcript.pdf"} />
    <ActionCard title="Request grade review" method="POST" path="/grade-reviews" fields={[{ name: "course_code", label: "Course code" }, { name: "reason", label: "Reason", type: "textarea" }]} buildBody={(v) => v} />
    <ActionCard title="My grade-review requests" path="/grade-reviews" />
    <ActionCard title="My fee invoices" path="/fees/invoices" />
    <ActionCard title="Initiate invoice payment" method="POST" fields={[{ name: "invoice_id", label: "Invoice ID", type: "number" }]} buildPath={(v) => `/fees/invoices/${v.invoice_id}/pay`} />
    <ActionCard title="Confirm payment" method="POST" fields={[{ name: "payment_id", label: "Payment ID", type: "number" }, { name: "transaction_id", label: "Transaction ID" }, { name: "signature", label: "Gateway signature" }]} buildPath={(v) => `/fees/payments/${v.payment_id}/confirm`} buildBody={(v) => ({ transaction_id: v.transaction_id, signature: v.signature })} />
    <ActionCard title="Download payment receipt" fields={[{ name: "payment_id", label: "Payment ID", type: "number" }]} buildPath={(v) => `/fees/payments/${v.payment_id}/receipt`} downloadName={() => "fee-receipt.pdf"} />
    <ActionCard title="My profile documents" buildPath={() => `/students/${encodeURIComponent(user.login_id)}/documents`} />
    <ActionCard title="Download profile document" fields={[{ name: "document_id", label: "Document ID", type: "number" }]} buildPath={(v) => `/students/${encodeURIComponent(user.login_id)}/documents/${v.document_id}`} downloadName={() => "student-document"} />
  </div></section>;
}

function FacultyWorkspace() {
  return <section><h2>Faculty portal</h2><div className="action-grid">
    <ActionCard title="Course catalogue" path="/courses" />
    <ActionCard title="Course roster" fields={[{ name: "course_code", label: "Course code" }]} buildPath={(v) => `/courses/${v.course_code}/roster`} />
    <ActionCard title="Record attendance" method="POST" fields={[{ name: "course_code", label: "Course code" }, { name: "attendance_date", label: "Date", type: "date" }, { name: "session", label: "Session" }, { name: "records", label: "Records as JSON", type: "textarea", placeholder: '[{"srn":"PES...","status":"Present"}]' }]} buildPath={(v) => `/courses/${v.course_code}/attendance`} buildBody={(v) => ({ ...v, records: JSON.parse(v.records) })} />
    <ActionCard title="Attendance summary" fields={[{ name: "course_code", label: "Course code" }]} buildPath={(v) => `/courses/${v.course_code}/attendance/summary`} />
    <ActionCard title="Submit marks" method="POST" fields={[{ name: "course_code", label: "Course code" }, { name: "srn", label: "Student SRN" }, { name: "internal_marks", label: "Internal marks", type: "number" }, { name: "end_semester_marks", label: "End-semester marks", type: "number" }]} buildPath={(v) => `/courses/${v.course_code}/marks`} buildBody={(v) => ({ srn: v.srn, internal_marks: Number(v.internal_marks), end_semester_marks: Number(v.end_semester_marks) })} />
    <ActionCard title="Modify marks" method="PUT" fields={[{ name: "course_code", label: "Course code" }, { name: "srn", label: "Student SRN" }, { name: "internal_marks", label: "Internal marks", type: "number" }, { name: "end_semester_marks", label: "End-semester marks", type: "number" }]} buildPath={(v) => `/courses/${v.course_code}/marks/${v.srn}`} buildBody={(v) => ({ internal_marks: Number(v.internal_marks), end_semester_marks: Number(v.end_semester_marks) })} />
  </div></section>;
}

function AdminWorkspace() {
  return <section><h2>Administrator workspace</h2><div className="action-grid">
    <ActionCard title="Course catalogue" path="/courses" />
    <ActionCard title="Create course" method="POST" path="/courses" fields={courseFields} buildBody={jsonBody(["code", "title", "credits", "semester", "department"])} />
    <ActionCard title="Assign faculty" method="PUT" fields={[{ name: "course_code", label: "Course code" }, { name: "faculty_login_id", label: "Faculty login ID" }]} buildPath={(v) => `/courses/${v.course_code}/faculty`} buildBody={(v) => ({ faculty_login_id: v.faculty_login_id })} />
    <ActionCard title="Set prerequisites" method="PUT" fields={[{ name: "course_code", label: "Course code" }, { name: "prerequisites", label: "Prerequisites (comma-separated)", required: false }]} buildPath={(v) => `/courses/${v.course_code}/prerequisites`} buildBody={(v) => ({ prerequisites: v.prerequisites ? v.prerequisites.split(",").map((x) => x.trim()).filter(Boolean) : [] })} />
    <ActionCard title="Enrollment window" path="/config/enrollment-window" />
    <ActionCard title="Set enrollment window" method="PUT" path="/config/enrollment-window" fields={[{ name: "start", label: "Start", type: "datetime-local" }, { name: "end", label: "End", type: "datetime-local" }]} buildBody={(v) => ({ start: v.start, end: v.end })} />
    <ActionCard title="Credit limit" fields={[{ name: "semester", label: "Semester", type: "number" }]} buildPath={(v) => `/config/credit-limit/${v.semester}`} />
    <ActionCard title="Set credit limit" method="PUT" path="/config/credit-limit" fields={[{ name: "semester", label: "Semester", type: "number" }, { name: "max_credits", label: "Maximum credits", type: "number" }]} buildBody={jsonBody(["semester", "max_credits"])} />
    <ActionCard title="Pending marks" path="/admin/marks/pending" />
    <ActionCard title="Approve marks" method="POST" fields={[{ name: "course_code", label: "Course code" }, { name: "srn", label: "Student SRN" }]} buildPath={(v) => `/admin/marks/${v.course_code}/${v.srn}/approve`} />
    <ActionCard title="Grade change history" fields={[{ name: "course_code", label: "Course code" }, { name: "srn", label: "Student SRN" }]} buildPath={(v) => `/admin/grades/${v.course_code}/${v.srn}/history`} />
    <ActionCard title="Grade review window" path="/config/review-window" />
    <ActionCard title="Set review window" method="PUT" path="/config/review-window" fields={[{ name: "days", label: "Days", type: "number" }]} buildBody={jsonBody(["days"])} />
    <ActionCard title="Grade-review requests" path="/grade-reviews" />
    <ActionCard title="Fee structures" path="/fees/structures" />
    <ActionCard title="Create fee structure" method="POST" path="/fees/structures" fields={[{ name: "program", label: "Program" }, { name: "semester", label: "Semester", type: "number" }, { name: "course_code", label: "Course code (optional)", required: false }, { name: "amount", label: "Amount", type: "number" }]} buildBody={(v) => ({ ...v, semester: Number(v.semester) })} />
    <ActionCard title="Generate fee invoices" method="POST" path="/fees/invoices/generate" />
    <ActionCard title="Create fee invoice" method="POST" path="/fees/invoices" fields={[{ name: "student_id", label: "Student user ID", type: "number" }, { name: "description", label: "Description" }, { name: "amount", label: "Amount", type: "number" }, { name: "due_date", label: "Due date (optional)", type: "date", required: false }]} buildBody={(v) => ({ ...v, student_id: Number(v.student_id) })} />
    <ActionCard title="Reminder settings" path="/fees/reminder-settings" />
    <ActionCard title="Set reminder days" method="PUT" path="/fees/reminder-settings" fields={[{ name: "days_before_due", label: "Days before due", type: "number" }]} buildBody={jsonBody(["days_before_due"])} />
    <ActionCard title="Fee enrollment threshold" path="/fees/enrollment-threshold" />
    <ActionCard title="Set fee threshold" method="PUT" path="/fees/enrollment-threshold" fields={[{ name: "threshold", label: "Threshold amount", type: "number" }]} buildBody={(v) => v} />
    <ActionCard title="Fee enrollment overrides" fields={[{ name: "student_srn", label: "Student SRN filter (optional)", required: false }]} buildPath={(v) => `/fees/enrollment-overrides${v.student_srn ? `?student_srn=${encodeURIComponent(v.student_srn)}` : ""}`} />
    <ActionCard title="Create fee override" method="POST" path="/fees/enrollment-overrides" fields={[{ name: "student_srn", label: "Student SRN" }, { name: "semester", label: "Semester", type: "number" }, { name: "reason", label: "Reason", type: "textarea" }]} buildBody={(v) => ({ ...v, semester: Number(v.semester) })} />
    <ActionCard title="Approve profile change" method="POST" fields={[{ name: "request_id", label: "Request ID", type: "number" }]} buildPath={(v) => `/students/requests/${v.request_id}/approve`} />
    <ActionCard title="Reject profile change" method="POST" fields={[{ name: "request_id", label: "Request ID", type: "number" }]} buildPath={(v) => `/students/requests/${v.request_id}/reject`} />
    <ActionCard title="Pending profile changes" path="/students/requests" />
    <ActionCard title="Upload student document" method="POST" multipart fields={[{ name: "srn", label: "Student SRN" }, { name: "file", label: "Document (PDF)", type: "file", accept: "application/pdf" }]} buildPath={(v) => `/students/${v.srn}/documents`} />
    <ActionCard title="Student documents" fields={[{ name: "srn", label: "Student SRN" }]} buildPath={(v) => `/students/${encodeURIComponent(v.srn)}/documents`} />
    <ActionCard title="Download student document" fields={[{ name: "srn", label: "Student SRN" }, { name: "document_id", label: "Document ID", type: "number" }]} buildPath={(v) => `/students/${encodeURIComponent(v.srn)}/documents/${v.document_id}`} downloadName={(v) => `${v.srn}-document`} />
    <ActionCard title="Search audit log" fields={[{ name: "event_type", label: "Event type (optional)", required: false }, { name: "user_id", label: "User ID (optional)", type: "number", required: false }, { name: "profile_id", label: "Profile ID (optional)", type: "number", required: false }]} buildPath={(v) => {
      const query = new URLSearchParams(Object.entries(v).filter(([, value]) => value !== ""));
      return `/admin/audit-events${query.size ? `?${query}` : ""}`;
    }} />
    <ActionCard title="Download student transcript" fields={[{ name: "srn", label: "Student SRN" }, { name: "semester", label: "Semester (optional)", required: false }]} buildPath={(v) => `/students/${v.srn}/transcript${v.semester ? `?semester=${encodeURIComponent(v.semester)}` : ""}`} downloadName={(v) => `${v.srn}-transcript.pdf`} />
  </div></section>;
}

export default function Operations() {
  const { user } = useAuth();
  if (user.role === "Student") return <StudentWorkspace user={user} />;
  if (user.role === "Faculty") return <FacultyWorkspace />;
  return <AdminWorkspace />;
}

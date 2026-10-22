import { useState } from "react";
import { api } from "../api.js";

const EMPTY = {
  srn: "",
  full_name: "",
  email: "",
  phone: "",
  date_of_birth: "",
  gender: "",
  address: "",
  program: "",
  branch: "",
  semester: "",
};

const FIELDS = [
  ["srn", "SRN", "text"],
  ["full_name", "Full name", "text"],
  ["email", "Email", "email"],
  ["phone", "Phone", "text"],
  ["date_of_birth", "Date of birth", "date"],
  ["gender", "Gender", "text"],
  ["address", "Address (optional)", "text"],
  ["program", "Program", "text"],
  ["branch", "Branch", "text"],
  ["semester", "Semester (1 to 8)", "number"],
];

export default function StudentProfiles() {
  const [form, setForm] = useState(EMPTY);
  const [lookupSrn, setLookupSrn] = useState("");
  const [editingSrn, setEditingSrn] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function startNew() {
    setForm(EMPTY);
    setEditingSrn(null);
    setMessage("");
    setError("");
  }

  async function handleLookup(event) {
    event.preventDefault();
    setMessage("");
    setError("");
    try {
      const data = await api(`/students/${encodeURIComponent(lookupSrn.trim())}`);
      setForm({ ...EMPTY, ...data, address: data.address ?? "", semester: String(data.semester) });
      setEditingSrn(data.srn);
      setMessage(`Loaded ${data.srn}. Edit the fields and save to update it.`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSave(event) {
    event.preventDefault();
    setMessage("");
    setError("");
    const payload = { ...form, semester: Number(form.semester) };
    if (!payload.address.trim()) delete payload.address;
    try {
      if (editingSrn) {
        await api(`/students/${encodeURIComponent(editingSrn)}`, { method: "PUT", body: payload });
        setMessage(`Profile ${editingSrn} updated.`);
      } else {
        const created = await api("/students", { method: "POST", body: payload });
        setMessage(`Profile created for ${created.srn}.`);
        setForm(EMPTY);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section>
      <h2>Student profiles</h2>

      <form onSubmit={handleLookup}>
        <label htmlFor="lookup">Find a profile by SRN</label>
        <div className="row">
          <input
            id="lookup"
            value={lookupSrn}
            onChange={(e) => setLookupSrn(e.target.value)}
            required
          />
          <button type="submit">Find</button>
        </div>
      </form>

      <h3>{editingSrn ? `Edit ${editingSrn}` : "New profile"}</h3>
      <form onSubmit={handleSave}>
        {FIELDS.map(([name, label, type]) => (
          <div key={name} className="field">
            <label htmlFor={name}>{label}</label>
            <input
              id={name}
              type={type}
              min={type === "number" ? 1 : undefined}
              max={type === "number" ? 8 : undefined}
              value={form[name]}
              readOnly={name === "srn" && editingSrn !== null}
              onChange={(e) => update(name, e.target.value)}
              required={name !== "address"}
            />
          </div>
        ))}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {message && (
          <p role="status" className="success">
            {message}
          </p>
        )}
        <div className="row">
          <button type="submit">{editingSrn ? "Save changes" : "Create profile"}</button>
          <button type="button" onClick={startNew}>
            Clear
          </button>
        </div>
      </form>
    </section>
  );
}
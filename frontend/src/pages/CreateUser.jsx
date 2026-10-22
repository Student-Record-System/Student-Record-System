import { useState } from "react";
import { api } from "../api.js";

const ROLES = ["Student", "Faculty", "Administrator"];
const EMPTY = { login_id: "", email: "", role: "Student" };

export default function CreateUser() {
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(null);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setCreated(null);
    try {
      const result = await api("/users", { method: "POST", body: form });
      setCreated(result);
      setForm(EMPTY);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section>
      <h2>Create user</h2>
      <form onSubmit={handleSubmit}>
        <label htmlFor="login_id">Login ID (SRN or employee ID)</label>
        <input
          id="login_id"
          value={form.login_id}
          onChange={(e) => update("login_id", e.target.value)}
          required
        />
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
          required
        />
        <label htmlFor="role">Role</label>
        <select
          id="role"
          value={form.role}
          onChange={(e) => update("role", e.target.value)}
        >
          {ROLES.map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </select>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {created && (
          <p role="status" className="success">
            Account created for {created.login_id}. The login details were sent
            to {created.email}.
          </p>
        )}
        <button type="submit">Create user</button>
      </form>
    </section>
  );
}
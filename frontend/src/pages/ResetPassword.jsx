import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

export default function ResetPassword() {
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [password, setPassword] = useState("");
  const [requested, setRequested] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function requestOtp(event) {
    event.preventDefault(); setError(""); setMessage("");
    try {
      const result = await api("/auth/forgot-password", { method: "POST", body: { email } });
      setRequested(true); setMessage(result.message || "If the account exists, an OTP has been sent.");
    } catch (err) { setError(err.message); }
  }
  async function reset(event) {
    event.preventDefault(); setError(""); setMessage("");
    try {
      const result = await api("/auth/reset-password", { method: "POST", body: { email, otp, new_password: password } });
      setMessage(result.message || "Password reset. You can now log in.");
    } catch (err) { setError(err.message); }
  }
  return <main className="narrow"><h1>Reset password</h1>
    <form onSubmit={requestOtp}><label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label><button>Request OTP</button></form>
    {requested && <form onSubmit={reset}><label>OTP<input value={otp} onChange={(e) => setOtp(e.target.value)} inputMode="numeric" required /></label><label>New password<input type="password" minLength="8" value={password} onChange={(e) => setPassword(e.target.value)} required /></label><button>Reset password</button></form>}
    {error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}<p><Link to="/login">Back to log in</Link></p>
  </main>;
}

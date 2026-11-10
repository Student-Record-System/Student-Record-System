import { Link } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Dashboard() {
  const { user } = useAuth();
  const isAdmin = user.role === "Administrator";
  return (
    <section>
      <h2>Welcome, {user.login_id}</h2>
      <p>
        You are logged in as <strong>{user.role}</strong>.
      </p>
      <p>{isAdmin ? "Manage users and profiles, or open the administrator workspace." : "Open your workspace to use courses, attendance, grades, and fee services."}</p>
      <Link to="/workspace">Open workspace</Link>
    </section>
  );
}

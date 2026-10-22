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
      {isAdmin ? (
        <p>Use the menu to create users and manage student profiles.</p>
      ) : (
        <p>
          Your portal pages (courses, attendance, grades, fees) will appear here
          as those features are built.
        </p>
      )}
    </section>
  );
}
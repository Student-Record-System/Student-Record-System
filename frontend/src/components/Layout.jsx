import { Link, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const isAdmin = user.role === "Administrator";

  return (
    <>
      <header className="topbar">
        <h1>Student Record System</h1>
        <nav aria-label="Main">
          <Link to="/">Dashboard</Link>
          {isAdmin && <Link to="/students">Student profiles</Link>}
          {isAdmin && <Link to="/users/new">Create user</Link>}
        </nav>
        <div className="who">
          <span>
            {user.login_id} ({user.role})
          </span>
          <button onClick={handleLogout}>Log out</button>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
    </>
  );
}
import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import CreateUser from "./pages/CreateUser.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Login from "./pages/Login.jsx";
import StudentProfiles from "./pages/StudentProfiles.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route
          path="/students"
          element={
            <ProtectedRoute roles={["Administrator"]}>
              <StudentProfiles />
            </ProtectedRoute>
          }
        />
        <Route
          path="/users/new"
          element={
            <ProtectedRoute roles={["Administrator"]}>
              <CreateUser />
            </ProtectedRoute>
          }
        />
      </Route>
    </Routes>
  );
}
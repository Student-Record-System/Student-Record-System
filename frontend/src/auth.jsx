import { createContext, useContext, useState } from "react";
import { api, clearSession, getStoredUser, saveSession } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getStoredUser());

  async function login(loginId, password) {
    const data = await api("/auth/login", {
      method: "POST",
      body: { login_id: loginId, password },
    });
    saveSession(data.access_token, data.user);
    setUser(data.user);
    return data.user;
  }

  function logout() {
    clearSession();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
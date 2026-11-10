const TOKEN_KEY = "srs_token";
const USER_KEY = "srs_user";

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function getStoredUser() {
  const raw = sessionStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function saveSession(token, user) {
  sessionStorage.setItem(TOKEN_KEY, token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  constructor(message, code, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  return request(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
}

async function request(path, { method = "GET", headers = {}, body } = {}) {
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      body,
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?", "ERR_NETWORK", 0);
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const err = data && data.error ? data.error : {};
    throw new ApiError(
      err.message || "Something went wrong.",
      err.code || "ERR_UNKNOWN",
      response.status
    );
  }
  return data;
}

export async function apiForm(path, formData, { method = "POST" } = {}) {
  return request(path, { method, body: formData });
}

export async function download(path, filename) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`/api${path}`, { headers });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(data?.error?.message || "Download failed.", data?.error?.code, response.status);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

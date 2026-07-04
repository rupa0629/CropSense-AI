const API_BASE = import.meta.env.VITE_API_BASE || "/api";

const ACCESS_KEY = "cropsense_access_token";
const REFRESH_KEY = "cropsense_refresh_token";

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY) || "";
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY) || "";
}

export function setTokens(accessToken, refreshToken) {
  if (accessToken) localStorage.setItem(ACCESS_KEY, accessToken);
  if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function rawRequest(path, options = {}, auth = true) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (auth) {
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  return { res, data };
}

async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  const { res, data } = await rawRequest(
    "/auth/refresh",
    { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) },
    false,
  );
  if (!res.ok) return false;
  setTokens(data.access_token, data.refresh_token);
  return true;
}

async function request(path, options = {}, auth = true, retry = true) {
  const { res, data } = await rawRequest(path, options, auth);

  if (res.status === 401 && auth && retry) {
    const ok = await refreshAccessToken();
    if (ok) return request(path, options, auth, false);
    clearTokens();
    throw new Error("Session expired. Please login again.");
  }

  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

export async function registerUser(payload) {
  return request("/auth/register", { method: "POST", body: JSON.stringify(payload) }, false);
}

export async function loginUser(payload) {
  const data = await request("/auth/login", { method: "POST", body: JSON.stringify(payload) }, false);
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function logoutCurrentSession() {
  const refreshToken = getRefreshToken();
  if (refreshToken) {
    try {
      await request("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) }, true);
    } catch {
      // ignore
    }
  }
  clearTokens();
}

export async function logoutAllSessions() {
  await request("/auth/logout-all", { method: "POST" }, true);
  clearTokens();
}

export async function getMe() {
  return request("/auth/me", { method: "GET" }, true);
}

export async function getDashboard() {
  return request("/dashboard", { method: "GET" }, true);
}

export async function getHistory(limit = 20) {
  return request(`/history?limit=${limit}`, { method: "GET" }, true);
}

export async function forgotPassword(email) {
  return request("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }, false);
}

export async function resetPassword(resetToken, newPassword) {
  return request(
    "/auth/reset-password",
    { method: "POST", body: JSON.stringify({ reset_token: resetToken, new_password: newPassword }) },
    false,
  );
}

export async function predictImage(file, coordinates = null) {
  const form = new FormData();
  form.append("image", file);
  if (coordinates?.latitude != null && coordinates?.longitude != null) {
    form.append("latitude", String(coordinates.latitude));
    form.append("longitude", String(coordinates.longitude));
  }

  const token = getAccessToken();
  const { res, data } = await (async () => {
    const r = await fetch(`${API_BASE}/predict`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    return { res: r, data: await r.json().catch(() => ({})) };
  })();

  if (res.status === 401) {
    const refreshed = await refreshAccessToken();
    if (!refreshed) {
      clearTokens();
      throw new Error("Session expired. Please login again.");
    }
    return predictImage(file, coordinates);
  }

  if (!res.ok) throw new Error(data.detail || "Prediction failed");
  return data;
}

export async function fetchWeather(payload) {
  return request("/weather", { method: "POST", body: JSON.stringify(payload) }, true);
}

export async function askChatbot(message, context = {}) {
  return request("/chat", { method: "POST", body: JSON.stringify({ message, context }) }, true);
}

export async function getAdminOverview() {
  return request("/admin/overview", { method: "GET" }, true);
}

export async function getAdminUsers() {
  return request("/admin/users", { method: "GET" }, true);
}

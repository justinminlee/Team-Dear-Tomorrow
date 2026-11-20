const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type AuthUser = { id: string; email: string | null; username: string };

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
  return data as T;
}

export const authApi = {
  register: (username: string, email: string, password: string) =>
    apiRequest<{ message: string; requires_email_confirmation: boolean; user?: AuthUser }>("/auth/register", {
      method: "POST", body: JSON.stringify({ username, email, password }),
    }),
  login: (email: string, password: string) =>
    apiRequest<{ user: AuthUser }>("/auth/login", {
      method: "POST", body: JSON.stringify({ email, password }),
    }),
  me: () => apiRequest<{ user: AuthUser }>("/auth/me"),
  logout: () => apiRequest<{ message: string }>("/auth/logout", { method: "POST" }),
};

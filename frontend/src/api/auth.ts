// Local dev: backend on localhost:8000. Production (Vercel): same domain as the
// site — vercel.json rewrites /auth, /questionnaire, /api to the backend.
export const API_URL = (
  import.meta.env.VITE_API_URL || (import.meta.env.DEV ? "http://localhost:8000" : "")
).replace(/\/$/, "");

export type AuthUser = { id: string; email: string | null; username: string };

/** Error from the backend, with the HTTP status (0 = server unreachable). */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      credentials: "include",
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch {
    throw new ApiError("Can't reach the server. Is the backend running?", 0);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string" ? detail
      : typeof detail?.message === "string" ? [detail.message, ...(detail.errors ?? [])].join("\n")
      : "Request failed";
    throw new ApiError(message, response.status);
  }
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

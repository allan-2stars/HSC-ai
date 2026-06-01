const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw { status: res.status, detail: body.detail ?? "Request failed" };
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  refresh_token: string;
}

export interface MeResponse {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
}

export interface StudentResponse {
  id: string;
  display_name: string;
  year_level: number | null;
  first_login_completed: boolean;
  login_email?: string;
  temp_password?: string;
}

export const api = {
  register: (email: string, password: string, display_name: string) =>
    request<TokenResponse>("/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name }),
    }),

  login: (email: string, password: string) =>
    request<TokenResponse>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: (refresh_token: string, token: string) =>
    request<void>("/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token }),
    }, token),

  me: (token: string) => request<MeResponse>("/v1/me", {}, token),

  listStudents: (token: string) =>
    request<StudentResponse[]>("/v1/parents/students", {}, token),

  createStudent: (
    display_name: string,
    year_level: number | null,
    token: string,
  ) =>
    request<StudentResponse>("/v1/parents/students", {
      method: "POST",
      body: JSON.stringify({ display_name, year_level }),
    }, token),
};

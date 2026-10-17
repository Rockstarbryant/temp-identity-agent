import { clearCache } from "@/lib/cache";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : "Request failed";
    super(detail);
    this.status = status;
    this.body = body;
  }
}

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("tia_access_token");
}

export function setTokens(access: string, refresh: string) {
  window.localStorage.setItem("tia_access_token", access);
  window.localStorage.setItem("tia_refresh_token", refresh);
}

export function clearTokens() {
  window.localStorage.removeItem("tia_access_token");
  window.localStorage.removeItem("tia_refresh_token");
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("tia_refresh_token");
}

async function request<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const token = getAccessToken();
  const optionHeaders = options.headers as Record<string, string> | undefined;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...optionHeaders,
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401 && retry) {
    const refreshed = await tryRefresh();
    if (refreshed) return request<T>(path, options, false);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body);
  }
  if (res.status === 204 || res.status === 205) return undefined as T;
  return res.json();
}

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_URL}/api/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    window.localStorage.setItem("tia_access_token", data.access);
    return true;
  } catch {
    return false;
  }
}

// --- Types (mirror the DRF serializers) ---------------------------------------

export interface User {
  id: string;
  username: string;
  email: string;
  date_joined: string;
}

export interface RegistrationStep {
  step_index: number;
  action: string;
  tool_name: string;
  /** Secret-free description, e.g. "Clicked the “Sign up” button". May be empty. */
  detail: string;
  success: boolean;
  error: string;
  created_at: string;
}

export type JobState =
  | "queued" | "starting" | "opening_site" | "analyzing" | "identity_created"
  | "filling_form" | "submitting" | "waiting_for_email" | "verifying"
  | "completed" | "captcha_required" | "human_action_required"
  | "failed" | "cancelled" | "expired";

export interface RegistrationJob {
  id: string;
  domain: string;
  state: JobState;
  identity_id: string | null;
  error_code: string;
  error_message: string;
  /** AI provider and concrete model that handled the job ("" until the first call). */
  provider: string;
  model: string;
  /** Vault entry created by a completed job. */
  account_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface RegistrationJobDetail extends RegistrationJob {
  steps: RegistrationStep[];
}

export interface TemporaryAccountSummary {
  id: string;
  domain: string;
  email: string;
  username: string;
  status: "active" | "expired" | "deleted";
  revealed_at: string | null;
  expires_at: string;
  created_at: string;
}

export interface RevealedCredentials {
  email: string;
  username: string;
  password: string;
  domain: string;
  expires_at: string;
}

interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// --- Auth ------------------------------------------------------------------

export async function register(username: string, password: string, email = "") {
  return request<User>("/api/auth/register/", {
    method: "POST",
    body: JSON.stringify({ username, password, email }),
  });
}

export async function login(username: string, password: string) {
  const data = await request<{ access: string; refresh: string }>("/api/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setTokens(data.access, data.refresh);
  return data;
}

export async function logout() {
  const refresh = getRefreshToken();
  try {
    if (refresh) {
      await request("/api/auth/logout/", { method: "POST", body: JSON.stringify({ refresh }) });
    }
  } finally {
    clearTokens();
    clearCache();
  }
}

export async function getMe() {
  return request<User>("/api/me/");
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}

// --- Registration jobs -------------------------------------------------------

export async function createRegistrationJob(url: string) {
  return request<RegistrationJob>("/api/registration-jobs/", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export async function listRegistrationJobs() {
  return request<Paginated<RegistrationJob>>("/api/registration-jobs/");
}

export async function getRegistrationJob(id: string) {
  return request<RegistrationJobDetail>(`/api/registration-jobs/${id}/`);
}

export async function resumeRegistrationJob(id: string) {
  return request<{ detail: string; id: string }>(`/api/registration-jobs/${id}/resume/`, { method: "POST" });
}

export async function cancelRegistrationJob(id: string) {
  return request<RegistrationJob>(`/api/registration-jobs/${id}/cancel/`, { method: "POST" });
}

export async function retryRegistrationJob(id: string) {
  return request<RegistrationJob>(`/api/registration-jobs/${id}/retry/`, { method: "POST" });
}

export async function deleteRegistrationJob(id: string) {
  return request<void>(`/api/registration-jobs/${id}/`, { method: "DELETE" });
}

export async function clearFinishedJobs() {
  return request<{ cleared: number }>("/api/registration-jobs/clear-finished/", { method: "POST" });
}

// --- Account vault -----------------------------------------------------------

export async function listAccounts() {
  return request<Paginated<TemporaryAccountSummary>>("/api/accounts/");
}

export async function getAccount(id: string) {
  return request<TemporaryAccountSummary>(`/api/accounts/${id}/`);
}

export async function revealCredentials(id: string) {
  return request<RevealedCredentials>(`/api/accounts/${id}/reveal-credentials/`, { method: "POST" });
}

export async function deleteAccount(id: string) {
  return request<void>(`/api/accounts/${id}/`, { method: "DELETE" });
}

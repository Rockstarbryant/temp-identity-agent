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
    if (refreshRejected) handleSessionExpired(path);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body);
  }
  if (res.status === 204 || res.status === 205) return undefined as T;
  return res.json();
}

/** True only when the server explicitly rejected the refresh token (not on a network error). */
let refreshRejected = false;

/**
 * The session is over: drop the tokens and send the user to log in, remembering where they were.
 * Auth endpoints are excluded so a wrong password on the login form does not trigger a redirect.
 */
function handleSessionExpired(path: string) {
  if (typeof window === "undefined" || path.startsWith("/api/auth/")) return;
  if (!getAccessToken() && !getRefreshToken()) return;
  clearTokens();
  clearCache();
  const here = window.location.pathname + window.location.search;
  if (!window.location.pathname.startsWith("/login")) {
    window.location.assign(`/login?next=${encodeURIComponent(here)}`);
  }
}

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  refreshRejected = false;
  if (!refresh) {
    refreshRejected = true; // an access token with nothing to renew it: the session is over
    return false;
  }
  try {
    const res = await fetch(`${API_URL}/api/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
    if (!res.ok) {
      refreshRejected = res.status === 400 || res.status === 401 || res.status === 403;
      return false;
    }
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
  | "waiting_for_user" | "completed" | "captcha_required" | "human_action_required"
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
  kind: "registration" | "form" | "account_setup" | "account_task";
  source: "web" | "mcp";
  account_mode: "temporary" | "permanent";
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  /** A CAPTCHA/manual step stopped the agent: the user can sign up by hand with the kit. */
  manual_available?: boolean;
}

export interface PendingQuestion {
  id: string;
  key: string;
  question: string;
  options: string[];
  sensitive: boolean;
  created_at: string;
}

export interface RegistrationJobDetail extends RegistrationJob {
  steps: RegistrationStep[];
  pending_question: PendingQuestion | null;
  /** Form jobs: {submitted: [{question, answer}], note}. MCP jobs: {summary, data}. */
  result: {
    submitted?: { question: string; answer: string }[];
    note?: string;
    summary?: string;
    data?: Record<string, unknown>;
    manual?: boolean;
  };
  auth_check: { email_password?: boolean; methods?: string[]; notes?: string };
  target_url: string;
  goal: string;
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
  permanent: boolean;
  /** Signed up by hand using the manual sign-up kit. */
  manual?: boolean;
}

export interface RevealedCredentials {
  permanent?: boolean;
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

export interface LiveFrame {
  image: string; // base64 JPEG
  width: number;
  height: number;
  url: string;
}

export interface LiveView {
  state: string;
  /** True while the job is paused and the browser is waiting for the user. */
  interactive: boolean;
  seq?: number;
  /** Null when nothing changed since `since`, or no browser frame exists yet. */
  frame: LiveFrame | null;
}

export type LiveInput =
  | { type: "click"; x: number; y: number }
  | { type: "type"; text: string; submit?: boolean }
  | { type: "key"; key: "Enter" | "Tab" | "Backspace" | "Delete" | "Escape" | "Space" | "ArrowUp" | "ArrowDown" | "ArrowLeft" | "ArrowRight" }
  | { type: "scroll"; dy: number };

export async function getLiveView(id: string, since = 0) {
  return request<LiveView>(`/api/registration-jobs/${id}/live/?since=${since}`);
}

export async function sendLiveInput(id: string, event: LiveInput) {
  return request<void>(`/api/registration-jobs/${id}/live/input/`, {
    method: "POST",
    body: JSON.stringify(event),
  });
}

export async function answerQuestion(jobId: string, questionId: string, body: { answer?: string; skip?: boolean; remember?: boolean }) {
  return request<void>(`/api/registration-jobs/${jobId}/questions/${questionId}/answer/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
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


// --- Settings: preferences, saved details, email, API keys -----------------------

export type AccountMode = "temporary" | "permanent";

export interface StandardField {
  key: string;
  label: string;
  type: string;
}

export interface ProfileEntry {
  key: string;
  label: string;
  value: string;
  source: "settings" | "answer";
}

export interface ProfileData {
  account_mode: AccountMode;
  standard_fields: StandardField[];
  entries: ProfileEntry[];
}

export interface EmailConnection {
  connected: boolean;
  kind: "imap" | "gmail" | null;
  address: string | null;
  imap_host: string | null;
  last_checked_at: string | null;
  last_error: string;
  gmail_oauth_available: boolean;
  ok?: boolean;
}

export type AccountProvider = "google" | "microsoft";

export interface ConnectedAccount {
  provider: AccountProvider;
  email: string;
  has_password: boolean;
  signed_in: boolean;
  session_saved_at: string | null;
  last_used_at: string | null;
  last_error: string;
}

export interface ApiKeySummary {
  id: string;
  name: string;
  prefix: string;
  /** "oauth" keys come from connecting a client (e.g. claude.ai) through the sign-in flow. */
  kind?: "manual" | "oauth";
  created_at: string;
  last_used_at: string | null;
}

export async function getProfile() {
  return request<ProfileData>("/api/profile/");
}

export async function setAccountMode(account_mode: AccountMode) {
  return request<{ account_mode: AccountMode }>("/api/preferences/", {
    method: "PATCH",
    body: JSON.stringify({ account_mode }),
  });
}

export async function saveProfileEntry(key: string, value: string, label?: string) {
  return request<ProfileEntry | undefined>(`/api/profile/entries/${encodeURIComponent(key)}/`, {
    method: "PUT",
    body: JSON.stringify({ value, label }),
  });
}

export async function deleteProfileEntry(key: string) {
  return request<void>(`/api/profile/entries/${encodeURIComponent(key)}/`, { method: "DELETE" });
}

export async function listConnectedAccounts() {
  return request<ConnectedAccount[]>("/api/connected-accounts/");
}

export async function saveConnectedAccount(provider: AccountProvider, email: string, password: string) {
  return request<ConnectedAccount>("/api/connected-accounts/", {
    method: "PUT",
    body: JSON.stringify({ provider, email, password }),
  });
}

export async function removeConnectedAccount(provider: AccountProvider) {
  return request<void>(`/api/connected-accounts/${provider}/`, { method: "DELETE" });
}

export async function startAccountSignIn(provider: AccountProvider) {
  return request<RegistrationJob>(`/api/connected-accounts/${provider}/signin/`, { method: "POST" });
}

export async function getEmailConnection() {
  return request<EmailConnection>("/api/email-connection/");
}

export async function connectImap(address: string, password: string, host: string) {
  return request<EmailConnection>("/api/email-connection/", {
    method: "PUT",
    body: JSON.stringify({ address, password, host }),
  });
}

export async function testEmailConnection() {
  return request<EmailConnection>("/api/email-connection/test/", { method: "POST" });
}

export async function disconnectEmail() {
  return request<void>("/api/email-connection/", { method: "DELETE" });
}

export async function getGmailAuthorizeUrl() {
  return request<{ url: string }>("/api/email-connection/gmail/authorize/");
}

export async function listApiKeys() {
  return request<ApiKeySummary[]>("/api/api-keys/");
}

export async function createApiKey(name: string) {
  return request<ApiKeySummary & { key: string }>("/api/api-keys/", { method: "POST", body: JSON.stringify({ name }) });
}

export async function revokeApiKey(id: string) {
  return request<void>(`/api/api-keys/${id}/`, { method: "DELETE" });
}

export { API_URL };

// --- OAuth approval (MCP clients such as claude.ai) ---------------------------------

export type OAuthParams = Record<string, string>;

export async function getOAuthInfo(params: OAuthParams) {
  return request<{ client_name: string; redirect_host: string | null }>(
    `/api/oauth/authorize-info/?${new URLSearchParams(params).toString()}`,
  );
}

export async function approveOAuth(params: OAuthParams, approve: boolean) {
  return request<{ redirect_url: string }>("/api/oauth/approve/", {
    method: "POST",
    body: JSON.stringify({ ...params, approve }),
  });
}


// --- Manual sign-up kit -------------------------------------------------------

export interface ManualKitField {
  label: string;
  type: string;
  required: boolean;
  source: string;
  options: string[];
  group: string;
  value: string;
  secret: boolean;
}

export interface ManualKit {
  url: string;
  title: string;
  domain: string;
  fields: ManualKitField[];
  email: string;
  username: string;
  password: string;
}

export async function getManualKit(jobId: string) {
  return request<ManualKit>(`/api/registration-jobs/${jobId}/manual-kit/`, { method: "POST" });
}

export async function completeManualSignup(jobId: string, body: { username?: string; password?: string; note?: string }) {
  return request<{ account_id: string; state: string }>(`/api/registration-jobs/${jobId}/manual-complete/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// --- Vault mailbox ---------------------------------------------------------------

export interface MailboxInfo {
  address: string;
  status: "active" | "closed";
  own_inbox: boolean;
  expires_at: string | null;
  last_checked_at: string | null;
}

export interface MailMessageSummary {
  id: string;
  sender: string;
  subject: string;
  snippet: string;
  received_at: string | null;
  read: boolean;
  has_link: boolean;
  has_code: boolean;
}

export interface MailMessage extends MailMessageSummary {
  text: string;
  links: string[];
  verification_link: string;
  code: string;
}

export interface Mailbox {
  mailbox: MailboxInfo;
  messages: MailMessageSummary[];
  unread: number;
  refresh_error: string;
}

export async function getMailbox(accountId: string, refresh = false) {
  return request<Mailbox>(`/api/accounts/${accountId}/mailbox/${refresh ? "?refresh=1" : ""}`);
}

export async function getMailMessage(accountId: string, messageId: string) {
  return request<MailMessage>(`/api/accounts/${accountId}/mailbox/messages/${messageId}/`);
}

export async function askMailbox(accountId: string, question: string) {
  return request<{ answer: string; checked: number; new: number }>(`/api/accounts/${accountId}/mailbox/ask/`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

// --- Chat -----------------------------------------------------------------------------------

export interface ChatAction {
  name: string;
  label: string;
  ok: boolean;
}

export interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  kind: "text" | "task_started" | "task_result";
  content: string;
  /** What the assistant did to produce this reply (checked the mailbox, started a task, ...). */
  actions: ChatAction[];
  /** For task messages: the task whose progress is shown inline. */
  job_id: string | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  /** Set when the conversation is about a vault account. */
  account_id: string | null;
  account_status: "active" | "expired" | "deleted" | null;
  can_chat: boolean;
  messages: ChatMessageItem[];
  active_job: { id: string; state: JobState } | null;
}

export interface ChatSummary {
  id: string;
  title: string;
  account_id: string | null;
  email: string;
  status: "active" | "expired" | "deleted";
  message_count: number;
  working: boolean;
  last_message: { role: "user" | "assistant"; content: string; created_at: string } | null;
  last_activity: string;
}

export async function listChats() {
  return request<{ results: ChatSummary[] }>("/api/chats/");
}

export async function createChat() {
  return request<Conversation>("/api/chats/", { method: "POST", body: JSON.stringify({}) });
}

export async function getChat(id: string) {
  return request<Conversation>(`/api/chats/${id}/`);
}

export async function sendChat(id: string, message: string) {
  return request<Conversation>(`/api/chats/${id}/`, { method: "POST", body: JSON.stringify({ message }) });
}

export async function deleteChat(id: string) {
  return request<void>(`/api/chats/${id}/`, { method: "DELETE" });
}

/** The conversation that belongs to one vault account. */
export async function getAccountChat(accountId: string) {
  return request<Conversation>(`/api/accounts/${accountId}/chat/`);
}

export async function sendAccountChat(accountId: string, message: string) {
  return request<Conversation>(`/api/accounts/${accountId}/chat/`, { method: "POST", body: JSON.stringify({ message }) });
}

export async function clearAccountChat(accountId: string) {
  return request<void>(`/api/accounts/${accountId}/chat/`, { method: "DELETE" });
}

// --- Notifications -----------------------------------------------------------------

export type NotificationKind =
  | "job_started" | "job_completed" | "job_failed" | "job_cancelled" | "job_needs_you" | "job_question"
  | "mail_received" | "account_expiring" | "account_expired" | "signin_issue" | "client_connected"
  | "manual_saved" | "playbook_used";

export interface AppNotification {
  id: number;
  kind: NotificationKind;
  title: string;
  body: string;
  link: string;
  data: Record<string, unknown>;
  read: boolean;
  created_at: string;
}

export async function listNotifications() {
  return request<{ unread: number; results: AppNotification[] }>("/api/notifications/");
}

export async function markNotificationsRead(ids?: number[]) {
  return request<{ unread: number }>("/api/notifications/read/", {
    method: "POST",
    body: JSON.stringify(ids ? { ids } : {}),
  });
}

export async function deleteNotification(id: number) {
  return request<void>(`/api/notifications/${id}/`, { method: "DELETE" });
}

export async function clearNotifications() {
  return request<void>("/api/notifications/", { method: "DELETE" });
}

/**
 * Opens the notification stream. EventSource can't send an Authorization header, so this reads
 * the response body directly. Returns the Response (caller reads `body`), refreshing the token once on 401.
 */
export async function openNotificationStream(lastId: number | null, signal: AbortSignal): Promise<Response> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const token = getAccessToken();
    const headers: Record<string, string> = { Accept: "text/event-stream" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (lastId !== null) headers["Last-Event-ID"] = String(lastId);
    const res = await fetch(`${API_URL}/api/notifications/stream/`, { headers, signal, cache: "no-store" });
    if (res.status === 401 && attempt === 0 && (await tryRefresh())) continue;
    return res;
  }
  throw new ApiError(401, {});
}

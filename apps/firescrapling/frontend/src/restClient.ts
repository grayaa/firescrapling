/**
 * REST client for FireScrapling FastAPI (same-origin via nginx in Docker, or VITE_API_BASE_URL in dev).
 */
const STORAGE_KEY = "firescrapling_api_key";
const SESSION_KEY = "firescrapling_session";
const ADMIN_KEY = "firescrapling_admin_token";

/** Dispatched when a session-authenticated call gets 401 (e.g. DB reset). */
export const SESSION_EXPIRED_EVENT = "firescrapling:session-expired";

export function getApiKey(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setApiKey(key: string): void {
  try {
    if (key.trim()) {
      localStorage.setItem(STORAGE_KEY, key.trim());
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    /* ignore */
  }
}

/**
 * Session tokens (from /v1/auth/login) and API keys are different credentials:
 * sessions authorize account routes like /v1/keys, API keys authorize
 * /v1/scrape|crawl|map. They are stored — and sent — separately.
 * Admin tokens (ADMIN_SECRET) authorize /v1/admin/* only.
 */
export function getSessionToken(): string {
  try {
    return localStorage.getItem(SESSION_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setSessionToken(token: string): void {
  try {
    if (token.trim()) {
      localStorage.setItem(SESSION_KEY, token.trim());
    } else {
      localStorage.removeItem(SESSION_KEY);
    }
  } catch {
    /* ignore */
  }
}

export function getAdminToken(): string {
  try {
    return localStorage.getItem(ADMIN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setAdminToken(token: string): void {
  try {
    if (token.trim()) {
      localStorage.setItem(ADMIN_KEY, token.trim());
    } else {
      localStorage.removeItem(ADMIN_KEY);
    }
  } catch {
    /* ignore */
  }
}

export function apiBaseUrl(): string {
  const v = import.meta.env.VITE_API_BASE_URL;
  return typeof v === "string" && v.trim() ? v.replace(/\/$/, "") : "";
}

/** Absolute API root for docs / copy-paste (`…/v1`). Prefers VITE_API_BASE_URL, else this origin. */
export function publicApiRoot(): string {
  const base = apiBaseUrl();
  if (base) return `${base.replace(/\/$/, "")}/v1`;
  if (typeof window !== "undefined" && window.location?.origin) {
    return `${window.location.origin}/v1`;
  }
  return "http://localhost:8000/v1";
}

function joinUrl(path: string): string {
  const base = apiBaseUrl();
  if (!path.startsWith("/")) path = `/${path}`;
  return base ? `${base}${path}` : path;
}

export type ApiErrorBody = {
  error?: { code?: string; message?: unknown; request_id?: string };
};

export class RestApiError extends Error {
  status: number;
  code: string;
  requestId?: string;
  detail?: unknown;

  constructor(status: number, message: string, code: string, requestId?: string, detail?: unknown) {
    super(message);
    this.name = "RestApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.detail = detail;
  }
}

function parseErrorMessage(data: unknown): string {
  if (data && typeof data === "object" && "error" in data) {
    const e = (data as ApiErrorBody).error;
    if (e && typeof e.message === "string") return e.message;
    if (e && Array.isArray(e.message)) return JSON.stringify(e.message);
  }
  return typeof data === "string" ? data : "Request failed";
}

export type AuthMode = "key" | "session" | "admin" | "none";

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit & { jsonBody?: unknown; auth?: AuthMode } = {},
): Promise<T> {
  const { jsonBody, headers: hdrs, auth = "key", ...rest } = init;
  const headers = new Headers(hdrs);
  if (jsonBody !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  const credential =
    auth === "session"
      ? getSessionToken()
      : auth === "admin"
        ? getAdminToken()
        : auth === "key"
          ? getApiKey()
          : "";
  if (credential) {
    headers.set("Authorization", `Bearer ${credential}`);
  }

  const res = await fetch(joinUrl(path), {
    ...rest,
    headers,
    body: jsonBody !== undefined ? JSON.stringify(jsonBody) : rest.body,
  });

  const ct = res.headers.get("content-type") || "";
  const text = await res.text();
  let data: unknown = text;
  if (ct.includes("application/json") && text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const msg = parseErrorMessage(data);
    const errObj = data && typeof data === "object" && "error" in data ? (data as ApiErrorBody).error : undefined;
    const code = (errObj?.code as string) || `http_${res.status}`;
    const rid = errObj?.request_id as string | undefined;
    // Stale session after DB wipe / Postgres switch — drop token so the UI can re-auth.
    // Only clear if this request's token is still the active one (ignore late 401s from
    // older in-flight calls after a fresh login).
    if (res.status === 401 && auth === "session" && credential) {
      if (getSessionToken() === credential) {
        setSessionToken("");
        try {
          window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
        } catch {
          /* ignore */
        }
      }
    }
    throw new RestApiError(res.status, msg, code, rid, data);
  }

  return data as T;
}

export async function getHealthReady(): Promise<{ status: string; database?: string }> {
  return apiFetch("/health/ready", { auth: "none" });
}

// --- Accounts & sessions ---

export type ApiUser = {
  id: string;
  email: string;
  full_name?: string | null;
};

type LoginResponse = { success: boolean; user: ApiUser; session_token: string };

export async function loginUser(email: string, password: string): Promise<ApiUser> {
  const res = await apiFetch<LoginResponse>("/v1/auth/login", {
    method: "POST",
    auth: "none",
    jsonBody: { email, password },
  });
  setSessionToken(res.session_token);
  return res.user;
}

/** Register does not issue a session, so chain a login to land signed in. */
export async function registerUser(
  email: string,
  password: string,
  fullName?: string,
): Promise<ApiUser> {
  await apiFetch<{ success: boolean; user: ApiUser }>("/v1/auth/register", {
    method: "POST",
    auth: "none",
    jsonBody: { email, password, full_name: fullName || null },
  });
  return loginUser(email, password);
}

export async function logoutUser(): Promise<void> {
  try {
    await apiFetch("/v1/auth/logout", { method: "POST", auth: "session" });
  } catch {
    // Server-side revocation is best-effort; the local token is dropped regardless.
  }
  setSessionToken("");
}

// --- API keys (session-authenticated) ---

export type ApiKeySummary = {
  id: string;
  name: string | null;
  key_preview: string;
  created_at: string | null;
  last_used: string | null;
};

export async function listApiKeys(): Promise<ApiKeySummary[]> {
  const res = await apiFetch<{ keys: ApiKeySummary[] }>("/v1/keys", { auth: "session" });
  return res.keys ?? [];
}

/** The full key value is returned exactly once, here. */
export async function createApiKey(name: string): Promise<{ id: string; name: string; value: string }> {
  const res = await apiFetch<{ key: { id: string; name: string; value: string } }>("/v1/keys", {
    method: "POST",
    auth: "session",
    jsonBody: { name },
  });
  return res.key;
}

export async function deleteApiKey(keyId: string): Promise<void> {
  await apiFetch(`/v1/keys/${encodeURIComponent(keyId)}`, { method: "DELETE", auth: "session" });
}

// --- Usage ---

export type UsageSummary = {
  window_days: number;
  total_requests: number;
  success_rate: number;
  failed_requests: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  pages_crawled: number;
  active_keys: number;
  daily: { date: string; success: number; failed: number }[];
  by_endpoint: { endpoint: string; requests: number; success_rate: number }[];
  recent_jobs: {
    id: string;
    type: string;
    url: string;
    status: string;
    pages: number;
    created_at: string | null;
  }[];
};

export async function getUsageSummary(days = 30): Promise<UsageSummary> {
  return apiFetch<UsageSummary>(`/v1/usage/summary?days=${days}`, { auth: "session" });
}

export type FetchSavingsSummary = {
  estimated: boolean;
  baseline_tier: string;
  window_days: number;
  events: number;
  baseline_cost: number;
  actual_cost: number;
  saved_cost: number;
  savings_pct: number;
  by_domain: {
    domain: string;
    events: number;
    baseline_cost: number;
    actual_cost: number;
    saved_cost: number;
    savings_pct: number;
  }[];
};

export async function getFetchSavings(days = 30): Promise<FetchSavingsSummary> {
  return apiFetch<FetchSavingsSummary>(`/v1/usage/fetch-savings?days=${days}`, { auth: "session" });
}

// --- Platform capabilities (public) ---

export type PlatformCapabilities = {
  scrapfly: boolean;
  scrapedo?: boolean;
  fetch_provider: string;
  fetch_escalate?: boolean;
  js_render: boolean;
  js_render_default: boolean;
  anti_bot: boolean;
  proxy_rotation: boolean;
  queue: boolean;
  webhooks: boolean;
  markdown: boolean;
  hosted?: boolean;
  byok?: boolean;
  managed_fetch?: boolean;
  playground?: boolean;
  registration_open?: boolean;
  billing?: boolean;
  extract_media?: boolean;
  encryption_key_present?: boolean;
  admin_configured?: boolean;
  rate_limit_per_minute?: number;
  domain_profile_ttl_seconds?: number;
  database_backend?: string;
  worker_concurrency?: number;
  version?: string;
  commit?: string;
  credential_source?: string;
  credential_provider?: string;
  platform_env?: { provider: string; env_var: string } | null;
  crawl_global_concurrency?: number;
  crawl_per_host_concurrency?: number;
};

export async function getCapabilities(): Promise<PlatformCapabilities> {
  return apiFetch<PlatformCapabilities>("/v1/capabilities", { auth: "none" });
}

// --- BYOK provider credentials (session) ---

export type ProviderCredential = {
  id: string;
  provider: "scrapedo" | "scrapfly" | string;
  label: string | null;
  key_hint: string;
  proxy_pool: string | null;
  residential_pool: string | null;
  country: string | null;
  status: string;
  created_at: string | null;
  last_used_at: string | null;
};

export async function listProviders(): Promise<ProviderCredential[]> {
  const res = await apiFetch<{ providers: ProviderCredential[] }>("/v1/providers", { auth: "session" });
  return res.providers ?? [];
}

export async function createProvider(body: {
  provider: "scrapedo" | "scrapfly";
  api_key: string;
  label?: string;
  country?: string;
}): Promise<ProviderCredential> {
  const res = await apiFetch<{ provider: ProviderCredential }>("/v1/providers", {
    method: "POST",
    auth: "session",
    jsonBody: body,
  });
  return res.provider;
}

export async function verifyProvider(id: string): Promise<{ success: boolean; status: string; message?: string }> {
  return apiFetch(`/v1/providers/${encodeURIComponent(id)}/verify`, { method: "POST", auth: "session" });
}

export async function deleteProvider(id: string): Promise<void> {
  await apiFetch(`/v1/providers/${encodeURIComponent(id)}`, { method: "DELETE", auth: "session" });
}

/** Public homepage playground — no API key; server enforces IP rate limits and URL safety. */
export async function playgroundFetch<T = unknown>(
  path: "/v1/playground/scrape" | "/v1/playground/map" | "/v1/playground/crawl",
  jsonBody: Record<string, unknown>,
): Promise<T> {
  const res = await fetch(joinUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(jsonBody),
  });
  const ct = res.headers.get("content-type") || "";
  const text = await res.text();
  let data: unknown = text;
  if (ct.includes("application/json") && text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const msg = parseErrorMessage(data);
    const errObj = data && typeof data === "object" && "error" in data ? (data as ApiErrorBody).error : undefined;
    const code = (errObj?.code as string) || `http_${res.status}`;
    const rid = errObj?.request_id as string | undefined;
    throw new RestApiError(res.status, msg, code, rid, data);
  }
  return data as T;
}

// --- Admin (ADMIN_SECRET bearer token) ---

export type AdminStats = {
  total_users: number;
  total_requests_30d: number;
  success_rate: number;
  active_jobs: number;
  failed_jobs: number;
  avg_latency_ms: number;
  jobs_by_status?: Record<string, number>;
};

export type AdminUser = {
  id: string;
  email: string;
  full_name: string | null;
  created_at: string | null;
  key_count: number;
  job_count: number;
  request_count_30d: number;
};

export type AdminJob = {
  id: string;
  user_email: string | null;
  type: string;
  status: string;
  url: string;
  created_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  progress: number;
};

export type AdminHealth = {
  db: string;
  users: number;
  active_sessions: number;
};

export async function getAdminHealth(): Promise<AdminHealth> {
  return apiFetch<AdminHealth>("/v1/admin/health", { auth: "admin" });
}

export async function getAdminStats(): Promise<AdminStats> {
  return apiFetch<AdminStats>("/v1/admin/stats", { auth: "admin" });
}

export async function listAdminUsers(opts?: {
  limit?: number;
  offset?: number;
  search?: string;
}): Promise<{ users: AdminUser[]; total: number; limit: number; offset: number }> {
  const params = new URLSearchParams();
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  if (opts?.search) params.set("search", opts.search);
  const qs = params.toString();
  return apiFetch(`/v1/admin/users${qs ? `?${qs}` : ""}`, { auth: "admin" });
}

export async function deleteAdminUser(userId: string): Promise<void> {
  await apiFetch(`/v1/admin/users/${encodeURIComponent(userId)}`, {
    method: "DELETE",
    auth: "admin",
  });
}

export async function listAdminJobs(opts?: {
  limit?: number;
  offset?: number;
  status?: string;
  type?: string;
}): Promise<{ jobs: AdminJob[]; total: number; limit: number; offset: number }> {
  const params = new URLSearchParams();
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  if (opts?.status) params.set("status", opts.status);
  if (opts?.type) params.set("type", opts.type);
  const qs = params.toString();
  return apiFetch(`/v1/admin/jobs${qs ? `?${qs}` : ""}`, { auth: "admin" });
}

export async function deleteAdminJob(jobId: string): Promise<void> {
  await apiFetch(`/v1/admin/jobs/${encodeURIComponent(jobId)}`, {
    method: "DELETE",
    auth: "admin",
  });
}

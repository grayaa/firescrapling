/**
 * REST client for FireScrapling FastAPI (same-origin via nginx in Docker, or VITE_API_BASE_URL in dev).
 */
const STORAGE_KEY = "firescrapling_api_key";

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

export function apiBaseUrl(): string {
  const v = import.meta.env.VITE_API_BASE_URL;
  return typeof v === "string" && v.trim() ? v.replace(/\/$/, "") : "";
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

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit & { jsonBody?: unknown } = {},
): Promise<T> {
  const { jsonBody, headers: hdrs, ...rest } = init;
  const headers = new Headers(hdrs);
  if (jsonBody !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  const key = getApiKey();
  if (key) {
    headers.set("Authorization", `Bearer ${key}`);
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
    throw new RestApiError(res.status, msg, code, rid, data);
  }

  return data as T;
}

export async function getHealthReady(): Promise<{ status: string; database?: string }> {
  return apiFetch("/health/ready");
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

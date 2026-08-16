/** Lightweight path ↔ view sync (no react-router). */

export const VIEWS = [
  "landing",
  "docs",
  "pricing",
  "overview",
  "playground",
  "api-keys",
  "providers",
  "savings",
  "settings",
  "admin",
  "webhooks",
  "usage",
  "login",
] as const;

export type AppView = (typeof VIEWS)[number];

const VIEW_TO_PATH: Record<AppView, string> = {
  landing: "/",
  docs: "/docs",
  pricing: "/pricing",
  overview: "/overview",
  playground: "/playground",
  "api-keys": "/api-keys",
  providers: "/providers",
  savings: "/savings",
  settings: "/settings",
  admin: "/admin",
  webhooks: "/webhooks",
  usage: "/usage",
  login: "/login",
};

const PATH_TO_VIEW: Record<string, AppView> = Object.fromEntries(
  Object.entries(VIEW_TO_PATH).map(([view, path]) => [path, view as AppView]),
) as Record<string, AppView>;

PATH_TO_VIEW["/features"] = "landing";

export function pathForView(view: string): string {
  return VIEW_TO_PATH[view as AppView] ?? "/";
}

export function viewFromPath(pathname: string): AppView {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  return PATH_TO_VIEW[normalized] ?? PATH_TO_VIEW[pathname] ?? "landing";
}

export function readViewFromLocation(): AppView {
  return viewFromPath(window.location.pathname);
}

/** Push or replace the browser URL for a view. */
/** Push or replace the browser URL for a view.
 * Pass `search` to set/clear the query. When omitted: keep the current query if the
 * path is unchanged (so `/login?register=1` survives the initial align), otherwise none.
 */
export function syncUrl(view: string, mode: "push" | "replace" = "push", search?: string): void {
  const path = pathForView(view);
  const full =
    search !== undefined
      ? path + search
      : path === window.location.pathname
        ? path + window.location.search
        : path;
  if (`${window.location.pathname}${window.location.search}` === full) return;
  if (mode === "replace") {
    window.history.replaceState({ view }, "", full);
  } else {
    window.history.pushState({ view }, "", full);
  }
}

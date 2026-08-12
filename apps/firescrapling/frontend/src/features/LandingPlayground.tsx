import { useCallback, useState } from "react";
import { playgroundFetch, RestApiError } from "../restClient";

type Mode = "scrape" | "map" | "crawl";

const DEFAULT_URL = "https://example.com";

function WireframeIllustration() {
  return (
    <div className="flex h-full min-h-[200px] flex-col gap-3 rounded-xl border border-white/10 bg-black/40 p-4 text-left text-xs text-white/50">
      <div className="flex gap-2">
        <div className="h-6 w-16 rounded bg-white/10" title="Logo" />
        <div className="flex flex-1 gap-1">
          <div className="h-6 flex-1 rounded bg-white/5" />
          <div className="h-6 flex-1 rounded bg-white/5" />
          <div className="h-6 flex-1 rounded bg-white/5" />
        </div>
      </div>
      <p className="text-[10px] uppercase tracking-wider text-white/30">Navigation</p>
      <div className="h-8 w-3/4 rounded bg-white/10" title="H1 Title" />
      <p className="text-[10px] uppercase tracking-wider text-white/30">Description</p>
      <div className="space-y-2">
        <div className="h-2 w-full rounded bg-white/5" />
        <div className="h-2 w-5/6 rounded bg-white/5" />
        <div className="h-2 w-4/6 rounded bg-white/5" />
      </div>
    </div>
  );
}

export function LandingPlayground() {
  const [url, setUrl] = useState(DEFAULT_URL);
  const [mode, setMode] = useState<Mode>("scrape");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      if (mode === "scrape") {
        const data = await playgroundFetch("/v1/playground/scrape", { url: url.trim() });
        setResult(data);
      } else if (mode === "map") {
        const data = await playgroundFetch("/v1/playground/map", { url: url.trim() });
        setResult(data);
      } else {
        const data = await playgroundFetch("/v1/playground/crawl", { url: url.trim() });
        setResult(data);
      }
    } catch (e) {
      if (e instanceof RestApiError) {
        setError(e.message || `Error ${e.status}`);
      } else {
        setError(e instanceof Error ? e.message : "Request failed");
      }
    } finally {
      setLoading(false);
    }
  }, [mode, url]);

  const jsonStr =
    result !== null
      ? JSON.stringify(result, null, 2)
      : error
        ? JSON.stringify({ error: error }, null, 2)
        : "// Run a request to see JSON output";

  return (
    <div className="mx-auto mt-10 w-full max-w-4xl">
      <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] shadow-xl backdrop-blur-sm">
        <div className="flex flex-col gap-0 sm:flex-row sm:items-stretch">
          <div className="flex flex-1 items-center gap-2 border-b border-white/10 px-4 py-3 sm:border-b-0 sm:border-r">
            <span className="text-white/40" aria-hidden>
              🌐
            </span>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com"
              className="min-w-0 flex-1 bg-transparent text-sm text-white placeholder:text-white/30 outline-none"
              spellCheck={false}
            />
          </div>
          <div className="flex flex-wrap items-center gap-1 px-2 py-2 sm:py-0">
            {(["scrape", "map", "crawl"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`rounded-lg px-3 py-2 text-xs font-medium capitalize transition ${
                  mode === m ? "bg-orange-500 text-white" : "text-white/60 hover:bg-white/10 hover:text-white"
                }`}
              >
                {m}
              </button>
            ))}
            <button
              type="button"
              onClick={() => void run()}
              disabled={loading || !url.trim()}
              className="ml-auto flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-orange-500 text-white transition hover:bg-orange-400 disabled:opacity-40"
              title="Run"
            >
              {loading ? (
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              ) : (
                "→"
              )}
            </button>
          </div>
        </div>
        <p className="border-t border-white/10 px-4 py-2 text-[11px] text-white/35">
          No API key — rate-limited demo. Full API with auth in the dashboard.
        </p>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-black/30 p-1">
          <WireframeIllustration />
        </div>
        <div className="overflow-hidden rounded-xl border border-white/10 bg-[#0d1117]">
          <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400/90">.json</span>
            {error && <span className="text-[10px] text-red-400">Error</span>}
          </div>
          <pre className="max-h-[min(420px,50vh)] overflow-auto p-4 text-left font-mono text-[11px] leading-relaxed text-emerald-100/90 whitespace-pre-wrap break-words">
            {jsonStr}
          </pre>
        </div>
      </div>
    </div>
  );
}

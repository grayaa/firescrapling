import React from "react";
import {
  Globe,
  Terminal,
  Play,
  Loader2,
  Code2,
  Activity,
  Braces,
  Copy,
  CheckCircle2,
  AlertCircle,
  Clock,
  RefreshCw,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Separator } from "../components/ui/separator";
import { Badge } from "../components/ui/badge";
import { ScrollArea } from "../components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Checkbox } from "../components/ui/checkbox";
import { Textarea } from "../components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../components/ui/dialog";
import { cn } from "../lib/utils";
import { apiFetch, getApiKey, setApiKey, getHealthReady, RestApiError } from "../restClient";

type Mode = "scrape" | "map" | "crawl";

type JobSummary = {
  id: string;
  type: string;
  url: string;
  status: string;
  progress: number;
  created_at?: string;
  finished_at?: string;
  error_message?: string | null;
};

const FORMAT_OPTIONS: { id: string; label: string; api: string }[] = [
  { id: "markdown", label: "Markdown", api: "markdown" },
  { id: "html", label: "HTML", api: "html" },
  { id: "raw", label: "Raw HTML", api: "raw_content" },
  { id: "screenshot", label: "Screenshot", api: "screenshot" },
  { id: "links", label: "Links", api: "links" },
  { id: "images", label: "Images", api: "images" },
];

async function pollJob(jobId: string, maxMs = 180000): Promise<{ status: string; error_message?: string | null }> {
  const step = 800;
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    const j = await apiFetch<{
      status: string;
      progress?: number;
      error_message?: string | null;
    }>(`/v1/jobs/${jobId}`);
    if (j.status === "completed" || j.status === "failed") return j;
    await new Promise((r) => setTimeout(r, step));
  }
  throw new Error("Job did not finish in time");
}

export function SaaSPlayground() {
  const [apiKeyInput, setApiKeyInput] = React.useState(() => getApiKey());
  const [mode, setMode] = React.useState<Mode>("scrape");
  const [url, setUrl] = React.useState("https://example.com");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [resultJson, setResultJson] = React.useState<string | null>(null);
  const [activeTab, setActiveTab] = React.useState<"json" | "preview">("json");

  const [fmt, setFmt] = React.useState<Record<string, boolean>>({
    markdown: true,
    html: false,
    raw: false,
    screenshot: false,
    links: false,
    images: false,
  });
  const [schemaJson, setSchemaJson] = React.useState("");
  const [useSchema, setUseSchema] = React.useState(false);
  const [onlyMain, setOnlyMain] = React.useState(true);
  const [actionsJson, setActionsJson] = React.useState("[]");
  const [showInteract, setShowInteract] = React.useState(false);

  const [mapSearch, setMapSearch] = React.useState("");
  const [mapIgnoreSub, setMapIgnoreSub] = React.useState(false);

  const [crawlLimit, setCrawlLimit] = React.useState(20);
  const [crawlDepth, setCrawlDepth] = React.useState(2);
  const [crawlIgnoreSub, setCrawlIgnoreSub] = React.useState(false);

  const [jobs, setJobs] = React.useState<JobSummary[]>([]);
  const [jobsLoading, setJobsLoading] = React.useState(false);
  const [selectedJobId, setSelectedJobId] = React.useState<string | null>(null);

  const [readyOk, setReadyOk] = React.useState<boolean | null>(null);

  const refreshJobs = React.useCallback(async () => {
    if (!getApiKey().trim()) {
      setJobs([]);
      return;
    }
    setJobsLoading(true);
    try {
      const out = await apiFetch<{ jobs: JobSummary[] }>("/v1/jobs?limit=30");
      setJobs(out.jobs ?? []);
    } catch (e) {
      if (e instanceof RestApiError && e.status === 401) setJobs([]);
    } finally {
      setJobsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refreshJobs();
  }, [refreshJobs]);

  React.useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        await getHealthReady();
        if (!cancelled) setReadyOk(true);
      } catch {
        if (!cancelled) setReadyOk(false);
      }
    };
    void tick();
    const id = window.setInterval(tick, 60000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const saveKey = () => {
    setApiKey(apiKeyInput);
    void refreshJobs();
  };

  const buildFormats = (): string[] => {
    const list: string[] = [];
    for (const opt of FORMAT_OPTIONS) {
      if (fmt[opt.id]) list.push(opt.api);
    }
    if (list.length === 0) list.push("markdown");
    return list;
  };

  const runScrape = async () => {
    setLoading(true);
    setError(null);
    setResultJson(null);
    try {
      let schema: Record<string, unknown> | undefined;
      if (useSchema && schemaJson.trim()) {
        schema = JSON.parse(schemaJson) as Record<string, unknown>;
      }
      let actions: unknown[] | undefined;
      if (showInteract && actionsJson.trim()) {
        const parsed = JSON.parse(actionsJson) as unknown;
        if (!Array.isArray(parsed)) throw new Error("actions must be a JSON array");
        actions = parsed;
      }
      const body: Record<string, unknown> = {
        url: url.trim(),
        formats: buildFormats(),
        onlyMainContent: onlyMain,
      };
      if (schema) body.schema = schema;
      if (actions && actions.length) body.actions = actions;

      const res = await apiFetch<{ success?: boolean; data?: unknown }>("/v1/scrape", {
        method: "POST",
        jsonBody: body,
      });
      setResultJson(JSON.stringify(res, null, 2));
      setActiveTab("json");
      await refreshJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const runMap = async () => {
    setLoading(true);
    setError(null);
    setResultJson(null);
    try {
      const body = {
        url: url.trim(),
        search: mapSearch.trim() || undefined,
        ignoreSubdomains: mapIgnoreSub,
      };
      const res = await apiFetch("/v1/map", { method: "POST", jsonBody: body });
      setResultJson(JSON.stringify(res, null, 2));
      setActiveTab("json");
      await refreshJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const runCrawl = async () => {
    setLoading(true);
    setError(null);
    setResultJson(null);
    try {
      const res = await apiFetch<{ id?: string; success?: boolean }>("/v1/crawl", {
        method: "POST",
        jsonBody: {
          url: url.trim(),
          limit: crawlLimit,
          maxDepth: crawlDepth,
          ignoreSubdomains: crawlIgnoreSub,
        },
      });
      const jobId = res.id;
      if (!jobId) throw new Error("No job id returned");
      await pollJob(jobId);
      const detail = await apiFetch(`/v1/crawl/${jobId}`);
      setResultJson(JSON.stringify(detail, null, 2));
      setActiveTab("json");
      await refreshJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const loadJob = async (job: JobSummary) => {
    if (!getApiKey().trim()) {
      setError("Save an API key first");
      return;
    }
    setSelectedJobId(job.id);
    setLoading(true);
    setError(null);
    try {
      const detail = await apiFetch(`/v1/crawl/${job.id}`);
      setResultJson(JSON.stringify(detail, null, 2));
      setActiveTab("json");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const run = () => {
    if (!getApiKey().trim()) {
      setError("Enter and save your API key (Bearer) to call the API.");
      return;
    }
    if (!url.trim()) {
      setError("URL is required");
      return;
    }
    if (mode === "scrape") void runScrape();
    else if (mode === "map") void runMap();
    else void runCrawl();
  };

  const codeSnippet = React.useMemo(() => {
    const key = getApiKey() || "YOUR_API_KEY";
    const base = 'const API = ""; // same-origin, or set VITE_API_BASE_URL';
    if (mode === "map") {
      return `${base}
await fetch(\`\${API}/v1/map\`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${key}",
  },
  body: JSON.stringify({
    url: ${JSON.stringify(url.trim() || "https://example.com")},
    search: ${JSON.stringify(mapSearch.trim() || undefined)},
    ignoreSubdomains: ${mapIgnoreSub},
  }),
});`;
    }
    if (mode === "crawl") {
      return `${base}
await fetch(\`\${API}/v1/crawl\`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${key}",
  },
  body: JSON.stringify({
    url: ${JSON.stringify(url.trim() || "https://example.com")},
    limit: ${crawlLimit},
    maxDepth: ${crawlDepth},
    ignoreSubdomains: ${crawlIgnoreSub},
  }),
});`;
    }
    const formats = buildFormats();
    return `${base}
await fetch(\`\${API}/v1/scrape\`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${key}",
  },
  body: JSON.stringify({
    url: ${JSON.stringify(url.trim() || "https://example.com")},
    formats: ${JSON.stringify(formats)},
    onlyMainContent: ${onlyMain},
  }),
});`;
  }, [mode, url, mapSearch, mapIgnoreSub, crawlLimit, crawlDepth, crawlIgnoreSub, onlyMain, fmt]);

  const curlSnippet = React.useMemo(() => {
    const key = getApiKey() || "YOUR_API_KEY";
    if (mode === "map") {
      return `curl -sS -X POST "$API/v1/map" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${key}" \\
  -d '${JSON.stringify({
        url: url.trim() || "https://example.com",
        search: mapSearch.trim() || undefined,
        ignoreSubdomains: mapIgnoreSub,
      })}'`;
    }
    if (mode === "crawl") {
      return `curl -sS -X POST "$API/v1/crawl" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${key}" \\
  -d '${JSON.stringify({
        url: url.trim() || "https://example.com",
        limit: crawlLimit,
        maxDepth: crawlDepth,
        ignoreSubdomains: crawlIgnoreSub,
      })}'`;
    }
    return `curl -sS -X POST "$API/v1/scrape" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${key}" \\
  -d '${JSON.stringify({
      url: url.trim() || "https://example.com",
      formats: buildFormats(),
      onlyMainContent: onlyMain,
    })}'`;
  }, [mode, url, mapSearch, mapIgnoreSub, crawlLimit, crawlDepth, crawlIgnoreSub, onlyMain, fmt]);

  const parsedPreview = React.useMemo(() => {
    if (!resultJson) return null;
    try {
      const o = JSON.parse(resultJson) as {
        data?: { markdown?: string; title?: string };
        success?: boolean;
      };
      const md = o.data?.markdown;
      if (typeof md === "string") return md;
    } catch {
      return null;
    }
    return null;
  }, [resultJson]);

  return (
    <div className="p-6 md:p-8 space-y-8 animate-in fade-in duration-500 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-3xl font-heading font-black tracking-tight text-white uppercase">Playground</h2>
          <p className="text-muted-foreground text-sm uppercase tracking-widest font-bold">
            Scrape, map, and crawl via the live API (same-origin in Docker)
          </p>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest">
          <Activity
            className={cn("h-4 w-4", readyOk === true ? "text-emerald-500" : readyOk === false ? "text-amber-500" : "text-muted-foreground")}
          />
          {readyOk === true ? "API ready" : readyOk === false ? "API degraded" : "Checking…"}
        </div>
      </div>

      <Card className="bg-card/40 border-border/50">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-bold uppercase tracking-widest flex items-center gap-2">
            <Terminal className="h-4 w-4" /> API key
          </CardTitle>
          <CardDescription className="text-xs">
            Paste a key from your account (create one via{" "}
            <code className="text-primary">POST /v1/keys</code> with a session token, or your dashboard). Stored in
            localStorage.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col sm:flex-row gap-2">
          <Input
            type="password"
            autoComplete="off"
            placeholder="fs_..."
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            className="font-mono bg-black/40 border-white/10"
          />
          <Button type="button" onClick={saveKey} className="shrink-0">
            Save key
          </Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 space-y-6">
          <Tabs value={mode} onValueChange={(v) => setMode(v as Mode)}>
            <TabsList className="grid w-full grid-cols-3 h-10">
              <TabsTrigger value="scrape" className="text-[10px] uppercase font-bold">
                Scrape
              </TabsTrigger>
              <TabsTrigger value="map" className="text-[10px] uppercase font-bold">
                Map
              </TabsTrigger>
              <TabsTrigger value="crawl" className="text-[10px] uppercase font-bold">
                Crawl
              </TabsTrigger>
            </TabsList>

            <TabsContent value="scrape" className="mt-4 space-y-4">
              <div className="space-y-2">
                <Label className="text-[10px] uppercase font-black tracking-widest text-muted-foreground">URL</Label>
                <Input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  className="font-mono bg-black/40 border-white/10 h-11 text-sm"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] uppercase font-black tracking-widest">Formats</Label>
                <div className="grid grid-cols-1 gap-2">
                  {FORMAT_OPTIONS.map((opt) => (
                    <label key={opt.id} className="flex items-center gap-2 text-xs cursor-pointer">
                      <Checkbox
                        checked={!!fmt[opt.id]}
                        onCheckedChange={(c) => setFmt((f) => ({ ...f, [opt.id]: !!c }))}
                      />
                      {opt.label}
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex items-center justify-between gap-2">
                <Label className="text-xs">Main content only</Label>
                <Switch checked={onlyMain} onCheckedChange={setOnlyMain} />
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-xs cursor-pointer">
                  <Checkbox checked={useSchema} onCheckedChange={(c) => setUseSchema(!!c)} />
                  Structured JSON (schema + OpenRouter)
                </label>
                {useSchema && (
                  <Textarea
                    value={schemaJson}
                    onChange={(e) => setSchemaJson(e.target.value)}
                    placeholder='{"type":"object","properties":{...}}'
                    className="font-mono text-xs min-h-[100px] bg-black/40"
                  />
                )}
              </div>
              <div className="space-y-2">
                <button
                  type="button"
                  className="text-xs font-bold text-primary uppercase tracking-widest"
                  onClick={() => setShowInteract((s) => !s)}
                >
                  {showInteract ? "Hide" : "Interact with page"} (actions JSON)
                </button>
                {showInteract && (
                  <Textarea
                    value={actionsJson}
                    onChange={(e) => setActionsJson(e.target.value)}
                    placeholder='[{"type":"wait","milliseconds":500}]'
                    className="font-mono text-xs min-h-[80px] bg-black/40"
                  />
                )}
              </div>
            </TabsContent>

            <TabsContent value="map" className="mt-4 space-y-4">
              <div className="space-y-2">
                <Label className="text-[10px] uppercase font-black tracking-widest">URL</Label>
                <Input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  className="font-mono bg-black/40 border-white/10 h-11 text-sm"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-[10px] uppercase">Filter (search substring)</Label>
                <Input value={mapSearch} onChange={(e) => setMapSearch(e.target.value)} className="bg-black/40" />
              </div>
              <div className="flex items-center justify-between gap-2">
                <Label className="text-xs">Ignore subdomains</Label>
                <Switch checked={mapIgnoreSub} onCheckedChange={setMapIgnoreSub} />
              </div>
            </TabsContent>

            <TabsContent value="crawl" className="mt-4 space-y-4">
              <div className="space-y-2">
                <Label className="text-[10px] uppercase font-black tracking-widest">URL</Label>
                <Input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  className="font-mono bg-black/40 border-white/10 h-11 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="text-[10px] uppercase">Limit</Label>
                  <Input
                    type="number"
                    min={1}
                    max={500}
                    value={crawlLimit}
                    onChange={(e) => setCrawlLimit(Number(e.target.value))}
                    className="bg-black/40"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[10px] uppercase">Max depth</Label>
                  <Input
                    type="number"
                    min={0}
                    max={10}
                    value={crawlDepth}
                    onChange={(e) => setCrawlDepth(Number(e.target.value))}
                    className="bg-black/40"
                  />
                </div>
              </div>
              <div className="flex items-center justify-between gap-2">
                <Label className="text-xs">Ignore subdomains</Label>
                <Switch checked={crawlIgnoreSub} onCheckedChange={setCrawlIgnoreSub} />
              </div>
            </TabsContent>
          </Tabs>

          <Separator className="bg-border/20" />

          <div className="flex flex-wrap gap-2">
            <Button
              onClick={run}
              disabled={loading}
              className="flex-1 min-w-[140px] bg-primary hover:bg-primary/90 font-bold uppercase tracking-widest"
            >
              {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2 fill-current" />}
              Run
            </Button>
            <Dialog>
              <DialogTrigger asChild>
                <Button type="button" variant="outline" className="font-bold uppercase text-[10px] tracking-widest">
                  <Code2 className="h-3.5 w-3.5 mr-1" /> Get code
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto bg-zinc-950 border-white/10">
                <DialogHeader>
                  <DialogTitle className="font-heading">Example requests</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 text-xs font-mono">
                  <div>
                    <p className="text-muted-foreground mb-1 uppercase tracking-widest text-[10px]">curl (set API base URL)</p>
                    <pre className="p-3 rounded-lg bg-black/60 border border-white/5 whitespace-pre-wrap break-all">{curlSnippet}</pre>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="mt-1 h-7 text-[10px]"
                      onClick={() => navigator.clipboard.writeText(curlSnippet)}
                    >
                      <Copy className="h-3 w-3 mr-1" /> Copy
                    </Button>
                  </div>
                  <div>
                    <p className="text-muted-foreground mb-1 uppercase tracking-widest text-[10px]">fetch</p>
                    <pre className="p-3 rounded-lg bg-black/60 border border-white/5 whitespace-pre-wrap break-all">{codeSnippet}</pre>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="mt-1 h-7 text-[10px]"
                      onClick={() => navigator.clipboard.writeText(codeSnippet)}
                    >
                      <Copy className="h-3 w-3 mr-1" /> Copy
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
            <Button type="button" variant="ghost" size="sm" onClick={() => void refreshJobs()} className="text-[10px] uppercase font-bold">
              <RefreshCw className={cn("h-3.5 w-3.5 mr-1", jobsLoading && "animate-spin")} />
              Jobs
            </Button>
          </div>

          {error && (
            <p className="text-sm text-destructive border border-destructive/30 rounded-md p-2 bg-destructive/10">{error}</p>
          )}
        </div>

        <div className="lg:col-span-2 space-y-6">
          <Card className="bg-card/40 border-border/50 min-h-[480px] flex flex-col">
            <Tabs
              value={activeTab}
              onValueChange={(v) => setActiveTab(v as "json" | "preview")}
              className="flex flex-col flex-1 min-h-0"
            >
              <CardHeader className="border-b border-border/50 p-0 shrink-0">
                <div className="flex items-center justify-between px-4 h-14">
                  <CardTitle className="text-sm font-bold uppercase tracking-widest">Result</CardTitle>
                  <TabsList className="h-9 bg-zinc-950 border border-border/50">
                    <TabsTrigger value="json" className="text-[10px] uppercase font-bold px-4">
                      <Braces className="h-3 w-3 mr-1" /> JSON
                    </TabsTrigger>
                    <TabsTrigger value="preview" className="text-[10px] uppercase font-bold px-4" disabled={!parsedPreview}>
                      Preview
                    </TabsTrigger>
                  </TabsList>
                </div>
              </CardHeader>
              <CardContent className="p-0 flex-1 min-h-0 flex flex-col">
                {!resultJson ? (
                  <div className="p-12 text-center text-muted-foreground text-sm">Run a request to see the response body.</div>
                ) : (
                  <>
                    <TabsContent value="json" className="mt-0 flex-1 min-h-0 data-[state=inactive]:hidden">
                      <ScrollArea className="h-[min(60vh,560px)]">
                        <pre className="text-xs font-mono text-zinc-300 p-4 whitespace-pre-wrap break-all">{resultJson}</pre>
                      </ScrollArea>
                    </TabsContent>
                    <TabsContent value="preview" className="mt-0 flex-1 min-h-0 data-[state=inactive]:hidden">
                      <ScrollArea className="h-[min(60vh,560px)] p-6">
                        <div className="prose prose-invert prose-sm max-w-none whitespace-pre-wrap font-mono text-orange-100/90">
                          {parsedPreview}
                        </div>
                      </ScrollArea>
                    </TabsContent>
                  </>
                )}
              </CardContent>
            </Tabs>
          </Card>

          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-bold uppercase tracking-widest flex items-center gap-2">
                <Clock className="h-4 w-4" /> Recent runs
              </h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {jobs.length === 0 && !jobsLoading && (
                <p className="text-xs text-muted-foreground col-span-full">No jobs yet. Save an API key and run Scrape, Map, or Crawl.</p>
              )}
              {jobs.map((j) => (
                <button
                  key={j.id}
                  type="button"
                  onClick={() => void loadJob(j)}
                  className={cn(
                    "text-left rounded-lg border p-3 transition-all hover:border-primary/40",
                    selectedJobId === j.id ? "border-primary/50 bg-primary/10" : "border-border/50 bg-card/30",
                  )}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <Badge variant="outline" className="text-[9px] uppercase">
                      {j.type}
                    </Badge>
                    {j.status === "completed" ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                    ) : j.status === "failed" ? (
                      <AlertCircle className="h-3.5 w-3.5 text-destructive shrink-0" />
                    ) : (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />
                    )}
                  </div>
                  <div className="text-[11px] font-mono truncate text-foreground">{j.url}</div>
                  <div className="text-[10px] text-muted-foreground mt-1">
                    {j.created_at ? new Date(j.created_at).toLocaleString() : ""} · {j.status}
                    {typeof j.progress === "number" ? ` · ${j.progress}%` : ""}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

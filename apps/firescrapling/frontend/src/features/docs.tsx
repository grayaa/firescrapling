import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { Terminal, Globe, Code2, Copy, Braces, Sparkles, Server, Zap } from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from '../components/ui/button';
import { publicApiRoot } from '../restClient';

export function ApiDocsView() {
  const [activeLang, setActiveLang] = React.useState<'python' | 'curl' | 'javascript'>('curl');
  // Resolves from VITE_API_BASE_URL, else this browser origin (nginx proxies /v1).
  const API = publicApiRoot();

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const endpoints = [
    {
      method: 'POST',
      path: '/v1/scrape',
      description: 'Scrape a single page and convert to Markdown or structured JSON.',
      params: [
        { name: 'url', type: 'string', required: true, description: 'The target URL to scrape.' },
        { name: 'formats', type: 'array', default: '["markdown"]', description: 'Output formats: markdown, html, raw_content, screenshot, links, images.' },
        { name: 'onlyMainContent', type: 'boolean', default: 'true', description: 'Remove headers, footers, and sidebars.' },
        { name: 'actions', type: 'array', description: 'Array of interaction steps (wait, click, scroll).' }
      ],
      code: {
        curl: `curl -X POST "${API}/scrape" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://stripe.com/docs",
    "formats": ["markdown"],
    "onlyMainContent": true,
    "actions": [
      { "type": "wait", "milliseconds": 2000 },
      { "type": "click", "selector": "#menu-button" }
    ]
  }'`,
        python: `import requests

url = "${API}/scrape"
payload = {
    "url": "https://stripe.com/docs",
    "formats": ["markdown"],
    "onlyMainContent": True,
    "actions": [
        { "type": "wait", "milliseconds": 2000 },
        { "type": "click", "selector": "#menu-button" }
    ]
}
headers = {"Authorization": "Bearer YOUR_API_KEY"}

response = requests.post(url, json=payload, headers=headers)
print(response.json())`,
        javascript: `const response = await fetch('${API}/scrape', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    url: 'https://stripe.com/docs',
    formats: ['markdown'],
    onlyMainContent: true,
    actions: [
      { type: 'wait', milliseconds: 2000 },
      { type: 'click', selector: '#menu-button' }
    ]
  })
});

const data = await response.json();
console.log(data);`
      }
    },
    {
      method: 'POST',
      path: '/v1/crawl',
      description: 'Initiate an asynchronous crawl job for a full domain.',
      params: [
        { name: 'url', type: 'string', required: true, description: 'The seed URL to start crawling from.' },
        { name: 'limit', type: 'integer', default: '100', description: 'Maximum number of pages to crawl.' },
        { name: 'maxDepth', type: 'integer', default: '2', description: 'Maximum crawl depth.' },
        { name: 'webhook', type: 'string', description: 'Destination URL for event notifications.' }
      ],
      code: {
        curl: `curl -X POST "${API}/crawl" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://example.com",
    "limit": 100,
    "webhook": "https://your-app.com/webhooks/crawl"
  }'`,
        python: `import requests

url = "${API}/crawl"
payload = {
    "url": "https://example.com",
    "limit": 100,
    "webhook": "https://your-app.com/webhooks/crawl"
}
headers = {"Authorization": "Bearer YOUR_API_KEY"}

response = requests.post(url, json=payload, headers=headers)
print(response.json())`,
        javascript: `const response = await fetch('${API}/crawl', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    url: 'https://example.com',
    limit: 100,
    webhook: 'https://your-app.com/webhooks/crawl'
  })
});

const data = await response.json();
console.log(data);`
      }
    },
    {
      method: 'GET',
      path: '/v1/crawl/{id}',
      description: 'Retrieve status and results for a specific crawl job.',
      params: [
        { name: 'id', type: 'string', required: true, description: 'The unique crawl job identifier.' }
      ],
      code: {
        curl: `curl "${API}/crawl/job_9k2f1" \\
  -H "Authorization: Bearer YOUR_API_KEY"`,
        python: `import requests

url = "${API}/crawl/job_9k2f1"
headers = {"Authorization": "Bearer YOUR_API_KEY"}

response = requests.get(url, headers=headers)
print(response.json())`,
        javascript: `const response = await fetch('${API}/crawl/job_9k2f1', {
  headers: { 'Authorization': 'Bearer YOUR_API_KEY' }
});

const data = await response.json();
console.log(data);`
      }
    },
    {
      method: 'GET',
      path: '/v1/jobs',
      description: 'List recent jobs for the authenticated user (playground “Recent runs”).',
      params: [
        { name: 'limit', type: 'integer', default: '50', description: 'Max jobs to return (1–200).' },
      ],
      code: {
        curl: `curl "${API}/jobs?limit=30" \\
  -H "Authorization: Bearer YOUR_API_KEY"`,
        python: `import requests

url = "${API}/jobs"
headers = {"Authorization": "Bearer YOUR_API_KEY"}

response = requests.get(url, params={"limit": 30}, headers=headers)
print(response.json())`,
        javascript: `const response = await fetch('${API}/jobs?limit=30', {
  headers: { 'Authorization': 'Bearer YOUR_API_KEY' }
});

const data = await response.json();
console.log(data);`
      }
    },
    {
      method: 'POST',
      path: '/v1/map',
      description: 'Discover all links on a domain without extracting content.',
      params: [
        { name: 'url', type: 'string', required: true, description: 'The seed URL to map.' },
        { name: 'search', type: 'string', description: 'Filter links by search query.' },
        { name: 'ignoreSubdomains', type: 'boolean', default: 'false', description: 'Ignore links to subdomains.' }
      ],
      code: {
        curl: `curl -X POST "${API}/map" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "url": "https://example.com",
    "search": "blog"
  }'`,
        python: `import requests

url = "${API}/map"
payload = {
    "url": "https://example.com",
    "search": "blog"
}
headers = {"Authorization": "Bearer YOUR_API_KEY"}

response = requests.post(url, json=payload, headers=headers)
print(response.json())`,
        javascript: `const response = await fetch('${API}/map', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    url: 'https://example.com',
    search: 'blog'
  })
});

const data = await response.json();
console.log(data);`
      }
    },
    {
      method: 'GET',
      path: '/v1/capabilities',
      description: 'Public instance flags (hosted, BYOK, queue, credential source, registration).',
      params: [],
      code: {
        curl: `curl "${API}/capabilities"`,
        python: `import requests\nprint(requests.get("${API}/capabilities").json())`,
        javascript: `const data = await fetch('${API}/capabilities').then(r => r.json());\nconsole.log(data);`,
      },
    },
    {
      method: 'GET',
      path: '/v1/usage/fetch-savings',
      description: 'Estimated credit savings vs always-ASP baseline (session auth).',
      params: [
        { name: 'days', type: 'integer', default: '30', description: 'Lookback window.' },
      ],
      code: {
        curl: `curl "${API}/usage/fetch-savings?days=30" \\\n  -H "Authorization: Bearer SESSION_TOKEN"`,
        python: `import requests\nr = requests.get("${API}/usage/fetch-savings", headers={"Authorization": "Bearer SESSION_TOKEN"})\nprint(r.json())`,
        javascript: `const data = await fetch('${API}/usage/fetch-savings?days=30', {\n  headers: { Authorization: 'Bearer SESSION_TOKEN' }\n}).then(r => r.json());\nconsole.log(data);`,
      },
    },
    {
      method: 'GET',
      path: '/v1/providers',
      description: 'List BYOK provider credentials (session auth). Keys never returned in full.',
      params: [],
      code: {
        curl: `curl "${API}/providers" \\\n  -H "Authorization: Bearer SESSION_TOKEN"`,
        python: `import requests\nr = requests.get("${API}/providers", headers={"Authorization": "Bearer SESSION_TOKEN"})\nprint(r.json())`,
        javascript: `const data = await fetch('${API}/providers', {\n  headers: { Authorization: 'Bearer SESSION_TOKEN' }\n}).then(r => r.json());\nconsole.log(data);`,
      },
    },
    {
      method: 'POST',
      path: '/v1/providers',
      description: 'Store an encrypted Scrape.do or Scrapfly key (requires BYOK_ENABLED).',
      params: [
        { name: 'provider', type: 'string', required: true, description: 'scrapedo | scrapfly' },
        { name: 'api_key', type: 'string', required: true, description: 'Provider secret (min 8 chars).' },
        { name: 'label', type: 'string', description: 'Optional label.' },
      ],
      code: {
        curl: `curl -X POST "${API}/providers" \\\n  -H "Authorization: Bearer SESSION_TOKEN" \\\n  -H "Content-Type: application/json" \\\n  -d '{"provider":"scrapedo","api_key":"YOUR_PROVIDER_KEY","label":"prod"}'`,
        python: `import requests\nr = requests.post("${API}/providers", headers={"Authorization": "Bearer SESSION_TOKEN"}, json={"provider":"scrapedo","api_key":"YOUR_PROVIDER_KEY"})\nprint(r.json())`,
        javascript: `const data = await fetch('${API}/providers', {\n  method: 'POST',\n  headers: { Authorization: 'Bearer SESSION_TOKEN', 'Content-Type': 'application/json' },\n  body: JSON.stringify({ provider: 'scrapedo', api_key: 'YOUR_PROVIDER_KEY' })\n}).then(r => r.json());\nconsole.log(data);`,
      },
    },
    {
      method: 'POST',
      path: '/v1/auth/login',
      description: 'Create a session token for account routes (keys, providers, usage).',
      params: [
        { name: 'email', type: 'string', required: true, description: 'Account email.' },
        { name: 'password', type: 'string', required: true, description: 'Account password.' },
      ],
      code: {
        curl: `curl -X POST "${API}/auth/login" \\\n  -H "Content-Type: application/json" \\\n  -d '{"email":"you@example.com","password":"…"}'`,
        python: `import requests\nr = requests.post("${API}/auth/login", json={"email":"you@example.com","password":"…"})\nprint(r.json()["session_token"])`,
        javascript: `const data = await fetch('${API}/auth/login', {\n  method: 'POST',\n  headers: { 'Content-Type': 'application/json' },\n  body: JSON.stringify({ email: 'you@example.com', password: '…' })\n}).then(r => r.json());\nconsole.log(data.session_token);`,
      },
    },
    {
      method: 'POST',
      path: '/v1/keys',
      description: 'Create an API key (fs_…) for scrape/crawl/map (session auth).',
      params: [
        { name: 'name', type: 'string', required: true, description: 'Key label.' },
      ],
      code: {
        curl: `curl -X POST "${API}/keys" \\\n  -H "Authorization: Bearer SESSION_TOKEN" \\\n  -H "Content-Type: application/json" \\\n  -d '{"name":"ci"}'`,
        python: `import requests\nr = requests.post("${API}/keys", headers={"Authorization": "Bearer SESSION_TOKEN"}, json={"name":"ci"})\nprint(r.json()["key"]["value"])`,
        javascript: `const data = await fetch('${API}/keys', {\n  method: 'POST',\n  headers: { Authorization: 'Bearer SESSION_TOKEN', 'Content-Type': 'application/json' },\n  body: JSON.stringify({ name: 'ci' })\n}).then(r => r.json());\nconsole.log(data.key.value);`,
      },
    },
    {
      method: 'POST',
      path: '/v1/scrape (extractMedia)',
      description: 'Optional media extraction — returns manifest URLs only (no proxy/download).',
      params: [
        { name: 'extractMedia', type: 'boolean', description: 'When true, run registered custom extractors.' },
      ],
      code: {
        curl: `curl -X POST "${API}/scrape" \\\n  -H "Authorization: Bearer YOUR_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"url":"https://example.com","formats":["markdown"],"extractMedia":true}'`,
        python: `import requests\nr = requests.post("${API}/scrape", headers={"Authorization": "Bearer YOUR_API_KEY"}, json={"url":"https://example.com","formats":["markdown"],"extractMedia":True})\nprint(r.json())`,
        javascript: `const data = await fetch('${API}/scrape', {\n  method: 'POST',\n  headers: { Authorization: 'Bearer YOUR_API_KEY', 'Content-Type': 'application/json' },\n  body: JSON.stringify({ url: 'https://example.com', formats: ['markdown'], extractMedia: true })\n}).then(r => r.json());\nconsole.log(data);`,
      },
    },
  ];

  return (
    <div className="space-y-8 pb-20 max-w-5xl mx-auto">
      <div className="space-y-2">
        <h2 className="text-3xl font-heading font-bold tracking-tight text-white flex items-center gap-3">
          <Terminal className="h-8 w-8 text-orange-500" />
          API Documentation
        </h2>
        <p className="text-muted-foreground text-lg max-w-3xl">
          Programmatically extract Markdown and structured JSON from any website using our API-first engine.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-orange-500/5 border-orange-500/20">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-widest text-orange-400">Base URL</CardTitle>
          </CardHeader>
          <CardContent>
            <code className="text-sm font-mono text-orange-200">{API}</code>
            <p className="mt-2 text-xs text-muted-foreground">
              Your instance — override with <code className="text-zinc-400">VITE_API_BASE_URL</code> if the API is on another host.
            </p>
          </CardContent>
        </Card>
        <Card className="bg-card/40 border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Auth Strategy</CardTitle>
          </CardHeader>
          <CardContent>
            <code className="text-sm font-mono text-zinc-400">Bearer YOUR_API_KEY</code>
          </CardContent>
        </Card>
        <Card className="bg-card/40 border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Response Rate</CardTitle>
          </CardHeader>
          <CardContent>
             <div className="flex items-center gap-2 text-sm font-mono text-zinc-400">
               <Zap className="h-3 w-3 text-orange-500" />
               Sub-second latency
             </div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-12">
        {endpoints.map((ep, i) => (
          <div key={i} className="space-y-6">
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Badge className="bg-orange-600 font-mono font-bold">{ep.method}</Badge>
                <code className="text-xl font-mono font-semibold text-white tracking-tight">{ep.path}</code>
              </div>
              <p className="text-muted-foreground">{ep.description}</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <Card className="lg:col-span-5 bg-card/20 border-border/50">
                <CardHeader className="p-4 border-b">
                   <CardTitle className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Parameters</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="divide-y divide-border/50">
                    {ep.params.map((p, j) => (
                      <div key={j} className="p-4 space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-bold text-orange-400">{p.name}</span>
                          <span className="text-[10px] text-muted-foreground px-1.5 py-0.5 rounded bg-muted/50 border border-border">
                            {p.type}
                          </span>
                          {p.required && (
                            <span className="text-[10px] font-black text-red-500 uppercase">Required</span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">{p.description}</p>
                        {p.default && (
                          <div className="text-[10px] text-muted-foreground">
                            Default: <code className="text-orange-300">{p.default}</code>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="lg:col-span-7 bg-zinc-950 border-orange-500/10 overflow-hidden shadow-2xl">
                <CardHeader className="p-0 border-b border-white/5 bg-zinc-900/50">
                  <div className="flex items-center justify-between px-4 py-2">
                    <div className="flex items-center gap-1">
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className={cn("h-7 px-3 text-[10px] font-bold uppercase", activeLang === 'curl' ? "text-orange-500 bg-orange-500/10" : "text-muted-foreground")}
                        onClick={() => setActiveLang('curl')}
                      >
                        cURL
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className={cn("h-7 px-3 text-[10px] font-bold uppercase", activeLang === 'python' ? "text-orange-500 bg-orange-500/10" : "text-muted-foreground")}
                        onClick={() => setActiveLang('python')}
                      >
                        Python
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className={cn("h-7 px-3 text-[10px] font-bold uppercase", activeLang === 'javascript' ? "text-orange-500 bg-orange-500/10" : "text-muted-foreground")}
                        onClick={() => setActiveLang('javascript')}
                      >
                        JS
                      </Button>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="icon" 
                      className="h-7 w-7 text-muted-foreground hover:text-white"
                      onClick={() => copyToClipboard(ep.code[activeLang])}
                    >
                      <Copy className="h-3 w-3" />
                    </Button>
                  </div>
                </CardHeader>
                <ScrollArea className="h-[300px]">
                  <pre className="p-4 text-xs font-mono text-orange-100/80 leading-relaxed overflow-x-auto">
                    {ep.code[activeLang]}
                  </pre>
                </ScrollArea>
              </Card>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

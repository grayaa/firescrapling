import React from 'react';
import { Button } from '../components/ui/button';
import {
  Check,
  ChevronRight,
  Copy,
  Terminal,
  KeyRound,
  Layers,
  Webhook,
  Activity,
  Cpu,
  BookOpen,
} from 'lucide-react';

const GITHUB_URL = 'https://github.com/firescrapling/firescrapling';
const CLONE_CMD = `git clone ${GITHUB_URL}.git
cd firescrapling
cp .env.example .env
docker compose up --build`;

const TIERS = [
  { name: 'local', weight: 0, desc: 'In-process fetch' },
  { name: 'sf_static', weight: 1, desc: 'Paid static HTML' },
  { name: 'sf_js', weight: 5, desc: '+ JS render' },
  { name: 'sf_asp', weight: 25, desc: '+ anti-bot' },
  { name: 'sf_residential', weight: 75, desc: '+ residential' },
];

export function LandingHero({ onViewDocs }: { onViewDocs: () => void; onGetStarted?: () => void }) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    void navigator.clipboard.writeText(CLONE_CMD.replace(/\n/g, ' && '));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative pt-20 pb-16 md:pt-28 md:pb-20 overflow-hidden">
      <div className="absolute inset-0 bg-mesh opacity-40 pointer-events-none" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] bg-primary/10 blur-[120px] rounded-full pointer-events-none" />

      <div className="container mx-auto px-6 relative z-10 text-center space-y-8">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-orange-400">
          Open source · Self-host first
        </p>

        <h1 className="text-4xl md:text-6xl lg:text-7xl font-heading font-black tracking-tighter text-white leading-[0.95] max-w-4xl mx-auto">
          FireScrapling
        </h1>

        <p className="text-muted-foreground text-lg md:text-xl max-w-2xl mx-auto font-medium">
          Cost-control scrape layer for teams already on Scrape.do or Scrapfly. Escalate only when
          needed; turn pages into Markdown — on your box.
        </p>

        <div className="max-w-2xl mx-auto rounded-xl border border-white/10 bg-[#0A0A0B]/90 text-left overflow-hidden">
          <div className="h-10 border-b border-white/5 px-4 flex items-center justify-between bg-white/[0.02]">
            <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-1.5">
              <Terminal className="h-3 w-3" /> Quickstart
            </span>
            <button type="button" onClick={handleCopy} className="text-muted-foreground hover:text-white">
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </div>
          <pre className="p-5 font-mono text-sm text-zinc-300 whitespace-pre-wrap">{CLONE_CMD}</pre>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Button
            size="lg"
            className="h-12 px-8 text-sm font-bold uppercase tracking-widest bg-orange-600 hover:bg-orange-700"
            onClick={() => window.open(GITHUB_URL, '_blank')}
          >
            GitHub
          </Button>
          <Button
            onClick={onViewDocs}
            variant="outline"
            size="lg"
            className="h-12 px-8 text-sm font-bold uppercase tracking-widest border-white/10 bg-white/5"
          >
            Docs <ChevronRight className="ml-2 h-4 w-4" />
          </Button>
        </div>

        {/* Cost problem — tier weights */}
        <div className="pt-16 max-w-4xl mx-auto space-y-6">
          <h2 className="text-2xl md:text-3xl font-heading font-black text-white tracking-tight">
            The cost problem
          </h2>
          <p className="text-muted-foreground text-sm max-w-xl mx-auto">
            Always-on anti-bot is expensive. Relative modeled weights vs that baseline:
          </p>
          <div className="grid grid-cols-5 gap-2 md:gap-3">
            {TIERS.map((t) => (
              <div
                key={t.name}
                className="rounded-lg border border-white/10 bg-white/[0.03] px-2 py-4 space-y-2"
              >
                <div className="text-2xl md:text-3xl font-heading font-black text-orange-400">{t.weight}</div>
                <div className="text-[10px] font-mono text-white uppercase tracking-wider">{t.name}</div>
                <div className="text-[10px] text-muted-foreground hidden md:block">{t.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function FeaturesGrid() {
  const sections = [
    {
      title: 'How the ladder works',
      body: 'local → static → JS → ASP → residential. Stops at the first tier that works, then remembers the domain for ~24h so the next fetch skips cheap probes.',
      icon: Layers,
    },
    {
      title: 'BYOK',
      body: 'Your Scrape.do or Scrapfly key, encrypted at rest. When self-hosted there is no third-party meter — keys never leave your box.',
      icon: KeyRound,
    },
    {
      title: 'What you get',
      body: 'scrape / crawl / map → Markdown, Redis job queue, HMAC webhooks, estimated savings dashboard, optional MCP server.',
      icon: Activity,
    },
  ];

  const grid = [
    { title: 'Scrape & crawl', desc: 'BFS crawl with robots and concurrency caps', icon: Cpu },
    { title: 'Jobs + queue', desc: 'Redis RQ workers with thread fallback', icon: Layers },
    { title: 'Webhooks', desc: 'HMAC-signed delivery on job complete', icon: Webhook },
    { title: 'Savings', desc: 'Estimated credits vs always-ASP baseline', icon: Activity },
    { title: 'MCP', desc: 'stdio tools over the same HTTP API', icon: Terminal },
    { title: 'Docs', desc: 'Self-host quickstart and API reference', icon: BookOpen },
  ];

  return (
    <section className="py-20 container mx-auto px-6 space-y-20">
      {sections.map((s) => (
        <div key={s.title} className="max-w-3xl mx-auto text-center space-y-3">
          <div className="inline-flex p-3 rounded-lg bg-orange-500/10 text-orange-400">
            <s.icon className="h-5 w-5" />
          </div>
          <h2 className="text-2xl font-heading font-black text-white uppercase tracking-tight">{s.title}</h2>
          <p className="text-muted-foreground text-sm leading-relaxed">{s.body}</p>
        </div>
      ))}

      <div className="space-y-8">
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-heading font-black text-white uppercase">Capabilities</h2>
          <p className="text-muted-foreground text-xs uppercase tracking-widest font-bold">
            Backed by GET /v1/capabilities
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {grid.map((f) => (
            <div key={f.title} className="rounded-xl border border-white/10 bg-white/[0.02] p-6 space-y-2">
              <f.icon className="h-5 w-5 text-orange-500" />
              <h3 className="font-heading font-bold text-white">{f.title}</h3>
              <p className="text-xs text-muted-foreground">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="max-w-2xl mx-auto rounded-xl border border-white/10 p-8 space-y-4 text-left">
        <h2 className="text-xl font-heading font-black text-white uppercase">Self-host env</h2>
        <p className="text-sm text-muted-foreground">
          Copy <code className="text-orange-400">.env.example</code> → <code className="text-orange-400">.env</code>.
          Defaults: <code className="text-zinc-300">HOSTED_MODE=false</code>,{' '}
          <code className="text-zinc-300">PLAYGROUND_ENABLED=false</code>. Set{' '}
          <code className="text-zinc-300">SCRAPE_API_KEY</code> or{' '}
          <code className="text-zinc-300">SCRAPFLY_API_KEY</code> for paid fetch; enable BYOK with{' '}
          <code className="text-zinc-300">CREDENTIAL_ENCRYPTION_KEY</code>.
        </p>
        <a href={GITHUB_URL} className="text-sm text-orange-400 hover:underline inline-flex items-center gap-1">
          Full reference in the README <ChevronRight className="h-3 w-3" />
        </a>
      </div>

      <footer className="border-t border-white/5 pt-10 flex flex-wrap justify-center gap-8 text-[10px] font-black uppercase tracking-widest text-muted-foreground">
        <a href={GITHUB_URL} className="hover:text-white">
          GitHub
        </a>
        <span className="hover:text-white cursor-default">Docs</span>
        <span className="hover:text-white cursor-default">AGPL-3.0</span>
      </footer>
    </section>
  );
}

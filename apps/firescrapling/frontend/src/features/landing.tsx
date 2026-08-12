import React from 'react';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { 
  Zap, 
  Terminal, 
  ChevronRight, 
  Copy, 
  Check, 
  Code2, 
  Globe, 
  ShieldCheck, 
  Layers, 
  Activity, 
  Webhook, 
  Cpu
} from 'lucide-react';
import { cn } from '../lib/utils';
import { LandingPlayground } from './LandingPlayground';

export function LandingHero({ onGetStarted, onViewDocs }: { onGetStarted: () => void, onViewDocs: () => void }) {
  const [copied, setCopied] = React.useState(false);
  const codeSnippet = `curl -X POST "https://api.firescrapling.com/v1/scrape" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{ "url": "https://example.com", "schema": { "title": "string" } }'`;

  const handleCopy = () => {
    navigator.clipboard.writeText(codeSnippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative pt-20 pb-16 md:pt-32 md:pb-24 overflow-hidden">
      <div className="absolute inset-0 bg-mesh opacity-40 pointer-events-none" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] bg-primary/10 blur-[120px] rounded-full pointer-events-none" />
      
      <div className="container mx-auto px-6 relative z-10 text-center space-y-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-[10px] font-black uppercase tracking-widest text-orange-400 animate-in fade-in slide-in-from-top-4 duration-1000">
          <Zap className="h-3 w-3 fill-current" />
          <span>v1.5.0 Now Live with AI Extraction</span>
        </div>
        
        <h1 className="text-5xl md:text-7xl lg:text-8xl font-heading font-black tracking-tighter text-white leading-[0.9] max-w-5xl mx-auto">
          Turn any website into <span className="bg-gradient-to-r from-orange-400 to-red-500 bg-clip-text text-transparent">LLM-ready</span> data.
        </h1>
        
        <p className="text-muted-foreground text-lg md:text-xl max-w-2xl mx-auto font-medium">
          The API-first web scraping engine built for AI agents. Convert complex websites into clean Markdown or structured JSON in milliseconds.
        </p>
        
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
          <Button 
            onClick={onGetStarted}
            size="lg" 
            className="h-14 px-8 text-base font-bold uppercase tracking-widest bg-orange-600 hover:bg-orange-700 shadow-2xl shadow-orange-600/20 transition-all hover:scale-105 active:scale-95 w-full sm:w-auto"
          >
            Get Started for Free
          </Button>
          <Button 
            onClick={onViewDocs}
            variant="outline" 
            size="lg" 
            className="h-14 px-8 text-base font-bold uppercase tracking-widest border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 w-full sm:w-auto"
          >
            View Docs <ChevronRight className="ml-2 h-4 w-4" />
          </Button>
        </div>

        <LandingPlayground />

        <div className="max-w-4xl mx-auto mt-10 rounded-2xl border border-white/10 bg-[#0A0A0B]/80 backdrop-blur-xl shadow-3xl overflow-hidden group">
          <div className="h-10 border-b border-white/5 px-4 flex items-center justify-between bg-white/[0.02]">
            <div className="flex gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-rose-500/20 border border-rose-500/40" />
              <div className="w-2.5 h-2.5 rounded-full bg-amber-500/20 border border-amber-500/40" />
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/20 border border-emerald-500/40" />
            </div>
            <div className="flex items-center gap-4">
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-1.5">
                <Terminal className="h-3 w-3" /> Full API (auth)
              </span>
              <button type="button" onClick={handleCopy} className="text-muted-foreground hover:text-white transition-colors">
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>
          <div className="p-6 text-left overflow-x-auto font-mono text-sm leading-relaxed">
            <div className="flex gap-4">
              <div className="text-zinc-600 select-none border-r border-white/5 pr-4">
                {['1', '2', '3'].map(n => <div key={n}>{n}</div>)}
              </div>
              <pre className="text-zinc-300">
                <span className="text-orange-400">curl</span> -X POST <span className="text-emerald-400">"https://api.firescrapling.com/v1/scrape"</span> \<br />
                &nbsp;&nbsp;-H <span className="text-emerald-400">"Authorization: Bearer YOUR_API_KEY"</span> \<br />
                &nbsp;&nbsp;-d <span className="text-zinc-400">{`'{ "url": "https://example.com", "schema": { "title": "string" } }'`}</span>
              </pre>
            </div>
          </div>
        </div>

        {/* Social Proof */}
        <div className="pt-20 space-y-6">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Trusted by 2,000+ AI Teams & Engineers</p>
          <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-8 grayscale opacity-50 contrast-125">
             <div className="flex items-center gap-2 font-black text-xl italic tracking-tighter text-white">Vercel</div>
             <div className="flex items-center gap-2 font-black text-xl italic tracking-tighter text-white">Supabase</div>
             <div className="flex items-center gap-2 font-black text-xl italic tracking-tighter text-white">Stripe</div>
             <div className="flex items-center gap-2 font-black text-xl italic tracking-tighter text-white">OpenAI</div>
             <div className="flex items-center gap-2 font-black text-xl italic tracking-tighter text-white">Anthropic</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function FeaturesGrid() {
  const features = [
    {
      title: "JS Rendering",
      desc: "Full browser impersonation to handle React, Vue, and Next.js sites seamlessly.",
      icon: Cpu,
      className: "md:col-span-2 md:row-span-1"
    },
    {
      title: "Proxy Rotation",
      desc: "Residential & datacenter proxies with automatic geographic failover.",
      icon: Globe,
      className: "md:col-span-1 md:row-span-2"
    },
    {
      title: "Markdown Output",
      desc: "LLM-ready, noise-free markdown generated instantly for your RAG pipelines.",
      icon: Code2,
      className: "md:col-span-1 md:row-span-1"
    },
    {
      title: "Scalable Queues",
      desc: "Process millions of pages concurrently with zero performance degradation.",
      icon: Layers,
      className: "md:col-span-1 md:row-span-1"
    },
    {
      title: "Anti-Bot Bypass",
      desc: "Bypass Cloudflare, Akamai, and DataDome using advanced stealth signatures.",
      icon: ShieldCheck,
      className: "md:col-span-1 md:row-span-1"
    },
    {
      title: "Real-time Webhooks",
      desc: "Get notified the millisecond an extraction is complete or a crawl job finishes.",
      icon: Webhook,
      className: "md:col-span-1 md:row-span-1"
    }
  ];

  return (
    <section className="py-24 container mx-auto px-6 space-y-12">
      <div className="text-center space-y-2">
        <h2 className="text-4xl font-heading font-black tracking-tight text-white uppercase">Engineered for Scale</h2>
        <p className="text-muted-foreground text-sm uppercase tracking-widest font-bold">The most powerful web extraction infrastructure on the planet</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 md:grid-rows-2 gap-4">
        {features.map((f, i) => (
          <div 
            key={i} 
            className={cn(
              "group relative p-8 rounded-3xl border border-white/5 bg-white/[0.02] overflow-hidden transition-all hover:bg-white/[0.05] hover:border-primary/20",
              f.className
            )}
          >
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
               <f.icon className="h-24 w-24 text-primary" />
            </div>
            <div className="relative z-10 space-y-4">
               <div className="p-3 rounded-2xl bg-primary/10 border border-primary/20 inline-block">
                 <f.icon className="h-6 w-6 text-primary" />
               </div>
               <div className="space-y-2">
                  <h3 className="text-xl font-heading font-black text-white">{f.title}</h3>
                  <p className="text-muted-foreground leading-relaxed text-sm">{f.desc}</p>
               </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

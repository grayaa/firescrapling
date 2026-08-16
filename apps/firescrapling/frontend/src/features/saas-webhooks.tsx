import React, { useEffect, useState } from 'react';
import { Webhook, Copy, CheckCircle2, Loader2, AlertTriangle } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { getCapabilities, type PlatformCapabilities } from '../restClient';

const EVENTS = [
  { name: 'scrape.completed', desc: 'Fired when a scrape finishes successfully.' },
  { name: 'scrape.failed', desc: 'Fired when a scrape fails.' },
  { name: 'crawl.completed', desc: 'Fired when a crawl job finishes.' },
  { name: 'crawl.failed', desc: 'Fired when a crawl job fails.' },
];

export function SaaSWebhooks() {
  const [caps, setCaps] = useState<PlatformCapabilities | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const c = await getCapabilities();
        if (!cancelled) setCaps(c);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load capabilities');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const sampleVerify = `const crypto = require('crypto');
function verify(secret, rawBody, signatureHeader) {
  const expected = 'sha256=' + crypto
    .createHmac('sha256', secret)
    .update(rawBody)
    .digest('hex');
  return crypto.timingSafeEqual(
    Buffer.from(expected),
    Buffer.from(signatureHeader || ''),
  );
}`;

  const copySample = async () => {
    try {
      await navigator.clipboard.writeText(sampleVerify);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="p-6 md:p-10 space-y-8 max-w-4xl animate-in fade-in duration-500">
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-primary/10 border border-primary/20">
            <Webhook className="h-5 w-5 text-primary" />
          </div>
          <h1 className="text-2xl font-heading font-black tracking-tight text-white uppercase">Webhooks</h1>
        </div>
        <p className="text-sm text-muted-foreground font-medium">
          Pass <code className="text-xs bg-muted px-1 rounded">webhook</code> on scrape/crawl requests.
          Deliveries are queued (Redis RQ) with HMAC-SHA256 signing and retries — they never block the job worker.
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground font-semibold">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading platform status…
        </div>
      )}
      {error && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-400 font-semibold flex gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}
      {caps && (
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="text-[10px] font-black uppercase">
            Queue {caps.queue ? 'online' : 'offline (inline fallback)'}
          </Badge>
          <Badge variant="outline" className="text-[10px] font-black uppercase">
            Webhooks enabled
          </Badge>
        </div>
      )}

      <Card className="border-white/5 bg-card/40">
        <CardHeader>
          <CardTitle className="text-sm font-bold uppercase tracking-widest">Events</CardTitle>
          <CardDescription className="text-xs">Payload includes job_id plus event-specific fields.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {EVENTS.map((ev) => (
            <div key={ev.name} className="flex items-start justify-between gap-4 border-b border-white/5 pb-3 last:border-0">
              <div>
                <code className="text-xs font-bold text-orange-400">{ev.name}</code>
                <p className="text-[11px] text-muted-foreground mt-1">{ev.desc}</p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="border-white/5 bg-card/40">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-sm font-bold uppercase tracking-widest">Verify signatures</CardTitle>
            <CardDescription className="text-xs">
              Header <code className="text-[10px]">X-FireScrapling-Signature: sha256=&lt;hex&gt;</code>
            </CardDescription>
          </div>
          <Button size="sm" variant="outline" className="h-8 text-[10px] font-bold uppercase" onClick={() => void copySample()}>
            {copied ? <CheckCircle2 className="h-3 w-3 mr-1.5" /> : <Copy className="h-3 w-3 mr-1.5" />}
            {copied ? 'Copied' : 'Copy'}
          </Button>
        </CardHeader>
        <CardContent>
          <pre className="text-[10px] font-mono bg-black/40 rounded-lg p-4 overflow-x-auto text-muted-foreground whitespace-pre-wrap">
            {sampleVerify}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}

import React from 'react';
import { Settings as SettingsIcon, Loader2 } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { getCapabilities, PlatformCapabilities } from '../restClient';

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 border-b border-white/5 last:border-0">
      <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">{label}</span>
      <span className="text-sm text-right text-white font-medium">{value}</span>
    </div>
  );
}

function yn(v: boolean | undefined) {
  return v ? (
    <Badge className="bg-emerald-600/20 text-emerald-300">on</Badge>
  ) : (
    <Badge variant="outline" className="text-muted-foreground">
      off
    </Badge>
  );
}

export function SaaSSettings() {
  const [caps, setCaps] = React.useState<PlatformCapabilities | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    getCapabilities()
      .then((c) => {
        if (!cancelled) setCaps(c);
      })
      .catch((err: any) => {
        if (!cancelled) setError(err?.message || 'Could not load capabilities');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground p-8">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading instance status…
      </div>
    );
  }

  return (
    <div className="space-y-8 p-1 max-w-3xl">
      <div>
        <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground mb-2">
          Instance
        </p>
        <h1 className="text-3xl font-heading font-black tracking-tight text-white flex items-center gap-3">
          <SettingsIcon className="h-8 w-8 text-orange-500" />
          Settings
        </h1>
        <p className="text-sm text-muted-foreground mt-2">
          Read-only status from <code className="text-xs">/v1/capabilities</code>. Configuration lives in
          environment variables — edit <code className="text-xs">.env</code> and restart.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <Card className="border-white/10 bg-card/40">
        <CardHeader>
          <CardTitle className="text-white">Mode</CardTitle>
          <CardDescription>Hosted surface vs self-host defaults</CardDescription>
        </CardHeader>
        <CardContent>
          <Row label="Hosted" value={yn(caps?.hosted)} />
          <Row label="Registration open" value={yn(caps?.registration_open)} />
          <Row label="Playground" value={yn(caps?.playground)} />
          <Row label="BYOK" value={yn(caps?.byok)} />
        </CardContent>
      </Card>

      <Card className="border-white/10 bg-card/40">
        <CardHeader>
          <CardTitle className="text-white">Fetch</CardTitle>
        </CardHeader>
        <CardContent>
          <Row label="Provider" value={caps?.fetch_provider ?? '—'} />
          <Row label="Credential source" value={caps?.credential_source ?? '—'} />
          <Row label="Escalation" value={yn(caps?.fetch_escalate)} />
          <Row
            label="Domain profile TTL"
            value={
              caps?.domain_profile_ttl_seconds != null
                ? `${caps.domain_profile_ttl_seconds}s`
                : '—'
            }
          />
          <Row
            label="Env provider"
            value={
              caps?.platform_env
                ? `${caps.platform_env.provider} (${caps.platform_env.env_var})`
                : 'none'
            }
          />
        </CardContent>
      </Card>

      <Card className="border-white/10 bg-card/40">
        <CardHeader>
          <CardTitle className="text-white">Infrastructure</CardTitle>
        </CardHeader>
        <CardContent>
          <Row label="Database" value={caps?.database_backend ?? '—'} />
          <Row label="Queue / Redis" value={yn(caps?.queue)} />
          <Row label="Worker concurrency" value={caps?.worker_concurrency ?? '—'} />
        </CardContent>
      </Card>

      <Card className="border-white/10 bg-card/40">
        <CardHeader>
          <CardTitle className="text-white">Security</CardTitle>
        </CardHeader>
        <CardContent>
          <Row label="Encryption key" value={yn(caps?.encryption_key_present)} />
          <Row label="Admin console" value={yn(caps?.admin_configured)} />
          <Row
            label="Rate limit / min"
            value={caps?.rate_limit_per_minute ?? '—'}
          />
        </CardContent>
      </Card>

      <Card className="border-white/10 bg-card/40">
        <CardHeader>
          <CardTitle className="text-white">Build</CardTitle>
        </CardHeader>
        <CardContent>
          <Row label="Version" value={caps?.version ?? 'dev'} />
          <Row label="Commit" value={<code className="text-xs">{caps?.commit ?? 'unknown'}</code>} />
        </CardContent>
      </Card>
    </div>
  );
}

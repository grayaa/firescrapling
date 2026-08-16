import React from 'react';
import {
  KeyRound,
  Plus,
  Trash2,
  ShieldCheck,
  Loader2,
  RefreshCcw,
  Server,
  AlertTriangle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
import {
  createProvider,
  deleteProvider,
  getCapabilities,
  listProviders,
  PlatformCapabilities,
  ProviderCredential,
  verifyProvider,
} from '../restClient';

export function SaaSProviders() {
  const [rows, setRows] = React.useState<ProviderCredential[]>([]);
  const [caps, setCaps] = React.useState<PlatformCapabilities | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [open, setOpen] = React.useState(false);
  const [provider, setProvider] = React.useState<'scrapedo' | 'scrapfly'>('scrapedo');
  const [apiKey, setApiKey] = React.useState('');
  const [label, setLabel] = React.useState('');
  const [busy, setBusy] = React.useState(false);

  const byokOn = caps?.byok === true;
  const platformEnv = caps?.platform_env ?? null;

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try {
      const [providers, capabilities] = await Promise.all([listProviders(), getCapabilities()]);
      setRows(providers);
      setCaps(capabilities);
      setError(null);
    } catch (err: any) {
      setError(err?.message || 'Could not load providers');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleCreate = async () => {
    if (!byokOn) return;
    setBusy(true);
    try {
      await createProvider({
        provider,
        api_key: apiKey.trim(),
        label: label.trim() || undefined,
      });
      setOpen(false);
      setApiKey('');
      setLabel('');
      await refresh();
    } catch (err: any) {
      setError(err?.message || 'Could not save provider key');
    } finally {
      setBusy(false);
    }
  };

  const byokTakesPrecedence =
    Boolean(platformEnv) && rows.some((r) => r.provider === platformEnv?.provider && r.status === 'active');

  return (
    <div className="space-y-8 p-1">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground mb-2">
            Bring your own key
          </p>
          <h1 className="text-3xl font-heading font-black tracking-tight text-white">Providers</h1>
          <p className="text-sm text-muted-foreground mt-2 max-w-xl">
            Attach a Scrape.do or Scrapfly key here, or set <code className="text-xs">SCRAPE_API_KEY</code> /
            <code className="text-xs"> SCRAPFLY_API_KEY</code> in the environment. BYOK credentials take
            precedence when present.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void refresh()}>
            <RefreshCcw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button
            size="sm"
            className="bg-orange-600"
            onClick={() => setOpen(true)}
            disabled={!byokOn}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add key
          </Button>
        </div>
      </div>

      {!byokOn && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-100 flex gap-3">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-400" />
          <div>
            <p className="font-bold">BYOK is disabled</p>
            <p className="text-amber-100/80 mt-1">
              Set <code className="text-xs">BYOK_ENABLED=true</code> and{' '}
              <code className="text-xs">CREDENTIAL_ENCRYPTION_KEY</code> to use your own provider keys.
              Until then, only environment keys are used.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {platformEnv && (
        <Card className="border-white/10 bg-card/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <Server className="h-5 w-5 text-sky-400" />
              Environment provider
            </CardTitle>
            <CardDescription>
              Configured via environment — read-only. No key hint is shown.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-white/10 px-4 py-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white uppercase tracking-wider text-xs">
                    {platformEnv.provider}
                  </span>
                  <Badge variant="outline" className="text-[10px] uppercase tracking-widest">
                    via {platformEnv.env_var}
                  </Badge>
                  {byokTakesPrecedence && (
                    <Badge className="bg-emerald-600/20 text-emerald-300 text-[10px] uppercase tracking-widest">
                      BYOK overrides
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-1">Configured via environment</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="border-white/10 bg-card/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-white">
            <KeyRound className="h-5 w-5 text-orange-500" />
            Saved credentials
          </CardTitle>
          <CardDescription>
            Keys are encrypted at rest. Only a short hint is shown after save.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </div>
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center">
              No BYOK keys yet. Add a key here, or set <code className="text-xs">SCRAPE_API_KEY</code> /{' '}
              <code className="text-xs">SCRAPFLY_API_KEY</code> in the environment.
            </p>
          ) : (
            <div className="space-y-3">
              {rows.map((row) => (
                <div
                  key={row.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-white/10 px-4 py-3"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-white uppercase tracking-wider text-xs">
                        {row.provider}
                      </span>
                      <Badge
                        className={
                          row.status === 'active'
                            ? 'bg-emerald-600/20 text-emerald-300'
                            : 'bg-zinc-700 text-zinc-300'
                        }
                      >
                        {row.status}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {row.label || 'Untitled'} · hint {row.key_hint}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={async () => {
                        try {
                          await verifyProvider(row.id);
                          await refresh();
                        } catch (err: any) {
                          setError(err?.message || 'Verify failed');
                        }
                      }}
                    >
                      <ShieldCheck className="h-4 w-4 mr-1" />
                      Verify
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-400"
                      onClick={async () => {
                        try {
                          await deleteProvider(row.id);
                          await refresh();
                        } catch (err: any) {
                          setError(err?.message || 'Delete failed');
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add provider key</DialogTitle>
            <DialogDescription>
              Stored encrypted. Never logged or returned in full after save.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Provider</Label>
              <select
                className="w-full rounded-md border border-white/10 bg-black/40 px-3 py-2 text-sm"
                value={provider}
                onChange={(e) => setProvider(e.target.value as 'scrapedo' | 'scrapfly')}
              >
                <option value="scrapedo">Scrape.do</option>
                <option value="scrapfly">Scrapfly</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>API key</Label>
              <Input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Provider secret"
              />
            </div>
            <div className="space-y-2">
              <Label>Label (optional)</Label>
              <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="prod" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button className="bg-orange-600" disabled={busy || apiKey.trim().length < 8} onClick={() => void handleCreate()}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

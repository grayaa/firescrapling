import React from 'react';
import { PiggyBank, Loader2, RefreshCcw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { getFetchSavings, FetchSavingsSummary } from '../restClient';

export function SaaSSavings() {
  const [data, setData] = React.useState<FetchSavingsSummary | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try {
      setData(await getFetchSavings(30));
      setError(null);
    } catch (err: any) {
      setError(err?.message || 'Could not load savings');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="space-y-8 p-1">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground mb-2">
            Cost control
          </p>
          <h1 className="text-3xl font-heading font-black tracking-tight text-white">Savings</h1>
          <p className="text-sm text-muted-foreground mt-2 max-w-xl">
            Estimated credits avoided by escalating only when needed, versus always paying for
            anti-bot (ASP) fetches. Figures are modeled — not your provider invoice.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refresh()}>
          <RefreshCcw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground py-16 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading…
        </div>
      ) : data ? (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="border-white/10 bg-card/40">
              <CardHeader className="pb-2">
                <CardDescription>Estimated savings</CardDescription>
                <CardTitle className="text-3xl text-emerald-400 flex items-center gap-2">
                  <PiggyBank className="h-7 w-7" />
                  {data.savings_pct}%
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Badge variant="outline" className="text-[10px] uppercase tracking-widest">
                  Estimated · {data.window_days}d
                </Badge>
              </CardContent>
            </Card>
            <Card className="border-white/10 bg-card/40">
              <CardHeader className="pb-2">
                <CardDescription>Baseline (always ASP)</CardDescription>
                <CardTitle className="text-2xl text-white">{data.baseline_cost}</CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground">
                Modeled units vs tier `{data.baseline_tier}`
              </CardContent>
            </Card>
            <Card className="border-white/10 bg-card/40">
              <CardHeader className="pb-2">
                <CardDescription>Actual (escalation)</CardDescription>
                <CardTitle className="text-2xl text-white">{data.actual_cost}</CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground">
                Across {data.events} fetches · saved {data.saved_cost}
              </CardContent>
            </Card>
          </div>

          <Card className="border-white/10 bg-card/40">
            <CardHeader>
              <CardTitle className="text-white">Per-domain breakdown</CardTitle>
              <CardDescription>Where escalation saved the most (estimated)</CardDescription>
            </CardHeader>
            <CardContent>
              {!data.by_domain?.length ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No fetch events yet. Run scrapes to populate savings.
                </p>
              ) : (
                <div className="space-y-2">
                  {data.by_domain.map((d) => (
                    <div
                      key={d.domain}
                      className="flex items-center justify-between rounded-lg border border-white/10 px-4 py-3 text-sm"
                    >
                      <div>
                        <p className="font-mono text-white">{d.domain}</p>
                        <p className="text-xs text-muted-foreground">{d.events} events</p>
                      </div>
                      <div className="text-right">
                        <p className="text-emerald-400 font-bold">{d.savings_pct}%</p>
                        <p className="text-xs text-muted-foreground">
                          {d.actual_cost} / {d.baseline_cost}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}

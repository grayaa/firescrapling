import React from 'react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  AreaChart, 
  Area,
  LineChart,
  Line,
  Legend
} from 'recharts';
import { 
  Zap, 
  CheckCircle2, 
  AlertCircle, 
  Globe, 
  Clock, 
  ExternalLink,
  MoreVertical,
  Activity,
  ArrowUpRight,
  ShieldCheck,
  Webhook,
  History
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../components/ui/table';
import { Button } from '../components/ui/button';
import { cn } from '../lib/utils';
import { getUsageSummary, UsageSummary } from '../restClient';

const WINDOW_DAYS = 30;

function relativeTime(ts: string | null): string {
  if (!ts) return '—';
  const d = new Date(ts.includes('T') ? ts : `${ts.replace(' ', 'T')}Z`);
  if (Number.isNaN(d.getTime())) return ts;
  const secs = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (secs < 60) return 'Just now';
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

export function SaaSOverview() {
  const [summary, setSummary] = React.useState<UsageSummary | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;
    getUsageSummary(WINDOW_DAYS)
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch((err: any) => {
        if (!cancelled) setError(err?.message || 'Could not load usage data');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const stats = [
    {
      label: "Pages Extracted",
      value: (summary?.pages_crawled ?? 0).toLocaleString(),
      delta: `${WINDOW_DAYS}d`,
      icon: Globe,
      color: "text-blue-500",
      bg: "bg-blue-500/10",
    },
    {
      label: "API Success Rate",
      value: `${summary?.success_rate ?? 0}%`,
      delta: `${summary?.failed_requests ?? 0} failed`,
      icon: ShieldCheck,
      color: "text-emerald-500",
      bg: "bg-emerald-500/10",
    },
    {
      label: "Total Requests",
      value: (summary?.total_requests ?? 0).toLocaleString(),
      delta: `${summary?.active_keys ?? 0} keys`,
      icon: Activity,
      color: "text-violet-500",
      bg: "bg-violet-500/10",
    },
    {
      label: "P95 Latency",
      value: `${summary?.p95_latency_ms ?? 0} ms`,
      delta: `avg ${summary?.avg_latency_ms ?? 0} ms`,
      icon: Zap,
      color: "text-amber-500",
      bg: "bg-amber-500/10",
    },
  ];

  const chartData = (summary?.daily ?? []).map((d) => ({
    name: d.date?.slice(5) ?? '',
    success: d.success,
    failed: d.failed,
  }));

  const recentCrawls = (summary?.recent_jobs ?? []).map((j) => ({
    id: j.id,
    url: j.url,
    status: j.status,
    pages: j.pages,
    time: relativeTime(j.created_at),
  }));

  return (
    <div className="p-6 md:p-8 space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-3xl font-heading font-black tracking-tight text-white uppercase">Overview</h2>
          <p className="text-muted-foreground text-sm uppercase tracking-widest font-bold">Your scraping engine performance at a glance</p>
        </div>
        <div className="flex gap-2">
           <Button variant="outline" className="border-border/50 bg-muted/20">
             <Clock className="h-4 w-4 mr-2" /> Last 30 Days
           </Button>
           <Button className="bg-primary hover:bg-primary/90">
             <Zap className="h-4 w-4 mr-2 fill-current" /> Upgrade Plan
           </Button>
        </div>
      </div>

      {error && (
        <div className="bg-rose-500/5 border border-rose-500/20 rounded-2xl p-4 flex items-center gap-3 text-rose-400">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p className="text-[11px] font-bold uppercase tracking-widest">{error}</p>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
        {stats.map((stat, i) => (
          <Card key={i} className="bg-card/40 border-border/50 backdrop-blur-md group hover:border-primary/30 transition-all duration-300 active:scale-[0.98]">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className={cn("p-2 rounded-xl border border-border/50 transition-colors group-hover:bg-primary/5", stat.bg, stat.color)}>
                  <stat.icon className="h-5 w-5" />
                </div>
                <Badge variant="outline" className={cn(
                  "text-[10px] font-bold tracking-widest uppercase",
                  stat.delta.startsWith('+') ? "text-emerald-500 bg-emerald-500/5 border-emerald-500/20" : 
                  stat.delta.startsWith('-') ? "text-rose-500 bg-rose-500/5 border-rose-500/20" : "text-zinc-400 bg-zinc-400/5 border-zinc-400/20"
                )}>
                  {stat.delta}
                </Badge>
              </div>
              <div className="space-y-1">
                <div className="text-2xl font-heading font-black text-white">{stat.value}</div>
                <div className="text-xs font-bold uppercase tracking-widest text-muted-foreground">{stat.label}</div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 md:gap-8">
        {/* Usage Chart */}
        <Card className="lg:col-span-2 bg-card/40 border-border/50 backdrop-blur-md overflow-hidden">
          <CardHeader className="bg-muted/10 border-b border-border/50 pb-4">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-sm font-bold uppercase tracking-widest flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" /> API Performance
                </CardTitle>
                <CardDescription className="text-[10px] uppercase font-bold text-muted-foreground mt-1">Total requests vs failed requests</CardDescription>
              </div>
              <div className="flex items-center gap-4">
                 <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground">
                    <div className="h-2 w-2 rounded-full bg-primary" /> SUCCESS
                 </div>
                 <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground">
                    <div className="h-2 w-2 rounded-full bg-rose-500" /> FAILED
                 </div>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-6">
             <div className="h-[300px] w-full">
               <ResponsiveContainer width="100%" height="100%">
                 <AreaChart data={chartData}>
                   <defs>
                     <linearGradient id="colorSuccess" x1="0" y1="0" x2="0" y2="1">
                       <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3}/>
                       <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0}/>
                     </linearGradient>
                     <linearGradient id="colorFailed" x1="0" y1="0" x2="0" y2="1">
                       <stop offset="5%" stopColor="rgb(244 63 94)" stopOpacity={0.3}/>
                       <stop offset="95%" stopColor="rgb(244 63 94)" stopOpacity={0}/>
                     </linearGradient>
                   </defs>
                   <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                   <XAxis 
                     dataKey="name" 
                     stroke="rgba(255,255,255,0.3)" 
                     fontSize={10} 
                     tickLine={false} 
                     axisLine={false}
                   />
                   <YAxis 
                     stroke="rgba(255,255,255,0.3)" 
                     fontSize={10} 
                     tickLine={false} 
                     axisLine={false}
                   />
                   <Tooltip 
                     contentStyle={{ backgroundColor: 'rgba(9, 9, 11, 0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', backdropFilter: 'blur(8px)' }}
                     itemStyle={{ fontSize: '10px', fontWeight: 'bold', textTransform: 'uppercase' }}
                   />
                   <Area type="monotone" dataKey="success" stroke="hsl(var(--primary))" strokeWidth={3} fillOpacity={1} fill="url(#colorSuccess)" />
                   <Area type="monotone" dataKey="failed" stroke="rgb(244 63 94)" strokeWidth={2} fillOpacity={1} fill="url(#colorFailed)" strokeDasharray="5 5" />
                 </AreaChart>
               </ResponsiveContainer>
             </div>
          </CardContent>
        </Card>

        {/* Quick Actions / Recent Activity */}
        <Card className="bg-card/40 border-border/50 backdrop-blur-md overflow-hidden">
           <CardHeader className="bg-muted/10 border-b border-border/50 pb-4">
              <CardTitle className="text-sm font-bold uppercase tracking-widest flex items-center gap-2">
                <History className="h-4 w-4 text-amber-500" /> Recent Activity
              </CardTitle>
           </CardHeader>
           <CardContent className="p-0">
              <div className="divide-y divide-border/50">
                {recentCrawls.length === 0 && (
                  <div className="p-8 text-center text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                    {loading ? 'Loading activity…' : 'No jobs yet — run one from the Playground'}
                  </div>
                )}
                {recentCrawls.map(crawl => (
                  <div key={crawl.id} className="p-4 hover:bg-muted/20 transition-colors group">
                     <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                           <Globe className="h-3 w-3 text-muted-foreground" />
                           <span className="text-[10px] font-mono text-primary truncate max-w-[150px]">{crawl.url}</span>
                        </div>
                        <Badge variant="outline" className={cn(
                          "text-[9px] font-black uppercase border-none px-1.5",
                          crawl.status === 'completed' ? "text-emerald-500 bg-emerald-500/10" :
                          crawl.status === 'processing' ? "text-blue-500 bg-blue-500/10 animate-pulse" : "text-rose-500 bg-rose-500/10"
                        )}>
                          {crawl.status}
                        </Badge>
                     </div>
                     <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground uppercase tracking-tighter">
                        <div className="flex gap-4">
                           <span>{crawl.pages} Pages</span>
                           <span>{crawl.time}</span>
                        </div>
                        <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity">
                           <ExternalLink className="h-3 w-3" />
                        </Button>
                     </div>
                  </div>
                ))}
              </div>
           </CardContent>
           <CardFooter className="p-4 bg-muted/5">
              <Button variant="ghost" size="sm" className="w-full text-[10px] font-bold uppercase tracking-widest text-muted-foreground hover:text-white">
                 View All Activity <ArrowUpRight className="h-3 w-3 ml-2" />
              </Button>
           </CardFooter>
        </Card>
      </div>

      <Card className="bg-card/40 border-border/50 backdrop-blur-md overflow-hidden">
        <CardHeader className="p-6 bg-muted/10 border-b border-border/50">
           <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-bold uppercase tracking-widest">Endpoint Breakdown</CardTitle>
              <Badge variant="secondary" className="text-[10px]">Last {WINDOW_DAYS} days</Badge>
           </div>
        </CardHeader>
        <CardContent className="p-0">
           <Table>
              <TableHeader className="bg-muted/5">
                 <TableRow className="hover:bg-transparent">
                    <TableHead className="text-[10px] uppercase font-black tracking-widest text-muted-foreground px-6">Endpoint</TableHead>
                    <TableHead className="text-[10px] uppercase font-black tracking-widest text-muted-foreground">Requests</TableHead>
                    <TableHead className="text-[10px] uppercase font-black tracking-widest text-muted-foreground text-right px-6">Success rate</TableHead>
                 </TableRow>
              </TableHeader>
              <TableBody>
                 {(summary?.by_endpoint ?? []).length === 0 ? (
                   <TableRow>
                      <TableCell colSpan={3} className="py-10 text-center text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                         {loading ? 'Loading…' : 'No API calls recorded yet'}
                      </TableCell>
                   </TableRow>
                 ) : (
                   (summary?.by_endpoint ?? []).map(row => (
                     <TableRow key={row.endpoint} className="border-b border-border/10 hover:bg-muted/10">
                        <TableCell className="px-6 font-mono text-xs text-primary">{row.endpoint}</TableCell>
                        <TableCell className="text-xs font-bold text-white">{row.requests.toLocaleString()}</TableCell>
                        <TableCell className="px-6 text-right">
                           <Badge variant="outline" className={cn(
                             "text-[9px] font-black uppercase border-none",
                             row.success_rate >= 95 ? "text-emerald-500 bg-emerald-500/10" :
                             row.success_rate >= 80 ? "text-amber-500 bg-amber-500/10" : "text-rose-500 bg-rose-500/10"
                           )}>
                             {row.success_rate}%
                           </Badge>
                        </TableCell>
                     </TableRow>
                   ))
                 )}
              </TableBody>
           </Table>
        </CardContent>
      </Card>
    </div>
  );
}

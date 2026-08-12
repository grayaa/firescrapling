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
  Webhook
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../components/ui/table';
import { Button } from '../components/ui/button';
import { cn } from '../lib/utils';

// Mock Data
const stats = [
  { label: "Pages Crawled", value: "12,482", delta: "+18%", icon: Globe, color: "text-blue-500", bg: "bg-blue-500/10" },
  { label: "API Success Rate", value: "99.8%", delta: "Stable", icon: ShieldCheck, color: "text-emerald-500", bg: "bg-emerald-500/10" },
  { label: "Active Webhooks", value: "8", delta: "+2", icon: Webhook, color: "text-violet-500", bg: "bg-violet-500/10" },
  { label: "Credits Remaining", value: "4,820", delta: "-420", icon: Zap, color: "text-amber-500", bg: "bg-amber-500/10" },
];

const chartData = [
  { name: '01 Apr', success: 420, failed: 12 },
  { name: '05 Apr', success: 580, failed: 24 },
  { name: '10 Apr', success: 490, failed: 8 },
  { name: '15 Apr', success: 620, failed: 15 },
  { name: '20 Apr', success: 750, failed: 32 },
  { name: '25 Apr', success: 590, failed: 10 },
  { name: '30 Apr', success: 810, failed: 18 },
];

const recentCrawls = [
  { id: "job_9k2f1", url: "https://stripe.com/docs", status: "completed", pages: 142, time: "2m ago" },
  { id: "job_4h1s8", url: "https://vercel.com/blog", status: "completed", pages: 84, time: "15m ago" },
  { id: "job_3d9z2", url: "https://supabase.com/docs", status: "processing", pages: 32, time: "Just now" },
  { id: "job_7r4x5", url: "https://nextjs.org/docs", status: "failed", pages: 0, time: "1h ago" },
  { id: "job_1m8v3", url: "https://tailwindcss.com", status: "completed", pages: 215, time: "3h ago" },
];

export function SaaSOverview() {
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
              <CardTitle className="text-sm font-bold uppercase tracking-widest">Global Crawl Map</CardTitle>
              <Badge variant="secondary" className="text-[10px]">Real-time Status</Badge>
           </div>
        </CardHeader>
        <CardContent className="p-12 text-center space-y-4 opacity-50 grayscale transition-all hover:grayscale-0 hover:opacity-100">
           <div className="p-6 rounded-full bg-primary/5 border border-primary/10 inline-block">
              <Globe className="h-12 w-12 text-primary animate-pulse" />
           </div>
           <div className="space-y-1">
             <h3 className="text-lg font-heading font-black text-white">LIVE ENGINE ACTIVE</h3>
             <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Active nodes in US-East-1, EU-West-1, and Tokyo</p>
           </div>
        </CardContent>
      </Card>
    </div>
  );
}

// Re-using Lucide icon as component placeholder
const History = Clock;

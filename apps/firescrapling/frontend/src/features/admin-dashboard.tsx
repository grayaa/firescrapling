import React, { useState } from 'react';
import { 
  Shield, 
  Users, 
  Activity, 
  Server, 
  Globe, 
  AlertTriangle, 
  Search, 
  MoreHorizontal, 
  ArrowUpRight, 
  ArrowDownRight, 
  CreditCard, 
  UserPlus, 
  Lock, 
  UserCog,
  Settings,
  Menu,
  Bell,
  CheckCircle2,
  XCircle,
  Terminal,
  Zap,
  BarChart3,
  Filter
} from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '../components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { ScrollArea } from '../components/ui/scroll-area';

// --- Mock Data ---

const systemStats = [
  { label: "Worker Node Status", value: "Healthy", status: "success", icon: Server },
  { label: "Proxy Success Rate", value: "94.2%", status: "success", icon: Globe },
  { label: "Queue Latency", value: "142ms", status: "warning", icon: Activity },
  { label: "Active Jobs", value: "1,284", status: "neutral", icon: Zap },
];

const financialStats = [
  { label: "MRR", value: "$42,480", trend: "+12.5%", isUp: true },
  { label: "Churn Rate", value: "2.1%", trend: "-0.4%", isUp: false },
  { label: "New Signups (24h)", value: "182", trend: "+24", isUp: true },
];

const mockUsers = [
  { id: "usr_9k2f1", email: "alex@stripe.com", plan: "Enterprise", usage: 85, joined: "2026-01-12" },
  { id: "usr_4h1s8", email: "sarah@vercel.com", plan: "Pro", usage: 42, joined: "2026-02-05" },
  { id: "usr_3d9z2", email: "dev@supabase.io", plan: "Pro", usage: 98, joined: "2026-03-20" },
  { id: "usr_7r4x5", email: "mike@hobby.dev", plan: "Free", usage: 12, joined: "2026-04-01" },
  { id: "usr_1m8v3", email: "tech@startup.ai", plan: "Enterprise", usage: 64, joined: "2026-04-10" },
];

const errorLogs = [
  { time: "14:22:01", code: 503, domain: "amazon.com", msg: "Service Unavailable (Proxy Blocked)" },
  { time: "14:21:45", code: 403, domain: "linkedin.com", msg: "Forbidden (Auth Challenge)" },
  { time: "14:20:12", code: 500, domain: "github.com", msg: "Internal Server Error (Timeout)" },
  { time: "14:18:55", code: 429, domain: "twitter.com", msg: "Too Many Requests" },
];

const domainPerformance = [
  { domain: "amazon.com", success: "78%", failed: "22%", status: "critical" },
  { domain: "linkedin.com", success: "92%", failed: "8%", status: "healthy" },
  { domain: "stripe.com", success: "99.9%", failed: "0.1%", status: "healthy" },
  { domain: "google.com", success: "95%", failed: "5%", status: "healthy" },
];

// --- Components ---

export function AdminDashboard() {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-[#111827] flex flex-col font-sans antialiased">
      {/* Top Navigation */}
      <header className="h-14 border-b bg-white flex items-center justify-between px-6 sticky top-0 z-50">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2">
            <div className="bg-black p-1.5 rounded-md">
              <Shield className="h-4 w-4 text-white" />
            </div>
            <span className="font-bold tracking-tight text-sm uppercase">FireScrailing Admin</span>
          </div>
          <div className="relative w-96">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-gray-400" />
            <Input 
              placeholder="Search User ID, URL, or API Key..." 
              className="h-9 pl-9 bg-gray-50 border-gray-200 text-xs focus:ring-1 focus:ring-black rounded-md"
            />
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" className="relative">
            <Bell className="h-4 w-4 text-gray-500" />
            <span className="absolute top-2 right-2 w-1.5 h-1.5 bg-red-500 rounded-full border border-white" />
          </Button>
          <div className="h-8 w-8 rounded-full bg-gray-100 border border-gray-200 flex items-center justify-center text-[10px] font-bold">
            AD
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-56 border-r bg-white flex flex-col">
          <nav className="p-3 space-y-1">
            {[
              { id: 'overview', label: 'System Health', icon: Activity },
              { id: 'users', label: 'User Management', icon: Users },
              { id: 'proxies', label: 'Proxy Network', icon: Globe },
              { id: 'billing', label: 'Financials', icon: CreditCard },
              { id: 'settings', label: 'Admin Settings', icon: Settings },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2 rounded-md text-xs font-semibold transition-colors",
                  activeTab === item.id 
                    ? "bg-gray-100 text-black" 
                    : "text-gray-500 hover:bg-gray-50 hover:text-black"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </button>
            ))}
          </nav>
        </aside>

        {/* Content Area */}
        <ScrollArea className="flex-1">
          <div className="p-8 space-y-8 max-w-[1600px] mx-auto">
            
            {/* 1. Infrastructure Stats */}
            <div className="grid grid-cols-4 gap-4">
              {systemStats.map((stat, i) => (
                <Card key={i} className="shadow-none border-gray-200 rounded-lg">
                  <CardContent className="p-4 flex items-center justify-between">
                    <div className="space-y-1">
                      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">{stat.label}</p>
                      <div className="flex items-center gap-2">
                        <span className="text-xl font-bold tracking-tight">{stat.value}</span>
                        {stat.status === 'success' && <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />}
                        {stat.status === 'warning' && <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />}
                      </div>
                    </div>
                    <div className="p-2 bg-gray-50 rounded-md">
                      <stat.icon className="h-4 w-4 text-gray-400" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            <div className="grid grid-cols-3 gap-6">
              {/* 2. Financial Metrics */}
              <div className="col-span-2 grid grid-cols-3 gap-4">
                {financialStats.map((stat, i) => (
                  <Card key={i} className="shadow-none border-gray-200 rounded-lg bg-white">
                    <CardHeader className="p-4 pb-0">
                      <CardTitle className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">{stat.label}</CardTitle>
                    </CardHeader>
                    <CardContent className="p-4 pt-1">
                      <div className="text-2xl font-bold tracking-tight">{stat.value}</div>
                      <div className={cn(
                        "text-[10px] font-bold flex items-center gap-1 mt-1",
                        stat.isUp ? "text-green-600" : "text-red-600"
                      )}>
                        {stat.isUp ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                        {stat.trend} <span className="text-gray-400 ml-1">vs last month</span>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* 3. Error Log Terminal */}
              <Card className="shadow-none border-gray-200 rounded-lg bg-black text-gray-300 overflow-hidden">
                <CardHeader className="p-3 border-b border-gray-800 bg-[#111] flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Terminal className="h-3.5 w-3.5 text-red-500" />
                    <span className="text-[10px] font-bold uppercase tracking-widest text-white">Critical Error Log</span>
                  </div>
                  <Badge variant="outline" className="text-[8px] font-black border-red-900 text-red-500 py-0 h-4 bg-red-950/20">LIVE</Badge>
                </CardHeader>
                <ScrollArea className="h-32">
                  <div className="p-3 font-mono text-[10px] space-y-1.5">
                    {errorLogs.map((log, i) => (
                      <div key={i} className="flex gap-3 group hover:bg-white/5 transition-colors cursor-pointer p-1 rounded">
                        <span className="text-gray-600 shrink-0">{log.time}</span>
                        <span className="text-red-500 font-bold shrink-0">{log.code}</span>
                        <span className="text-gray-400 truncate">{log.domain} › {log.msg}</span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </Card>
            </div>

            {/* 4. User Management Table */}
            <Card className="shadow-none border-gray-200 rounded-lg overflow-hidden bg-white">
              <CardHeader className="p-6 border-b border-gray-100 flex flex-row items-center justify-between">
                <div className="space-y-1">
                  <CardTitle className="text-sm font-bold flex items-center gap-2">
                    <Users className="h-4 w-4" /> USER & SUBSCRIPTION MANAGEMENT
                  </CardTitle>
                  <CardDescription className="text-xs">Manage lifecycle, billing, and system access for all platform users.</CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="h-8 text-[10px] font-bold uppercase border-gray-200">
                    <Filter className="h-3 w-3 mr-1.5" /> Filter
                  </Button>
                  <Button size="sm" className="h-8 text-[10px] font-bold uppercase bg-black text-white hover:bg-gray-800">
                    <UserPlus className="h-3 w-3 mr-1.5" /> Add User
                  </Button>
                </div>
              </CardHeader>
              <Table>
                <TableHeader className="bg-gray-50">
                  <TableRow>
                    <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">User ID</TableHead>
                    <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">Email / Status</TableHead>
                    <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10 text-center">Plan</TableHead>
                    <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">Monthly Usage</TableHead>
                    <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10">Joined Date</TableHead>
                    <TableHead className="text-[10px] font-bold uppercase tracking-wider h-10 text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mockUsers.map((user) => (
                    <TableRow key={user.id} className="hover:bg-gray-50/50 transition-colors group">
                      <TableCell className="font-mono text-[10px] font-semibold text-gray-500">{user.id}</TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="text-xs font-bold">{user.email}</span>
                          <span className="text-[10px] text-gray-400 flex items-center gap-1">
                            <div className="w-1.5 h-1.5 bg-green-500 rounded-full" /> Verified
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className={cn(
                          "text-[9px] font-black px-2 py-0 h-4 uppercase tracking-tighter",
                          user.plan === 'Enterprise' ? "border-black bg-black text-white" : 
                          user.plan === 'Pro' ? "border-gray-200 bg-gray-50 text-gray-700" : "border-gray-100 text-gray-400"
                        )}>
                          {user.plan}
                        </Badge>
                      </TableCell>
                      <TableCell className="w-48">
                        <div className="space-y-1.5">
                          <div className="flex justify-between text-[9px] font-bold">
                            <span className="text-gray-400">{user.usage}% consumed</span>
                            <span className={user.usage > 90 ? "text-red-500" : "text-gray-500"}>
                              {Math.round(user.usage * 500)} / 50,000
                            </span>
                          </div>
                          <Progress 
                            value={user.usage} 
                            className="h-1 bg-gray-100" 
                            indicatorClassName={cn(
                              user.usage > 90 ? "bg-red-500" : "bg-black"
                            )}
                          />
                        </div>
                      </TableCell>
                      <TableCell className="text-[10px] font-semibold text-gray-500">{user.joined}</TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0 hover:bg-gray-100">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-48 bg-white border-gray-200">
                            <DropdownMenuLabel className="text-[10px] font-bold uppercase text-gray-400">Account Actions</DropdownMenuLabel>
                            <DropdownMenuItem className="text-xs font-semibold flex gap-2">
                              <UserCog className="h-3.5 w-3.5" /> Impersonate User
                            </DropdownMenuItem>
                            <DropdownMenuItem className="text-xs font-semibold flex gap-2">
                              <RefreshCcw className="h-3.5 w-3.5" /> Reset API Key
                            </DropdownMenuItem>
                            <DropdownMenuItem className="text-xs font-semibold flex gap-2">
                              <BarChart3 className="h-3.5 w-3.5" /> Adjust Credits
                            </DropdownMenuItem>
                            <DropdownMenuSeparator className="bg-gray-100" />
                            <DropdownMenuItem className="text-xs font-semibold text-red-600 flex gap-2 focus:bg-red-50 focus:text-red-600">
                              <Lock className="h-3.5 w-3.5" /> Suspend Account
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>

            {/* 5. Domain Performance Analytics */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <Card className="shadow-none border-gray-200 rounded-lg overflow-hidden bg-white">
                <CardHeader className="p-4 border-b border-gray-100 bg-gray-50">
                  <CardTitle className="text-[10px] font-bold text-gray-500 uppercase tracking-widest flex items-center gap-2">
                    <Globe className="h-3.5 w-3.5" /> Target Domain Health
                  </CardTitle>
                </CardHeader>
                <Table>
                  <TableBody>
                    {domainPerformance.map((item, i) => (
                      <TableRow key={i} className="hover:bg-gray-50/30 border-gray-100 last:border-0">
                        <TableCell className="text-xs font-bold py-3">{item.domain}</TableCell>
                        <TableCell className="text-center py-3">
                          <div className="flex flex-col items-center">
                            <span className="text-[10px] font-bold text-green-600">{item.success}</span>
                            <span className="text-[8px] uppercase font-black text-gray-400">Success</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-center py-3">
                          <div className="flex flex-col items-center">
                            <span className={cn(
                              "text-[10px] font-bold",
                              item.status === 'critical' ? "text-red-500" : "text-gray-400"
                            )}>{item.failed}</span>
                            <span className="text-[8px] uppercase font-black text-gray-400">Failed</span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right py-3">
                           <Badge className={cn(
                             "text-[8px] font-black uppercase py-0 px-2 h-4",
                             item.status === 'healthy' ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-500"
                           )}>
                             {item.status}
                           </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>

              <Card className="shadow-none border-gray-200 rounded-lg bg-white flex flex-col justify-center items-center p-8 space-y-4 opacity-50 grayscale hover:grayscale-0 hover:opacity-100 transition-all">
                <div className="p-4 rounded-full bg-gray-50 border border-gray-100">
                  <Globe className="h-10 w-10 text-gray-300" />
                </div>
                <div className="text-center space-y-1">
                  <h4 className="text-xs font-bold uppercase tracking-widest">Global Proxy Map</h4>
                  <p className="text-[10px] text-gray-400 font-medium">Real-time geographic distribution of residental IP traffic.</p>
                </div>
                <Badge variant="outline" className="text-[9px] font-black border-gray-200 text-gray-400">Rendering Engine Offline</Badge>
              </Card>
            </div>

          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

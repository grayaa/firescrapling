import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { 
  Key, 
  Plus, 
  Trash2, 
  Copy, 
  Clock, 
  Activity, 
  Zap, 
  Check, 
  ExternalLink,
  ShieldCheck,
  Server,
  Terminal,
  RefreshCcw,
  BarChart3,
  CalendarDays
} from 'lucide-react';
import { rpcCall } from '../api';
import { cn } from '../lib/utils';
import { UserData } from './auth';

interface DashboardProps {
  user: UserData;
}

interface ApiKey {
  id: string;
  key_value: string;
  name: string;
  created_at: string;
  last_used: string | null;
}

interface ApiUsage {
  id: string;
  endpoint: string;
  status_code: number;
  response_time_ms: number;
  created_at: string;
  key_name: string | null;
}

export function UserDashboard({ user }: DashboardProps) {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [usage, setUsage] = useState<ApiUsage[]>([]);
  const [loading, setLoading] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [creatingKey, setCreatingKey] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const keysData = await rpcCall({ func: 'get_api_keys', args: { user_id: user.id } });
      setKeys(keysData);
      const usageData = await rpcCall({ func: 'get_api_usage', args: { user_id: user.id, limit: 50 } });
      setUsage(usageData);
    } catch (err) {
      console.error("Dashboard data fetch error", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [user.id]);

  const handleCreateKey = async () => {
    if (!newKeyName) return;
    setCreatingKey(true);
    try {
      const res = await rpcCall({ func: 'create_api_key', args: { user_id: user.id, name: newKeyName } });
      if (res.success) {
        setKeys(prev => [res.key, ...prev]);
        setNewKeyName('');
        fetchData();
      }
    } catch (err) {
      console.error("Key creation error", err);
    } finally {
      setCreatingKey(false);
    }
  };

  const handleDeleteKey = async (id: string) => {
    try {
      await rpcCall({ func: 'delete_api_key', args: { user_id: user.id, key_id: id } });
      setKeys(prev => prev.filter(k => k.id !== id));
    } catch (err) {
      console.error("Key deletion error", err);
    }
  };

  const copyKey = (val: string) => {
    navigator.clipboard.writeText(val);
    setCopiedKey(val);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const formatTime = (iso: string) => {
    return new Date(iso).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500 pb-20">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-3xl font-heading font-black tracking-tight text-white flex items-center gap-3">
             <LayoutDashboard className="h-8 w-8 text-orange-500" />
             USER DASHBOARD
          </h2>
          <p className="text-muted-foreground">Manage your API keys, track real-time usage, and monitor engine performance.</p>
        </div>
        <div className="flex items-center gap-2">
           <Button variant="outline" size="sm" onClick={fetchData} className="border-white/5 bg-zinc-900/50">
             <RefreshCcw className={cn("h-4 w-4 mr-2", loading && "animate-spin")} /> Refresh
           </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: "Total Extractions", value: usage.length, icon: Zap, color: "text-orange-500" },
          { label: "Success Rate", value: usage.length ? "100%" : "0%", icon: ShieldCheck, color: "text-emerald-500" },
          { label: "Avg Latency", value: usage.length ? `${Math.round(usage.reduce((a, b) => a + b.response_time_ms, 0) / usage.length)}ms` : "0ms", icon: Activity, color: "text-blue-500" },
          { label: "Active Keys", value: keys.length, icon: Key, color: "text-amber-500" }
        ].map((stat, i) => (
          <Card key={i} className="bg-zinc-900/40 border-white/5 backdrop-blur-md">
            <CardContent className="p-4 flex items-center gap-4">
               <div className={cn("p-2 rounded-lg bg-zinc-950/50 border border-white/5", stat.color)}>
                 <stat.icon className="h-5 w-5" />
               </div>
               <div>
                  <div className="text-xs font-bold text-muted-foreground uppercase tracking-widest">{stat.label}</div>
                  <div className="text-xl font-heading font-black text-white">{stat.value}</div>
               </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Keys Section */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="bg-zinc-900/40 border-white/5 backdrop-blur-md overflow-hidden">
            <CardHeader className="bg-zinc-950/50 border-b border-white/5 p-4">
              <CardTitle className="text-sm font-bold flex items-center gap-2 uppercase tracking-widest">
                <Key className="h-4 w-4 text-orange-500" /> API Keys
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
               <div className="p-4 border-b border-white/5 bg-black/20 space-y-3">
                  <div className="space-y-1">
                    <Label className="text-[10px] uppercase font-bold text-muted-foreground">New Key Name</Label>
                    <div className="flex gap-2">
                      <Input 
                        placeholder="e.g. Production Web" 
                        value={newKeyName}
                        onChange={e => setNewKeyName(e.target.value)}
                        className="h-9 text-xs bg-black/40 border-white/10"
                      />
                      <Button size="sm" onClick={handleCreateKey} disabled={creatingKey || !newKeyName} className="bg-orange-600 hover:bg-orange-700">
                         {creatingKey ? <RefreshCcw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>
               </div>
               <ScrollArea className="h-[400px]">
                 <div className="divide-y divide-white/5">
                   {keys.map(key => (
                     <div key={key.id} className="p-4 hover:bg-white/5 transition-colors group">
                        <div className="flex items-center justify-between mb-2">
                           <span className="text-xs font-bold text-white uppercase tracking-tight">{key.name}</span>
                           <Button 
                             variant="ghost" 
                             size="icon" 
                             className="h-6 w-6 text-muted-foreground hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                             onClick={() => handleDeleteKey(key.id)}
                            >
                             <Trash2 className="h-3.5 w-3.5" />
                           </Button>
                        </div>
                        <div className="flex items-center gap-2 bg-black/40 p-2 rounded border border-white/5 mb-3">
                           <code className="text-[10px] font-mono text-orange-200 truncate flex-1">
                             {copiedKey === key.key_value ? key.key_value : key.key_value.substring(0, 12) + "..."}
                           </code>
                           <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-white" onClick={() => copyKey(key.key_value)}>
                             {copiedKey === key.key_value ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                           </Button>
                        </div>
                        <div className="flex items-center gap-4 text-[9px] font-bold text-muted-foreground uppercase tracking-widest">
                           <span className="flex items-center gap-1"><CalendarDays className="h-3 w-3" /> {formatTime(key.created_at)}</span>
                           {key.last_used && <span className="flex items-center gap-1 text-orange-400"><Zap className="h-3 w-3 fill-current" /> {formatTime(key.last_used)}</span>}
                        </div>
                     </div>
                   ))}
                   {keys.length === 0 && (
                     <div className="p-8 text-center text-xs text-muted-foreground opacity-50 uppercase tracking-widest font-bold">
                       No API Keys Found
                     </div>
                   )}
                 </div>
               </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* Usage Section */}
        <div className="lg:col-span-2 space-y-6">
           <Card className="bg-zinc-900/40 border-white/5 backdrop-blur-md overflow-hidden h-full">
            <CardHeader className="bg-zinc-950/50 border-b border-white/5 p-4 flex flex-row items-center justify-between">
              <CardTitle className="text-sm font-bold flex items-center gap-2 uppercase tracking-widest">
                <BarChart3 className="h-4 w-4 text-orange-500" /> API Usage History
              </CardTitle>
              <Badge variant="outline" className="text-[9px] border-white/10 uppercase bg-black/40">Last 50 Events</Badge>
            </CardHeader>
            <CardContent className="p-0">
               <div className="overflow-x-auto">
                 <Table>
                   <TableHeader className="bg-black/20">
                     <TableRow className="border-white/5 hover:bg-transparent">
                       <TableHead className="text-[10px] font-bold uppercase tracking-widest py-3">Endpoint</TableHead>
                       <TableHead className="text-[10px] font-bold uppercase tracking-widest py-3">Key Name</TableHead>
                       <TableHead className="text-[10px] font-bold uppercase tracking-widest py-3">Status</TableHead>
                       <TableHead className="text-[10px] font-bold uppercase tracking-widest py-3">Latency</TableHead>
                       <TableHead className="text-[10px] font-bold uppercase tracking-widest py-3 text-right">Time</TableHead>
                     </TableRow>
                   </TableHeader>
                   <TableBody>
                     {usage.map(u => (
                       <TableRow key={u.id} className="border-white/5 hover:bg-white/5 transition-colors">
                         <TableCell className="py-3">
                            <div className="flex items-center gap-2">
                               <div className="p-1 rounded bg-orange-500/10"><Terminal className="h-3 w-3 text-orange-500" /></div>
                               <span className="text-[11px] font-mono font-bold text-zinc-300">{u.endpoint}</span>
                            </div>
                         </TableCell>
                         <TableCell className="py-3">
                           <Badge variant="secondary" className="text-[9px] font-bold bg-zinc-950/50 text-muted-foreground border-white/5">
                             {u.key_name || "Internal"}
                           </Badge>
                         </TableCell>
                         <TableCell className="py-3">
                           <div className="flex items-center gap-1.5">
                             <div className={cn("h-1.5 w-1.5 rounded-full shadow-[0_0_8px]", u.status_code === 200 ? "bg-emerald-500 shadow-emerald-500/50" : "bg-red-500 shadow-red-500/50")} />
                             <span className={cn("text-[10px] font-black", u.status_code === 200 ? "text-emerald-400" : "text-red-400")}>{u.status_code}</span>
                           </div>
                         </TableCell>
                         <TableCell className="py-3">
                            <span className="text-[10px] font-mono font-bold text-muted-foreground">{u.response_time_ms}ms</span>
                         </TableCell>
                         <TableCell className="py-3 text-right">
                            <span className="text-[10px] text-muted-foreground font-medium">{formatTime(u.created_at)}</span>
                         </TableCell>
                       </TableRow>
                     ))}
                   </TableBody>
                 </Table>
                 {usage.length === 0 && (
                   <div className="p-20 flex flex-col items-center justify-center opacity-30">
                      <Activity className="h-12 w-12 text-muted-foreground mb-4" />
                      <div className="text-xs font-bold uppercase tracking-widest">No API activity yet</div>
                   </div>
                 )}
               </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

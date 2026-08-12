import React from 'react';
import { 
  Key, 
  Plus, 
  Trash2, 
  Copy, 
  ShieldCheck, 
  Zap, 
  Check, 
  AlertCircle, 
  ExternalLink,
  ChevronRight,
  MoreVertical,
  Key as KeyIcon,
  Activity,
  CalendarDays,
  Lock,
  RefreshCcw,
  PlusCircle
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '../components/ui/table';
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger,
  DialogFooter
} from '../components/ui/dialog';
import { cn } from '../lib/utils';

// Mock API Keys
const initialKeys = [
  { id: "1", name: "Production", value: "sk_live_v2f9...8d2k", created: "2026-03-12", lastUsed: "2m ago" },
  { id: "2", name: "Development", value: "sk_test_k9s2...r1m4", created: "2026-04-05", lastUsed: "1h ago" },
  { id: "3", name: "Analytics Dashboard", value: "sk_live_m7v3...j1p9", created: "2026-04-10", lastUsed: "Never" },
];

export function SaaSApiKeys() {
  const [keys, setKeys] = React.useState(initialKeys);
  const [copiedId, setCopiedId] = React.useState<string | null>(null);
  const [newKeyName, setNewKeyName] = React.useState('');
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const [generatedKey, setGeneratedKey] = React.useState<string | null>(null);

  const copyKey = (id: string, val: string) => {
    navigator.clipboard.writeText(val);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleGenerate = () => {
    const newKey = {
      id: Math.random().toString(36).substr(2, 9),
      name: newKeyName || "Untitled Key",
      value: "sk_live_" + Math.random().toString(36).substr(2, 12),
      created: new Date().toISOString().split('T')[0],
      lastUsed: "Never"
    };
    setGeneratedKey(newKey.value);
    setKeys([newKey, ...keys]);
    setIsModalOpen(false);
    setNewKeyName('');
  };

  const deleteKey = (id: string) => {
    setKeys(keys.filter(k => k.id !== id));
  };

  return (
    <div className="p-6 md:p-8 space-y-8 animate-in fade-in duration-500 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-3xl font-heading font-black tracking-tight text-white uppercase">API Keys</h2>
          <p className="text-muted-foreground text-sm uppercase tracking-widest font-bold">Manage your bearer tokens to programmatically extract data</p>
        </div>
        
        <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
           <DialogTrigger asChild>
              <Button className="bg-primary hover:bg-primary/90 font-bold uppercase tracking-widest shadow-xl shadow-primary/20 transition-all hover:scale-[1.02] active:scale-[0.98]">
                 <Plus className="h-4 w-4 mr-2" /> Generate New Key
              </Button>
           </DialogTrigger>
           <DialogContent className="bg-zinc-950 border-white/10 sm:max-w-md">
             <DialogHeader>
               <DialogTitle className="text-xl font-heading font-black text-white uppercase">Create API Key</DialogTitle>
               <DialogDescription className="text-xs font-bold uppercase tracking-widest text-muted-foreground mt-2">
                 Name your key so you can easily identify it in your usage logs.
               </DialogDescription>
             </DialogHeader>
             <div className="space-y-4 py-4">
               <div className="space-y-2">
                 <Label className="text-[10px] uppercase font-bold text-muted-foreground">Key Name</Label>
                 <Input 
                   placeholder="e.g. Production App" 
                   value={newKeyName}
                   onChange={(e) => setNewKeyName(e.target.value)}
                   className="bg-black/60 border-white/10"
                 />
               </div>
             </div>
             <DialogFooter>
               <Button variant="ghost" onClick={() => setIsModalOpen(false)} className="text-xs font-bold uppercase text-muted-foreground">Cancel</Button>
               <Button onClick={handleGenerate} className="bg-primary font-bold uppercase tracking-widest">Create Key</Button>
             </DialogFooter>
           </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {/* Security Warning */}
        <div className="bg-amber-500/5 border border-amber-500/20 rounded-2xl p-6 flex gap-4 items-start animate-in slide-in-from-top-4 duration-700">
           <div className="p-2 rounded-xl bg-amber-500/10 text-amber-500">
             <AlertCircle className="h-5 w-5" />
           </div>
           <div className="space-y-1 flex-1">
              <h4 className="text-sm font-bold text-amber-500 uppercase tracking-widest">Security Advisory</h4>
              <p className="text-[11px] text-amber-500/70 leading-relaxed font-bold">
                API keys are sensitive credentials. Never expose them in client-side code, frontend environments, or public repositories.
                If a key is compromised, revoke it immediately and generate a new one.
              </p>
           </div>
           <Button variant="ghost" size="sm" className="text-amber-500 text-[10px] font-black uppercase hover:bg-amber-500/10">
              Security Best Practices <ChevronRight className="h-3 w-3 ml-1" />
           </Button>
        </div>

        {/* API Keys Table */}
        <Card className="bg-card/40 border-border/50 backdrop-blur-md overflow-hidden">
          <CardHeader className="bg-muted/10 border-b border-border/50 p-6">
             <div className="flex items-center justify-between">
                <div>
                   <CardTitle className="text-sm font-bold uppercase tracking-widest flex items-center gap-2">
                      <KeyIcon className="h-4 w-4 text-primary" /> Active Bearer Tokens
                   </CardTitle>
                   <CardDescription className="text-[10px] uppercase font-bold text-muted-foreground mt-1">Manage your programmatically controlled extraction tokens</CardDescription>
                </div>
                <Badge variant="secondary" className="text-[10px] bg-zinc-950/50">{keys.length} Active</Badge>
             </div>
          </CardHeader>
          <CardContent className="p-0">
             <div className="overflow-x-auto">
                <Table>
                   <TableHeader className="bg-muted/5 border-b border-border/10">
                      <TableRow className="hover:bg-transparent">
                         <TableHead className="text-[10px] uppercase font-black tracking-widest text-muted-foreground py-4 px-6">Name</TableHead>
                         <TableHead className="text-[10px] uppercase font-black tracking-widest text-muted-foreground py-4">Key</TableHead>
                         <TableHead className="text-[10px] uppercase font-black tracking-widest text-muted-foreground py-4">Created</TableHead>
                         <TableHead className="text-[10px] uppercase font-black tracking-widest text-muted-foreground py-4">Last Used</TableHead>
                         <TableHead className="text-right py-4 px-6"></TableHead>
                      </TableRow>
                   </TableHeader>
                   <TableBody>
                      {keys.length === 0 ? (
                        <TableRow>
                           <TableCell colSpan={5} className="py-20 text-center space-y-4 opacity-50 grayscale transition-all hover:grayscale-0 hover:opacity-100">
                              <div className="p-4 rounded-full bg-zinc-950/50 border border-white/5 inline-block">
                                 <KeyIcon className="h-10 w-10 text-primary" />
                              </div>
                              <div className="space-y-1">
                                <h3 className="text-lg font-heading font-black text-white">NO KEYS FOUND</h3>
                                <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Generate your first API key to start using the engine programmatically.</p>
                              </div>
                           </TableCell>
                        </TableRow>
                      ) : (
                        keys.map((key) => (
                          <TableRow key={key.id} className="border-b border-border/10 hover:bg-muted/10 transition-colors group">
                             <TableCell className="px-6 py-4">
                                <div className="flex items-center gap-3">
                                   <div className="h-8 w-8 rounded-lg bg-zinc-950/50 border border-white/5 flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-all">
                                      <Zap className="h-3.5 w-3.5 fill-current" />
                                   </div>
                                   <span className="text-sm font-bold text-white uppercase tracking-tight">{key.name}</span>
                                </div>
                             </TableCell>
                             <TableCell>
                                <div className="flex items-center gap-2">
                                   <code className="text-xs font-mono text-zinc-400 bg-zinc-950/50 px-2 py-1 rounded border border-white/5">{key.value}</code>
                                   <Button 
                                     variant="ghost" 
                                     size="icon" 
                                     className="h-8 w-8 text-muted-foreground hover:text-white"
                                     onClick={() => copyKey(key.id, key.value)}
                                   >
                                     {copiedId === key.id ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                                   </Button>
                                </div>
                             </TableCell>
                             <TableCell className="text-xs font-bold text-muted-foreground uppercase tracking-tighter">{key.created}</TableCell>
                             <TableCell>
                                <Badge variant="outline" className={cn(
                                   "text-[9px] font-black uppercase border-none px-1.5",
                                   key.lastUsed === 'Never' ? "text-muted-foreground bg-zinc-950/50" : "text-emerald-500 bg-emerald-500/10"
                                )}>
                                   {key.lastUsed}
                                </Badge>
                             </TableCell>
                             <TableCell className="px-6 text-right">
                                <div className="flex justify-end gap-2">
                                   <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-white">
                                      <Activity className="h-3.5 w-3.5" />
                                   </Button>
                                   <Button 
                                     variant="ghost" 
                                     size="icon" 
                                     className="h-8 w-8 text-muted-foreground hover:text-rose-500 transition-colors"
                                     onClick={() => deleteKey(key.id)}
                                   >
                                      <Trash2 className="h-3.5 w-3.5" />
                                   </Button>
                                </div>
                             </TableCell>
                          </TableRow>
                        ))
                      )}
                   </TableBody>
                </Table>
             </div>
          </CardContent>
          <CardFooter className="bg-muted/5 border-t border-border/10 p-4">
             <div className="flex items-center gap-4 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                <span className="flex items-center gap-1.5"><ShieldCheck className="h-3 w-3 text-emerald-500" /> AES-256 Encryption</span>
                <span className="flex items-center gap-1.5"><CalendarDays className="h-3 w-3" /> Rotating Keys Recommended</span>
             </div>
          </CardFooter>
        </Card>
      </div>

      {/* Generated Key Modal (One-time view) */}
      <Dialog open={!!generatedKey} onOpenChange={() => setGeneratedKey(null)}>
         <DialogContent className="bg-zinc-950 border-white/10 sm:max-w-md">
            <DialogHeader>
               <DialogTitle className="text-xl font-heading font-black text-white uppercase flex items-center gap-3">
                  <ShieldCheck className="h-6 w-6 text-emerald-500" /> API KEY GENERATED
               </DialogTitle>
               <DialogDescription className="text-xs font-bold uppercase tracking-widest text-muted-foreground mt-2">
                  Copy this key now. For security, we will only show it this once.
               </DialogDescription>
            </DialogHeader>
            <div className="bg-emerald-500/5 border border-emerald-500/20 p-6 rounded-2xl space-y-4">
               <div className="space-y-2">
                  <Label className="text-[10px] uppercase font-bold text-emerald-500">Your New Secret Key</Label>
                  <div className="relative group">
                     <Input 
                       readOnly 
                       value={generatedKey || ''} 
                       className="bg-black/60 border-emerald-500/20 text-emerald-100 font-mono text-sm h-12 pr-12"
                     />
                     <Button 
                       size="icon" 
                       variant="ghost" 
                       className="absolute right-2 top-2 text-emerald-500 hover:text-emerald-400"
                       onClick={() => copyKey('new', generatedKey || '')}
                     >
                        {copiedId === 'new' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                     </Button>
                  </div>
               </div>
            </div>
            <DialogFooter>
               <Button onClick={() => setGeneratedKey(null)} className="w-full bg-emerald-600 hover:bg-emerald-700 font-bold uppercase tracking-widest">
                  I've saved the key
               </Button>
            </DialogFooter>
         </DialogContent>
      </Dialog>
    </div>
  );
}

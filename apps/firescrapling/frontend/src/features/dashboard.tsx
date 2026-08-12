import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Clock, Globe, FileText, CheckCircle2, AlertCircle, Loader2, Trash2, Terminal } from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from '../components/ui/button';

export interface Job {
  id: string;
  type: 'scrape' | 'crawl';
  url: string;
  status: 'running' | 'completed' | 'failed';
  created_at: string;
  finished_at?: string;
}

interface HistorySidebarProps {
  jobs: Job[];
  activeJobId: string | null;
  onSelectJob: (job: Job) => void;
  onDeleteJob: (id: string) => void;
  loading?: boolean;
}

export function HistorySidebar({ jobs, activeJobId, onSelectJob, onDeleteJob, loading }: HistorySidebarProps) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b flex items-center justify-between bg-card/30 backdrop-blur-sm">
        <h2 className="font-heading font-semibold flex items-center gap-2">
          <Clock className="h-4 w-4 text-primary" />
          Job History
        </h2>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>
      
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {jobs.length === 0 && !loading ? (
          <div className="text-center py-8 text-muted-foreground text-sm">
            No history yet. Start your first scrape!
          </div>
        ) : (
          jobs.map((job) => (
            <div
              key={job.id}
              onClick={() => onSelectJob(job)}
              className={cn(
                "group relative rounded-lg border p-3 cursor-pointer transition-all hover:shadow-md",
                activeJobId === job.id 
                  ? "bg-primary/10 border-primary/30 ring-1 ring-primary/20" 
                  : "bg-card/40 border-border hover:border-primary/20 hover:bg-card/60"
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={job.type === 'crawl' ? 'default' : 'outline'} className="text-[10px] px-1 py-0 h-4 uppercase">
                      {job.type}
                    </Badge>
                    <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                      {new Date(job.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <div className="text-sm font-medium truncate text-foreground group-hover:text-primary transition-colors">
                    {job.url}
                  </div>
                </div>
                
                <div className="flex flex-col items-end gap-2">
                  {job.status === 'running' ? (
                    <Loader2 className="h-3 w-3 animate-spin text-primary" />
                  ) : job.status === 'completed' ? (
                    <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                  ) : (
                    <AlertCircle className="h-3 w-3 text-destructive" />
                  )}
                  
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteJob(job.id);
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

interface StatusIndicatorProps {
  status: string;
  progress: number;
}

export function StatusIndicator({ status, progress }: StatusIndicatorProps) {
  return (
    <div className="space-y-3 p-4 bg-primary/5 rounded-xl border border-primary/10 animate-in fade-in slide-in-from-bottom-2">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2 font-medium">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span>{status || 'Processing...'}</span>
        </div>
        <span className="text-primary font-bold">{progress}%</span>
      </div>
      <div className="h-2 w-full bg-primary/10 rounded-full overflow-hidden">
        <div 
          className="h-full bg-gradient-to-r from-orange-600 to-red-500 transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

export interface ActivityLog {
  content: string;
  progress?: number;
  created_at: string;
}

interface JobActivityLogProps {
  logs: ActivityLog[];
}

export function JobActivityLog({ logs }: JobActivityLogProps) {
  return (
    <Card className="bg-card/40 border-border overflow-hidden">
      <CardHeader className="p-4 flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-xs uppercase tracking-widest text-muted-foreground flex items-center gap-2">
          <Terminal className="h-3 w-3" />
          Real-Time Activity Logs
        </CardTitle>
        <Badge variant="outline" className="text-[9px] h-4 px-1 bg-emerald-500/5 text-emerald-500 border-emerald-500/20">
          LIVE
        </Badge>
      </CardHeader>
      <CardContent className="p-0 border-t">
        <div className="max-h-[250px] overflow-y-auto bg-black/20 p-3 space-y-1.5 font-mono text-[11px]">
          {logs.length === 0 ? (
            <div className="text-muted-foreground italic opacity-50 py-4 text-center">
              Awaiting engine signals...
            </div>
          ) : (
            logs.map((log, idx) => (
              <div key={idx} className="flex gap-3 leading-relaxed group border-l-2 border-transparent hover:border-primary/30 pl-2 transition-colors">
                <span className="text-muted-foreground opacity-40 select-none whitespace-nowrap">
                   {new Date(log.created_at).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
                <span className={cn(
                  "flex-1 break-words",
                  log.content.includes("ERROR") ? "text-red-400" : 
                  log.content.includes("🔍") ? "text-orange-400" :
                  log.content.includes("completed") ? "text-emerald-400" : "text-orange-100/80"
                )}>
                  {log.content}
                </span>
                {log.progress !== null && (
                  <span className="text-primary/60 font-bold ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
                    {log.progress}%
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
